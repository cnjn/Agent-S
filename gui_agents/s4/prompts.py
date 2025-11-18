from __future__ import annotations

from typing import List, Type

from gui_agents.s3.agents.grounding import OSWorldACI
from gui_agents.s3.memory.procedural_memory import PROCEDURAL_MEMORY


def build_worker_prompt(aci_cls: Type[OSWorldACI], platform: str, skipped_actions: List[str]) -> str:
    """复用 S3 的程序化记忆生成系统提示。"""

    base_prompt = PROCEDURAL_MEMORY.construct_simple_worker_procedural_memory(
        aci_cls, skipped_actions=skipped_actions
    )

    return base_prompt.replace("CURRENT_OS", platform)


def build_skipped_actions(grounding_agent: OSWorldACI, platform: str) -> List[str]:
    skipped_actions: List[str] = []
    if platform != "linux":
        skipped_actions.append("set_cell_values")

    if not getattr(grounding_agent, "env", None) or not getattr(
        getattr(grounding_agent, "env", None), "controller", None
    ):
        skipped_actions.append("call_code_agent")

    return skipped_actions

