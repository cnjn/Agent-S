from __future__ import annotations

import base64
import io
import logging
from functools import partial
from typing import Dict, List, Optional, TypedDict

import pyautogui
from PIL import Image
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph, CompiledGraph
from langgraph.types import interrupt

from gui_agents.s3.agents.grounding import OSWorldACI
from gui_agents.s3.utils.common_utils import create_pyautogui_code, parse_code_from_string

logger = logging.getLogger("desktopenv.agent.s4")


class AgentState(TypedDict, total=False):
    instruction: str
    messages: List[BaseMessage]
    notes: List[str]
    screenshot: Optional[bytes]
    plan: Optional[str]
    plan_code: Optional[str]
    exec_code: Optional[str]
    turn: int
    max_turns: int
    done: bool
    fail_reason: Optional[str]
    scaled_width: int
    scaled_height: int
    last_observation: Optional[str]


def _encode_image_bytes(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


def _capture_observation(state: AgentState, scaled_width: int, scaled_height: int):
    screenshot = pyautogui.screenshot()
    screenshot = screenshot.resize((scaled_width, scaled_height), Image.LANCZOS)
    buffer = io.BytesIO()
    screenshot.save(buffer, format="PNG")
    screenshot_bytes = buffer.getvalue()

    text_summary = f"Step {state.get('turn', 0) + 1}: Screen snapshot for task `{state['instruction']}`"
    human_message = HumanMessage(
        content=[
            {"type": "text", "text": text_summary},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{_encode_image_bytes(screenshot_bytes)}",
                    "detail": "high",
                },
            },
        ]
    )
    return screenshot_bytes, human_message


def _trim_messages(messages: List[BaseMessage], limit: int) -> List[BaseMessage]:
    if limit <= 0 or len(messages) <= limit:
        return messages
    return messages[-limit:]


def observe_node(state: AgentState, *, scaled_width: int, scaled_height: int, history_limit: int):
    screenshot_bytes, human_message = _capture_observation(
        state, scaled_width=scaled_width, scaled_height=scaled_height
    )
    messages = state.get("messages", []) + [human_message]
    return {
        "screenshot": screenshot_bytes,
        "messages": _trim_messages(messages, history_limit),
        "turn": state.get("turn", 0) + 1,
    }


def _ai_message_to_text(message: AIMessage) -> str:
    if isinstance(message.content, str):
        return message.content
    chunks = []
    for block in message.content:
        if isinstance(block, dict) and block.get("type") == "text":
            chunks.append(block.get("text", ""))
    return "\n".join(chunks)


def plan_node(
    state: AgentState,
    *,
    llm: BaseChatModel,
    grounding_agent: OSWorldACI,
    history_limit: int,
    tool_lookup: Dict[str, StructuredTool],
):
    messages = state.get("messages", [])
    response = llm.invoke(messages)
    tool_messages: List[BaseMessage] = []
    exec_code: Optional[str] = None
    plan_code: Optional[str] = None

    if getattr(response, "tool_calls", None):
        plan_text = response.content or "Tool invocation"
        for call in response.tool_calls:
            tool = tool_lookup.get(call["name"])
            if not tool:
                logger.warning("未注册的工具: %s", call["name"])
                continue
            tool_output = tool.invoke(call["args"])
            tool_messages.append(
                ToolMessage(content=str(tool_output), tool_call_id=call["id"])
            )
            exec_code = str(tool_output)
            plan_code = call["name"]
    else:
        plan_text = _ai_message_to_text(response)
        plan_code = parse_code_from_string(plan_text)
        obs = {"screenshot": state.get("screenshot")}

        try:
            grounding_agent.assign_screenshot(obs)
            exec_code = create_pyautogui_code(grounding_agent, plan_code, obs)
        except Exception as exc:  # pragma: no cover - best effort fallback
            logger.error("无法编译执行代码，将等待一拍: %s", exc)
            exec_code = grounding_agent.wait(1.333)

    done = str(exec_code).strip().upper() == "DONE"
    fail = str(exec_code).strip().upper() == "FAIL"

    logger.info("S4 PLAN:\n%s", plan_text)

    updated_messages = messages + [response] + tool_messages

    return {
        "plan": plan_text,
        "plan_code": plan_code,
        "exec_code": exec_code,
        "done": state.get("done", False) or done or fail,
        "fail_reason": state.get("fail_reason")
        or ("Agent returned FAIL" if fail else None),
        "messages": _trim_messages(updated_messages, history_limit),
    }


def act_node(state: AgentState):
    exec_code = state.get("exec_code")
    if not exec_code:
        return {}

    payload = interrupt(
        {
            "action": "execute_code",
            "code": exec_code,
            "plan": state.get("plan"),
            "plan_code": state.get("plan_code"),
            "turn": state.get("turn"),
        }
    )

    notes = state.get("notes", [])
    if payload:
        incoming_notes = payload.get("notes") or []
        if isinstance(incoming_notes, str):
            incoming_notes = [incoming_notes]
        notes = notes + incoming_notes

    status = (payload or {}).get("status", "ok")
    done = state.get("done", False)
    fail_reason = state.get("fail_reason")

    if status == "fail":
        done = True
        fail_reason = payload.get("fail_reason", "Execution failed")
    elif payload and payload.get("done"):
        done = True

    return {
        "notes": notes,
        "exec_code": None,
        "last_observation": (payload or {}).get("observation"),
        "done": done,
        "fail_reason": fail_reason,
    }


def decide_node(state: AgentState):
    return state


def _route_decision(state: AgentState):
    if state.get("done"):
        return "end"
    if state.get("turn", 0) >= state.get("max_turns", 8):
        return "end"
    return "continue"


def build_agent_graph(
    llm: BaseChatModel,
    grounding_agent: OSWorldACI,
    *,
    tool_lookup: Dict[str, StructuredTool],
    max_turns: int,
    scaled_width: int,
    scaled_height: int,
) -> CompiledGraph:
    history_limit = max(max_turns * 4, 16)
    builder = StateGraph(AgentState)
    builder.add_node(
        "observe",
        partial(
            observe_node,
            scaled_width=scaled_width,
            scaled_height=scaled_height,
            history_limit=history_limit,
        ),
    )
    builder.add_node(
        "plan",
        partial(
            plan_node,
            llm=llm,
            grounding_agent=grounding_agent,
            history_limit=history_limit,
            tool_lookup=tool_lookup,
        ),
    )
    builder.add_node("act", act_node)
    builder.add_node("decide", decide_node)

    builder.add_edge(START, "observe")
    builder.add_edge("observe", "plan")
    builder.add_edge("plan", "act")
    builder.add_edge("act", "decide")
    builder.add_conditional_edges("decide", _route_decision, {"continue": "observe", "end": END})

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)

