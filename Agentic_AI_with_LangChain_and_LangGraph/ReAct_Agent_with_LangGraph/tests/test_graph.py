"""Structure of the compiled ReAct graph."""

from react_agent import graph


def _all_edges():
    return list(graph.graph.get_graph().edges)


def test_graph_compiles_with_expected_nodes():
    nodes = set(graph.graph.get_graph().nodes)
    assert {"agent", "tools"} <= nodes


def test_entry_point_and_static_edge():
    edges = {(edge.source, edge.target) for edge in _all_edges()}
    assert ("__start__", "agent") in edges
    assert ("tools", "agent") in edges


def test_agent_routes_conditionally_to_tools_and_end():
    conditional = {
        (edge.source, edge.target)
        for edge in _all_edges()
        if getattr(edge, "conditional", False)
    }
    assert ("agent", "tools") in conditional
    assert ("agent", "__end__") in conditional


def test_build_graph_returns_a_runnable_graph():
    from react_agent.graph import build_graph

    compiled = build_graph()
    assert hasattr(compiled, "invoke")
