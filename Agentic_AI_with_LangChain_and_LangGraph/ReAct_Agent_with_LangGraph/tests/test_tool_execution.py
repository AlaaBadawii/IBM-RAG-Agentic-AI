"""The ``tools`` node: execution, linking, and failure handling."""

import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from react_agent import tool_execution
from react_agent.tool_execution import tool_node


class _FakeTool:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def invoke(self, args):
        self.calls.append(args)
        if self.error is not None:
            raise self.error
        return self.result


def _ai_message(*tool_calls):
    return AIMessage(content="", tool_calls=list(tool_calls))


def _tool_call(name, args, tool_id):
    return {"name": name, "args": args, "id": tool_id}


def _patch_registry(monkeypatch, registry):
    monkeypatch.setattr(tool_execution, "tools_by_name", registry)


def test_non_ai_last_message_returns_no_output():
    assert tool_node({"messages": [HumanMessage(content="hi")]}) == {"messages": []}


def test_empty_state_returns_no_output():
    assert tool_node({"messages": []}) == {"messages": []}


def test_ai_message_without_tool_calls_returns_no_output(monkeypatch):
    _patch_registry(monkeypatch, {})
    assert tool_node({"messages": [AIMessage(content="done")]}) == {"messages": []}


def test_single_call_runs_the_tool_and_links_the_id(monkeypatch):
    tool = _FakeTool(result="14")
    _patch_registry(monkeypatch, {"calculator": tool})
    state = {"messages": [_ai_message(_tool_call("calculator", {"expression": "2+3*4"}, "c1"))]}

    result = tool_node(state)["messages"]

    assert len(result) == 1
    message = result[0]
    assert isinstance(message, ToolMessage)
    assert message.tool_call_id == "c1"
    assert message.name == "calculator"
    assert message.content == "14"
    assert tool.calls == [{"expression": "2+3*4"}]


def test_multiple_calls_are_all_executed_in_order(monkeypatch):
    first = _FakeTool(result="a")
    second = _FakeTool(result="b")
    _patch_registry(monkeypatch, {"one": first, "two": second})
    state = {
        "messages": [
            _ai_message(
                _tool_call("one", {}, "c1"),
                _tool_call("two", {}, "c2"),
            )
        ]
    }

    result = tool_node(state)["messages"]

    assert [m.tool_call_id for m in result] == ["c1", "c2"]
    assert [m.content for m in result] == ["a", "b"]


def test_list_result_is_json_stringified(monkeypatch):
    tool = _FakeTool(result=[{"title": "t", "url": "u"}])
    _patch_registry(monkeypatch, {"search": tool})
    state = {"messages": [_ai_message(_tool_call("search", {"query": "q"}, "c1"))]}

    message = tool_node(state)["messages"][0]

    assert isinstance(message.content, str)
    assert json.loads(message.content) == [{"title": "t", "url": "u"}]


def test_string_result_is_preserved_verbatim(monkeypatch):
    tool = _FakeTool(result="plain text")
    _patch_registry(monkeypatch, {"search": tool})
    state = {"messages": [_ai_message(_tool_call("search", {}, "c1"))]}

    assert tool_node(state)["messages"][0].content == "plain text"


def test_unknown_tool_becomes_an_error_message_and_keeps_the_id(monkeypatch):
    _patch_registry(monkeypatch, {})
    state = {"messages": [_ai_message(_tool_call("mystery", {}, "c1"))]}

    message = tool_node(state)["messages"][0]

    assert isinstance(message, ToolMessage)
    assert message.tool_call_id == "c1"
    assert message.content.startswith("Error:")
    assert "mystery" in message.content


def test_malformed_arguments_become_an_error_message(monkeypatch):
    tool = _FakeTool(result="ok")
    _patch_registry(monkeypatch, {"echo": tool})

    # AIMessage validates that args is a dict, so build a valid message and
    # inject the malformed call the way a broken provider might.
    message = AIMessage(content="")
    message.tool_calls = [{"name": "echo", "args": "not-an-object", "id": "c1"}]
    result = tool_node({"messages": [message]})["messages"][0]

    assert result.content.startswith("Error:")
    assert tool.calls == []


def test_tool_failure_is_captured_rather_than_raised(monkeypatch):
    tool = _FakeTool(error=RuntimeError("boom"))
    _patch_registry(monkeypatch, {"echo": tool})
    state = {"messages": [_ai_message(_tool_call("echo", {}, "c1"))]}

    message = tool_node(state)["messages"][0]

    assert message.content.startswith("Error:")
    assert "boom" in message.content
