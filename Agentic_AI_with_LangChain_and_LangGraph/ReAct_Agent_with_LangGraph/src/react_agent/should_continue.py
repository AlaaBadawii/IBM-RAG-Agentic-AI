"""Conditional edge that decides whether the agent keeps using tools.

The router ends the run when the model returns a final answer (no tool calls)
or when the configured tool-round limit is reached. The limit is the safety
valve that guarantees termination even if the model gets stuck calling tools
forever.
"""

import os

from langchain_core.messages import ToolMessage

from .agent_state import AgentState

DEFAULT_MAX_ITERATIONS = 6


def _max_iterations() -> int:
    """Read the tool-round limit from ``REACT_MAX_ITERATIONS`` (default 6)."""

    raw = os.environ.get("REACT_MAX_ITERATIONS", "").strip()
    if not raw:
        return DEFAULT_MAX_ITERATIONS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_ITERATIONS
    return value if value > 0 else DEFAULT_MAX_ITERATIONS


def should_continue(state: AgentState) -> str:
    """Return ``"continue"`` to run tools, or ``"end"`` to stop.

    * No tool calls in the last message -> the model answered -> ``"end"``.
    * Otherwise, if the number of completed tool rounds has reached the limit,
      stop with ``"end"`` (the final ``AIMessage`` is still in the state).
    * Otherwise, ``"continue"`` to execute the requested tools.
    """

    messages = state["messages"]
    last_message = messages[-1]

    if not getattr(last_message, "tool_calls", None):
        return "end"

    completed_rounds = sum(isinstance(message, ToolMessage) for message in messages)
    if completed_rounds >= _max_iterations():
        return "end"

    return "continue"
