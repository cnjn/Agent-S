from __future__ import annotations

import uuid
from typing import Dict, Optional

from langchain_core.messages import SystemMessage
from langgraph.types import Command

from gui_agents.s3.agents.grounding import OSWorldACI
from gui_agents.s4.graph import build_agent_graph
from gui_agents.s4.models import build_chat_model
from gui_agents.s4.prompts import build_skipped_actions, build_worker_prompt
from gui_agents.s4.tools import build_ui_tools


class AgentS4:
    """LangGraph 驱动的 UI 代理。"""

    def __init__(
        self,
        worker_engine_params: Dict,
        grounding_agent: OSWorldACI,
        *,
        platform: str,
        max_turns: int,
        scaled_width: int,
        scaled_height: int,
    ):
        self.platform = platform
        self.max_turns = max_turns
        self.scaled_width = scaled_width
        self.scaled_height = scaled_height

        self.grounding_agent = grounding_agent
        self.llm = build_chat_model(worker_engine_params)
        skipped_actions = build_skipped_actions(grounding_agent, platform)
        self.worker_prompt_template = build_worker_prompt(type(grounding_agent), platform, skipped_actions)

        self.tools = build_ui_tools(self.grounding_agent)
        self.tool_lookup = {tool.name: tool for tool in self.tools}
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        self.graph = build_agent_graph(
            self.llm_with_tools,
            grounding_agent,
            tool_lookup=self.tool_lookup,
            max_turns=max_turns,
            scaled_width=scaled_width,
            scaled_height=scaled_height,
        )

        self.thread_id: Optional[str] = None
        self.config = None

    def reset(self):
        self.thread_id = str(uuid.uuid4())
        self.config = {"configurable": {"thread_id": self.thread_id}}

    def _build_initial_state(self, instruction: str):
        prompt = self.worker_prompt_template.replace("TASK_DESCRIPTION", instruction)
        messages = [SystemMessage(content=prompt)]
        return {
            "instruction": instruction,
            "messages": messages,
            "notes": [],
            "plan": None,
            "plan_code": None,
            "exec_code": None,
            "turn": 0,
            "max_turns": self.max_turns,
            "done": False,
            "fail_reason": None,
            "scaled_width": self.scaled_width,
            "scaled_height": self.scaled_height,
        }

    def start(self, instruction: str):
        if self.config is None:
            self.reset()
        initial_state = self._build_initial_state(instruction)
        return self.graph.invoke(initial_state, config=self.config)

    def resume(self, payload: Dict):
        if self.config is None:
            raise RuntimeError("Agent 尚未启动任务")
        return self.graph.invoke(Command(resume=payload), config=self.config)

