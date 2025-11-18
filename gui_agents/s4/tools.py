from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_core.tools import StructuredTool

from gui_agents.s3.agents.grounding import OSWorldACI


def build_ui_tools(grounding_agent: OSWorldACI) -> List[StructuredTool]:
    """将 OSWorld ACI 方法包装为 LangChain 工具。"""

    tools: List[StructuredTool] = []

    def click_tool(
        element_description: str,
        num_clicks: int = 1,
        button_type: str = "left",
        hold_keys: Optional[List[str]] = None,
    ) -> str:
        return grounding_agent.click(
            element_description=element_description,
            num_clicks=num_clicks,
            button_type=button_type,
            hold_keys=hold_keys or [],
        )

    def type_tool(
        element_description: Optional[str] = None,
        text: str = "",
        overwrite: bool = False,
        enter: bool = False,
    ) -> str:
        return grounding_agent.type(
            element_description=element_description,
            text=text,
            overwrite=overwrite,
            enter=enter,
        )

    def drag_tool(
        starting_description: str,
        ending_description: str,
        hold_keys: Optional[List[str]] = None,
    ) -> str:
        return grounding_agent.drag_and_drop(
            starting_description=starting_description,
            ending_description=ending_description,
            hold_keys=hold_keys or [],
        )

    def highlight_tool(
        starting_phrase: str,
        ending_phrase: str,
        button: str = "left",
    ) -> str:
        return grounding_agent.highlight_text_span(
            starting_phrase=starting_phrase,
            ending_phrase=ending_phrase,
            button=button,
        )

    def scroll_tool(element_description: str, clicks: int, shift: bool = False) -> str:
        return grounding_agent.scroll(
            element_description=element_description, clicks=clicks, shift=shift
        )

    def hotkey_tool(keys: List[str]) -> str:
        return grounding_agent.hotkey(keys=keys)

    def hold_press_tool(hold_keys: List[str], press_keys: List[str]) -> str:
        return grounding_agent.hold_and_press(
            hold_keys=hold_keys, press_keys=press_keys
        )

    def open_tool(app_or_filename: str) -> str:
        return grounding_agent.open(app_or_filename=app_or_filename)

    def switch_tool(app_code: str) -> str:
        return grounding_agent.switch_applications(app_code=app_code)

    def save_notes_tool(text: List[str]) -> str:
        return grounding_agent.save_to_knowledge(text=text)

    def set_cell_values_tool(
        cell_values: Dict[str, Any], app_name: str, sheet_name: str
    ) -> str:
        return grounding_agent.set_cell_values(
            cell_values=cell_values, app_name=app_name, sheet_name=sheet_name
        )

    def call_code_agent_tool(task: Optional[str] = None) -> str:
        return grounding_agent.call_code_agent(task=task)

    def wait_tool(seconds: float) -> str:
        return grounding_agent.wait(seconds)

    def done_tool() -> str:
        return grounding_agent.done()

    def fail_tool() -> str:
        return grounding_agent.fail()

    name_doc_pairs = [
        ("click", click_tool),
        ("type", type_tool),
        ("drag_and_drop", drag_tool),
        ("highlight_text_span", highlight_tool),
        ("scroll", scroll_tool),
        ("hotkey", hotkey_tool),
        ("hold_and_press", hold_press_tool),
        ("open", open_tool),
        ("switch_applications", switch_tool),
        ("save_to_knowledge", save_notes_tool),
        ("set_cell_values", set_cell_values_tool),
        ("call_code_agent", call_code_agent_tool),
        ("wait", wait_tool),
        ("done", done_tool),
        ("fail", fail_tool),
    ]

    for method_name, func in name_doc_pairs:
        original = getattr(grounding_agent, method_name)
        func.__name__ = method_name
        func.__doc__ = original.__doc__
        tools.append(StructuredTool.from_function(func))

    return tools

