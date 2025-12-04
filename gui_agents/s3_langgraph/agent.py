from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import InMemorySaver

from .state import AgentState, Context as AgentConfig
from .nodes import *

# model = ChatOpenAI(name="gpt-4", temperature=0)

agent_builder = StateGraph(AgentState, AgentConfig, input_schema=InputState)

agent_builder.add_node(start)
agent_builder.add_node(end)

agent_builder.add_edge("start", "end")
agent_builder.set_entry_point("start")
agent = agent_builder.compile(InMemorySaver())

if __name__ == "__main__":
    agent.invoke({"instruction": "打开浏览器，搜索滑板鞋"}, {"configurable": {"thread_id": 0}}, context=AgentConfig())