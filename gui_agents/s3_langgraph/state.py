from dataclasses import dataclass, field
import os
from typing import Annotated, Literal, Optional
from typing_extensions import TypedDict
from operator import add
from pydantic import SecretStr

class Observation(TypedDict, total=False):
    screenshot_b64: str
    width: int
    height: int
    captured_at: float  # 时间戳

class ActionPlan(TypedDict, total=False):
    rationale: str  
    plan_code: str
    grounded_code: str
    tool: Literal["gui", "code_agent", "noop"]
    approval_required: bool

class CodeAgentState(TypedDict, total=False):
    request: Optional[str]
    result: Optional[dict]
    steps_used: int
    budget: int

class TurnLog(TypedDict, total=False):
    turn: int  # 轮数
    plan: str  # 本轮计划
    plan_code: str  # 本轮计划对应的代码
    executed: str  # 本轮执行的操作
    reflection: Optional[str]  # 本轮反思
    screenshot_digest: str  # 截图摘要

class AgentState(TypedDict, total=False):
    instruction: str  # 任务指令
    env: dict  # platform, screen, permissions
    observation: Observation  # 最新截图
    plan: Optional[ActionPlan]  # 当前计划
    reflection: Optional[str]   # 反思
    code_agent: Optional[CodeAgentState]
    trajectory: Annotated[list[TurnLog], add]  # 历史记录
    notes: Annotated[list[str], add]  # 额外笔记
    turn: int   # 当前轮数
    status: Literal["running", "waiting", "done", "fail"]

class InputState(TypedDict, total=False):
    instruction: str

@dataclass
class Context:
    model: str = 'google/gemini-2.5-flash-preview-09-2025'   # 模型名称
    api_key: SecretStr = SecretStr(os.getenv("API_KEY", ""))  # API密钥，始终用 SecretStr 包装
    base_url: str = 'https://openrouter.ai/api/v1/chat/completions'  # 基础URL
