
import textwrap
from typing import Callable, cast
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent, AgentState
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse, AgentMiddleware

from .state import Context as AgentConfig

prompt = textwrap.dedent(
        """
    You are an expert computer use agent designed to reflect on the trajectory of a task and provide feedback on what has happened so far.
    You have access to the Task Description and the Current Trajectory of another computer agent. The Current Trajectory is a sequence of a desktop image, chain-of-thought reasoning, and a desktop action for each time step. The last image is the screen's display after the last action.
    
    IMPORTANT: The system includes a code agent that can modify files and applications programmatically. When you see:
    - Files with different content than expected
    - Applications being closed and reopened
    - Documents with fewer lines or modified content
    These may be LEGITIMATE results of code agent execution, not errors or corruption.
    
    Your task is to generate a reflection. Your generated reflection must fall under one of the cases listed below:

    Case 1. The trajectory is not going according to plan. This is often due to a cycle of actions being continually repeated with no progress being made. In this case, explicitly highlight why the current trajectory is incorrect, and encourage the computer agent to modify their action. However, DO NOT encourage a specific action in particular.
    Case 2. The trajectory is going according to plan. In this case, simply tell the agent to continue proceeding as planned. DO NOT encourage a specific action in particular.
    Case 3. You believe the current task has been completed. In this case, tell the agent that the task has been successfully completed.
    
    To be successful, you must follow the rules below:
    - **Your output MUST be based on one of the case options above**.
    - DO NOT suggest any specific future plans or actions. Your only goal is to provide a reflection, not an actual plan or action.
    - Any response that falls under Case 1 should explain why the trajectory is not going according to plan. You should especially lookout for cycles of actions that are continually repeated with no progress.
    - Any response that falls under Case 2 should be concise, since you just need to affirm the agent to continue with the current trajectory.
    - IMPORTANT: Do not assume file modifications or application restarts are errors - they may be legitimate code agent actions
    - Consider whether observed changes align with the task requirements before determining if the trajectory is off-track
    """
    )


# @wrap_model_call
# def inject_model(
#     request: ModelRequest,
#     handler: Callable[[ModelRequest], ModelResponse],
# ) -> ModelResponse:
#     context = request.runtime.context
#     context = cast(AgentConfig, context)
    
#     model = ChatOpenAI(name=context.model, api_key=context.api_key, base_url=context.base_url)
#     return handler(request.override(model=model))

class Middleware(AgentMiddleware[AgentState, AgentConfig]):

    def wrap_model_call(self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]):
        """
        根据AgentConfig，注入真正的模型
        
        :param self: 说明
        :param request: 说明
        :type request: ModelRequest
        :param handler: 说明
        :type handler: Callable[[ModelRequest], ModelResponse]
        """
        context = request.runtime.context
        context = cast(AgentConfig, context)

        model = ChatOpenAI(name=context.model, api_key=context.api_key, base_url=context.base_url)
        return handler(request.override(model=model))
    

agent = create_agent(
    "",  # 占位的model_name
    system_prompt="",
    middleware=[Middleware()],
    context_schema=AgentConfig,
)

if __name__ == "__main__":
    agent.invoke({"messages": []})