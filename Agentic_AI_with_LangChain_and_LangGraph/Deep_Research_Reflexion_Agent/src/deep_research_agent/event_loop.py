from langchain_core.messages import BaseMessage, ToolMessage
from langgraph.graph import END

MAX_ITERATIONS = 3

def event_loop(state: list[BaseMessage]) -> str:
    count_tool_visits = sum(isinstance(item, ToolMessage) for item in state)

    if count_tool_visits >= MAX_ITERATIONS:
        return END

    return "execute_tools"

