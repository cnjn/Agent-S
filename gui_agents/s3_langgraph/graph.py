from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel

from gui_agents.s3_langgraph.state import AgentState
from gui_agents.s3_langgraph.nodes import AgentNodes
from gui_agents.s3_langgraph.utils import OSWorldACI

def should_continue(state: AgentState):
    """Determine if the agent should continue or end."""
    messages = state["messages"]
    last_message = messages[-1]
    content = last_message.content
    
    if "Task Completed" in content or "Task Failed" in content:
        return END
    
    # Optional: Check for max steps
    if state.get("loop_step", 0) > 15:
        return END
        
    return "worker"

def create_graph(worker_model: BaseChatModel, grounding_agent: OSWorldACI):
    """Create the LangGraph agent."""
    nodes = AgentNodes(worker_model, grounding_agent)
    
    workflow = StateGraph(AgentState)
    
    workflow.add_node("worker", nodes.worker_node)
    workflow.add_node("execution", nodes.execution_node)
    
    workflow.set_entry_point("worker")
    
    workflow.add_edge("worker", "execution")
    workflow.add_conditional_edges(
        "execution",
        should_continue,
        {
            "worker": "worker",
            END: END
        }
    )
    
    return workflow.compile()
