"""The ``agent`` node: render the conversation into the model."""

from typing import cast

from langchain_core.messages import AIMessage

from .agent_state import AgentState
from .model_react import get_model_react


def call_model(state: AgentState) -> dict:
    """Ask the model what to do next given the whole message history.

    The reply is an ``AIMessage``. If it carries ``tool_calls`` the graph routes
    to the ``tools`` node; otherwise it is the final answer. The message is
    returned in an ``add_messages``-compatible dict so LangGraph appends it to
    the state.
    """

    response = cast(
        AIMessage,
        get_model_react().invoke({"scratch_pad": state["messages"]}),
    )
    return {"messages": [response]}
