import logging
import platform
from typing import Dict, Any, List

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.language_models import BaseChatModel

from gui_agents.s3.memory.procedural_memory import PROCEDURAL_MEMORY
from gui_agents.s3.utils.common_utils import parse_code_from_string, create_pyautogui_code
from gui_agents.s3_langgraph.state import AgentState
from gui_agents.s3_langgraph.utils import OSWorldACI

logger = logging.getLogger("desktopenv.agent")

class AgentNodes:
    def __init__(self, worker_model: BaseChatModel, grounding_agent: OSWorldACI):
        self.worker_model = worker_model
        self.grounding_agent = grounding_agent
        self.platform = platform.system().lower()
        
        # Initialize system prompt
        skipped_actions = []
        if self.platform != "linux":
            skipped_actions.append("set_cell_values")
            
        self.system_prompt = PROCEDURAL_MEMORY.construct_simple_worker_procedural_memory(
            OSWorldACI, skipped_actions=skipped_actions
        ).replace("CURRENT_OS", self.platform)

    def worker_node(self, state: AgentState) -> Dict[str, Any]:
        messages = state["messages"]
        screenshot = state["screenshot"]
        instruction = state["instruction"]
        
        # If it's the first step, prepend system prompt and instruction
        if not messages:
            sys_prompt_with_task = self.system_prompt.replace("TASK_DESCRIPTION", instruction)
            messages = [
                SystemMessage(content=sys_prompt_with_task),
                HumanMessage(
                    content=[
                        {"type": "text", "text": "The initial screen is provided. No action has been taken yet."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{screenshot}"},
                        },
                    ]
                )
            ]
        else:
            # Add latest screenshot to the last user message if needed
            # In LangGraph, we usually append new messages. 
            # Here we assume the previous execution node added a HumanMessage with the result, 
            # but we need to attach the NEW screenshot to it or create a new message.
            # Let's check how execution_node handles it.
            pass

        # Invoke model
        response = self.worker_model.invoke(messages)
        
        return {"messages": [response]}

    def execution_node(self, state: AgentState) -> Dict[str, Any]:
        messages = state["messages"]
        last_message = messages[-1]
        
        if not isinstance(last_message, AIMessage):
            raise ValueError("Last message should be from AI")
            
        content = last_message.content
        code = parse_code_from_string(content)
        
        # Update grounding agent with current observation
        obs = {"screenshot": state["screenshot"]}
        self.grounding_agent.assign_screenshot(obs)
        self.grounding_agent.set_task_instruction(state["instruction"])
        
        result_text = ""
        done = False
        fail = False
        
        if not code:
            result_text = "No code found in response."
        else:
            if "DONE" in code:
                done = True
                result_text = "Task Completed."
            elif "FAIL" in code:
                fail = True
                result_text = "Task Failed."
            else:
                try:
                    # Execute code
                    # create_pyautogui_code evaluates the code string which calls agent methods
                    # The agent methods return a string of python code to be executed by exec()
                    # But create_pyautogui_code in common_utils does eval(code). 
                    # Wait, let's check common_utils.py again.
                    # def create_pyautogui_code(agent, code: str, obs: Dict) -> str:
                    #     agent.assign_screenshot(obs)
                    #     exec_code = eval(code)
                    #     return exec_code
                    
                    # So eval(code) calls agent.click(...) which returns a string like "import pyautogui; ..."
                    # Then we need to exec() that string.
                    
                    # We need to make sure 'agent' variable is available for eval context if the code uses 'agent.click'
                    # The code usually looks like 'agent.click(...)'.
                    # So we need a local dict with 'agent': self.grounding_agent
                    
                    # However, create_pyautogui_code takes 'agent' as argument, but inside eval(code), 'agent' must be defined in globals/locals.
                    # common_utils.py: exec_code = eval(code)
                    # If code is "agent.click(...)", then "agent" must be in scope.
                    # common_utils.py doesn't seem to pass locals to eval. 
                    # Let's check common_utils.py content again.
                    # It just says `exec_code = eval(code)`. 
                    # This implies `agent` must be in the scope where `create_pyautogui_code` is defined or called? 
                    # No, `eval` uses current scope. `agent` is passed as argument to `create_pyautogui_code`.
                    # So `agent` IS in scope.
                    
                    exec_code = create_pyautogui_code(self.grounding_agent, code, obs)
                    
                    # Now execute the generated pyautogui code
                    # We need to execute it in the environment.
                    # Since we are running locally (as per original agent design), we use exec().
                    # But wait, the original code in cli_app.py does:
                    # info, code = agent.predict(...)
                    # exec(code[0])
                    
                    # So here we should return the exec_code to be executed?
                    # Or execute it here?
                    # If we execute it here, we are the "environment".
                    # Let's execute it here.
                    
                    exec(exec_code)
                    result_text = "Action executed successfully."
                    
                except Exception as e:
                    logger.error(f"Execution error: {e}")
                    result_text = f"Error executing action: {e}"

        # Capture new screenshot after action
        # In a real scenario, we need to wait a bit and take a screenshot.
        # Since we are inside the agent logic, we might need to ask the environment for a new screenshot.
        # But `AgentState` has `screenshot`. We need to UPDATE it.
        # We need access to the "environment" to take a screenshot.
        # In `cli_app.py`, the loop takes a screenshot.
        # Here, `execution_node` should probably take the screenshot.
        
        import pyautogui
        import io
        from PIL import Image
        
        # Wait a bit for action to take effect
        import time
        time.sleep(1.0)
        
        # Take new screenshot
        # We need to respect the scaling used in main.py
        # But for now let's just take it.
        # Ideally, the "env" should be passed to nodes or available.
        # I'll assume we can use pyautogui directly as in the original code.
        
        screen_width, screen_height = pyautogui.size()
        # We should probably use the same scaling logic as in cli_app.py
        # For simplicity, let's just take it and resize to what grounding agent expects if needed.
        # But grounding agent expects original size for resizing coordinates back.
        # Let's just save it.
        
        screenshot_img = pyautogui.screenshot()
        # Resize if needed? Original code resizes to scaled_width/height.
        # Let's assume we keep it simple for now or use a helper.
        
        buffered = io.BytesIO()
        screenshot_img.save(buffered, format="PNG")
        new_screenshot = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        # Create response message
        response_msg = HumanMessage(
            content=[
                {"type": "text", "text": f"Action result: {result_text}\n\nHere is the new screen:"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{new_screenshot}"},
                },
            ]
        )
        
        return {
            "messages": [response_msg],
            "screenshot": new_screenshot,
            "loop_step": state["loop_step"] + 1
        }

