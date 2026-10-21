"""Build the ReAct agent graph.

The workflow is the classic two-node ReAct loop plus a conditional edge::

    agent -> (tool calls?) -> tools -> agent
              (no tool calls) -> END

* ``agent`` (:mod:`react_agent.call_model`) renders every message so far into
  the tool-bound model.
* ``tools`` (:mod:`react_agent.tool_execution`) runs the requested tools and
  appends ``ToolMessage`` results.
* ``should_continue`` (:mod:`react_agent.should_continue`) sends the run back to
  ``agent`` while the model still wants tools, and to ``END`` once it answers or
  the tool-round limit is reached.

Importing this module compiles the graph, which is cheap and offline: no node
runs and no client is created until :func:`run` (or ``graph.invoke``) is called.
"""

from langgraph.graph import END, StateGraph

from .agent_state import AgentState
from .call_model import call_model
from .should_continue import should_continue
from .tool_execution import tool_node


def build_graph():
    """Construct and compile the ReAct workflow."""

    workflow = StateGraph(AgentState)

    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)

    workflow.set_entry_point("agent")
    workflow.add_edge("tools", "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"continue": "tools", "end": END},
    )

    return workflow.compile()


graph = build_graph()
