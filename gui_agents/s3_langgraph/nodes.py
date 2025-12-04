from langgraph.runtime import Runtime

from .state import AgentState, Context, InputState

def start(state: InputState, runtime: Runtime[Context]):
    print("Starting agent with state:", state)
    print("Using runtime:", runtime)

def end(state: AgentState, runtime: Runtime[Context]):
    print("Ending agent with state:", state)
    print("Using runtime:", runtime)