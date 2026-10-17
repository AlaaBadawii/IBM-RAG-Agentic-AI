from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END

from deep_research_agent import graph
from deep_research_agent.event_loop import MAX_ITERATIONS
from deep_research_agent.event_loop import event_loop as route


def _answer_message(name, answer, tool_id):
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": {"answer": answer}, "id": tool_id}],
    )


def test_graph_compiles_with_expected_nodes():
    nodes = set(graph.app.get_graph().nodes)
    assert {"respond", "execute_tools", "revisor"} <= nodes


def test_graph_entry_point_and_static_edges():
    edges = {(edge.source, edge.target) for edge in graph.app.get_graph().edges}
    assert ("__start__", "respond") in edges
    assert ("respond", "execute_tools") in edges
    assert ("execute_tools", "revisor") in edges


def test_conditional_edges_route_only_back_to_tools_or_to_the_end():
    conditional = {
        (edge.source, edge.target)
        for edge in graph.app.get_graph().edges
        if getattr(edge, "conditional", False)
    }
    assert conditional == {("revisor", "execute_tools"), ("revisor", "__end__")}


def test_event_loop_continues_below_the_iteration_limit():
    state = [
        HumanMessage(content="q"),
        ToolMessage(content="{}", tool_call_id="1"),
    ]
    assert route(state) == "execute_tools"


def test_event_loop_ignores_non_tool_messages():
    assert route([HumanMessage(content="q"), AIMessage(content="")]) == "execute_tools"


def test_event_loop_stops_at_the_iteration_limit():
    state = [
        ToolMessage(content="{}", tool_call_id=str(index))
        for index in range(MAX_ITERATIONS)
    ]
    assert route(state) == END


def test_max_iterations_is_a_small_positive_number():
    assert isinstance(MAX_ITERATIONS, int)
    assert 1 <= MAX_ITERATIONS <= 10


def test_extract_answers_returns_draft_then_revisions_in_order():
    messages = [
        HumanMessage(content="q"),
        _answer_message("AnswerQuestion", "draft", "1"),
        ToolMessage(content="{}", tool_call_id="1"),
        _answer_message("ReviseAnswer", "revision 1", "2"),
        ToolMessage(content="{}", tool_call_id="2"),
        _answer_message("ReviseAnswer", "revision 2", "3"),
    ]

    assert graph.extract_answers(messages) == ["draft", "revision 1", "revision 2"]


def test_extract_answers_handles_messages_without_answers():
    assert graph.extract_answers([]) == []
    assert graph.extract_answers(["raw string", HumanMessage(content="q")]) == []
    assert graph.extract_answers([AIMessage(content="no tool calls")]) == []
