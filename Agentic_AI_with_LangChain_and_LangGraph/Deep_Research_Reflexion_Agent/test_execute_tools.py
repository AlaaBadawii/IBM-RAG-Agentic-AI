import json
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import execute_tools as execute_tools_module
from execute_tools import SUPPORTED_TOOLS, execute_tools


def _ai_message(*tool_calls):
    return AIMessage(content="", tool_calls=list(tool_calls))


def _tool_call(name, queries, tool_id):
    return {"name": name, "args": {"search_queries": queries}, "id": tool_id}


def _mock_tavily(monkeypatch, side_effect=None):
    tool = MagicMock()
    if side_effect is None:
        tool.invoke.side_effect = lambda query: f"result for {query}"
    else:
        tool.invoke.side_effect = side_effect
    monkeypatch.setattr(execute_tools_module, "tavily_tool", tool)
    return tool


def test_supported_tools_are_the_two_agent_tools():
    assert SUPPORTED_TOOLS == {"AnswerQuestion", "ReviseAnswer"}


def test_empty_state_returns_no_messages():
    assert execute_tools([]) == []


def test_non_ai_last_message_returns_no_messages(monkeypatch):
    _mock_tavily(monkeypatch)
    assert execute_tools([HumanMessage(content="hello")]) == []


def test_ai_message_without_tool_calls_returns_no_messages(monkeypatch):
    _mock_tavily(monkeypatch)
    assert execute_tools([AIMessage(content="just text")]) == []


def test_single_query_returns_a_linked_tool_message(monkeypatch):
    tool = _mock_tavily(monkeypatch)
    message = _ai_message(_tool_call("AnswerQuestion", ["query one"], "call-1"))

    result = execute_tools([message])

    assert len(result) == 1
    tool_message = result[0]
    assert isinstance(tool_message, ToolMessage)
    assert tool_message.tool_call_id == "call-1"
    assert json.loads(tool_message.content) == {"query one": "result for query one"}
    tool.invoke.assert_called_once_with("query one")


def test_multiple_queries_are_all_executed(monkeypatch):
    tool = _mock_tavily(monkeypatch)
    message = _ai_message(_tool_call("AnswerQuestion", ["q1", "q2", "q3"], "call-1"))

    result = execute_tools([message])

    payload = json.loads(result[0].content)
    assert list(payload) == ["q1", "q2", "q3"]
    assert tool.invoke.call_count == 3


def test_each_supported_tool_call_gets_its_own_message(monkeypatch):
    _mock_tavily(monkeypatch)
    message = _ai_message(
        _tool_call("AnswerQuestion", ["q1"], "call-a"),
        _tool_call("ReviseAnswer", ["q2"], "call-b"),
    )

    result = execute_tools([message])

    assert [m.tool_call_id for m in result] == ["call-a", "call-b"]


def test_unsupported_tool_names_are_ignored(monkeypatch):
    tool = _mock_tavily(monkeypatch)
    message = _ai_message(_tool_call("SomeOtherTool", ["q1"], "call-x"))

    assert execute_tools([message]) == []
    tool.invoke.assert_not_called()


def test_empty_query_list_yields_empty_payload_without_searching(monkeypatch):
    tool = _mock_tavily(monkeypatch)
    message = _ai_message(_tool_call("AnswerQuestion", [], "call-1"))

    result = execute_tools([message])

    assert len(result) == 1
    assert json.loads(result[0].content) == {}
    tool.invoke.assert_not_called()


def test_search_failure_is_recorded_and_does_not_abort_other_queries(monkeypatch):
    def side_effect(query):
        if query == "bad-query":
            raise RuntimeError("tavily exploded")
        return f"result for {query}"

    _mock_tavily(monkeypatch, side_effect=side_effect)
    message = _ai_message(_tool_call("AnswerQuestion", ["good-query", "bad-query"], "call-1"))

    result = execute_tools([message])

    payload = json.loads(result[0].content)
    assert payload["good-query"] == "result for good-query"
    assert "tavily exploded" in payload["bad-query"]


def test_regression_reads_search_queries_not_the_singular_search_query(monkeypatch):
    """The executor once read ``search_query``, so research silently never ran."""

    tool = _mock_tavily(monkeypatch)
    message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "AnswerQuestion",
                "args": {
                    "search_queries": ["correct-key"],
                    "search_query": ["decoy-key"],
                },
                "id": "call-1",
            }
        ],
    )

    result = execute_tools([message])

    payload = json.loads(result[0].content)
    assert list(payload) == ["correct-key"]
    tool.invoke.assert_called_once_with("correct-key")
