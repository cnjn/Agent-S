import base64
from datetime import datetime

from langgraph.runtime import Runtime
from langchain_openai import ChatOpenAI
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from .utils import screenshot
from .state import AgentState, Context, InputState, Observation
from .prompts import *


def start(state: InputState, runtime: Runtime[Context]):
    print("Starting agent with state:", state)
    print("Using runtime:", runtime)

def end(state: AgentState, runtime: Runtime[Context]):
    print("Ending agent with state:", state)
    print("Using runtime:", runtime)

def inject_prompt(state: AgentState):
    ...


def obs(state: AgentState):
    shot = screenshot()
    return {
        "observation": Observation(screenshot_b64=base64.b64encode(shot.getvalue()).decode('utf-8'), captured_at=datetime.now().timestamp())
    }


def reflect(state: AgentState, runtime: Runtime[Context]):
    
    model = ChatOpenAI(
        name=runtime.context.model,
        api_key=runtime.context.api_key,
        base_url=runtime.context.base_url
    )
    
    base64_image = state.get('observation', {})['screenshot_b64']
    if state.get('turn', 0) == 0:
        prompt = REFLECTION_PROMPT + textwrap.dedent(f"""
            Task Description: {state['instruction']}
            Current Trajectory below:
            """)
        
        return {
            "reflection_messages": [
                SystemMessage(prompt),
                HumanMessage([
                    "The initial screen is provided. No action has been taken yet.",
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                ])
            ],
            "reflection": ""
        }
    else:
        message = HumanMessage([
            state.get("plan", {})['rationale'],
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
        ])
        response = model.invoke({"messages": state["reflection_messages"] + [message]}) # type: ignore

        return {
            "reflection_messages": [message, response],
            "reflection": response.text
        }


def plan(state: AgentState, runtime: Runtime[Context]):
    if state.get('turn', 0) == 0:
        prompt = 
        message = HumanMessage([
            "The initial screen is provided. No action has been taken yet.",
        ])