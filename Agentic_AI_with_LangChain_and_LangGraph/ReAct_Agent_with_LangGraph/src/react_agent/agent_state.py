"""The graph state shared by every node in the ReAct workflow."""

from collections.abc import Sequence
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State of the agent: an append-only list of chat messages.

    ``add_messages`` is a LangGraph reducer. When a node returns
    ``{"messages": [...]}`` the reducer appends those messages to the existing
    history (keyed by message id, so re-emitting the same message does not
    duplicate it) instead of replacing the list. This is what lets the model
    see the full conversation, including every previous tool call and result.
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]
