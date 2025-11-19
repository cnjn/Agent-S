from typing import TypedDict, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    messages: List[BaseMessage]
    screenshot: Optional[str]  # Base64 string
    instruction: str
    notes: List[str]
    scratchpad: Dict[str, Any]
    loop_step: int
