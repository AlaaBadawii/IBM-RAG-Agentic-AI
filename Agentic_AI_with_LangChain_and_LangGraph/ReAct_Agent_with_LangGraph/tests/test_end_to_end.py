"""Offline end-to-end test of the complete ReAct cycle.

The chat model is scripted so no IBM watsonx.ai call is made, and the live
client is booby-trapped. Everything else -- the real graph, the real
``call_model`` node, the real ``tool_node`` executor, the real
``should_continue`` router, and the real calculator tool -- runs.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import react_agent.call_model as call_model_module
from react_agent import graph, llm


class _ScriptedModel:
    """A tiny fake LLM that returns a fixed list of responses in order."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def invoke(self, inputs):
        self.calls.append(inputs)
        return self._responses.pop(0)


def _tool_call(name, args, tool_id):
    return {"name": name, "args": args, "id": tool_id}


def _forbid_live_client(monkeypatch):
    def _forbidden(*args, **kwargs):
        raise AssertionError("a live watsonx client must not be built in tests")

    monkeypatch.setattr(llm, "ChatWatsonx", _forbidden)


def test_full_cycle_runs_tool_then_answers(monkeypatch):
    scripted = _ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    _tool_call("calculator", {"expression": "2 + 3 * 4"}, "call-1")
                ],
            ),
            AIMessage(content="The answer is 14."),
        ]
    )
    monkeypatch.setattr(call_model_module, "get_model_react", lambda: scripted)
    _forbid_live_client(monkeypatch)

    result = graph.graph.invoke(
        {"messages": [HumanMessage(content="What is 2 + 3 * 4?")]}
    )
    messages = result["messages"]

    assert len(messages) == 4
    assert isinstance(messages[0], HumanMessage)
    assert isinstance(messages[1], AIMessage)
    assert messages[1].tool_calls[0]["id"] == "call-1"

    assert isinstance(messages[2], ToolMessage)
    assert messages[2].tool_call_id == "call-1"
    assert messages[2].name == "calculator"
    assert messages[2].content == "14"

    assert messages[3].content == "The answer is 14."

    # The model was invoked twice and saw the tool result the second time.
    assert len(scripted.calls) == 2
    second_input = scripted.calls[1]["scratch_pad"]
    assert any(isinstance(message, ToolMessage) for message in second_input)


def test_unknown_tool_is_reported_to_the_model(monkeypatch):
    scripted = _ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[_tool_call("does_not_exist", {}, "call-9")],
            ),
            AIMessage(content="Sorry, that tool is unavailable."),
        ]
    )
    monkeypatch.setattr(call_model_module, "get_model_react", lambda: scripted)
    _forbid_live_client(monkeypatch)

    result = graph.graph.invoke({"messages": [HumanMessage(content="do it")]})
    messages = result["messages"]

    tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].tool_call_id == "call-9"
    assert tool_messages[0].content.startswith("Error:")
    assert "does_not_exist" in tool_messages[0].content
    assert messages[-1].content == "Sorry, that tool is unavailable."


def test_iteration_limit_stops_a_stuck_agent(monkeypatch):
    monkeypatch.setenv("REACT_MAX_ITERATIONS", "2")
    scripted = _ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[_tool_call("calculator", {"expression": "1 + 1"}, "c1")],
            ),
            AIMessage(
                content="",
                tool_calls=[_tool_call("calculator", {"expression": "1 + 1"}, "c2")],
            ),
            AIMessage(
                content="",
                tool_calls=[_tool_call("calculator", {"expression": "1 + 1"}, "c3")],
            ),
        ]
    )
    monkeypatch.setattr(call_model_module, "get_model_react", lambda: scripted)
    _forbid_live_client(monkeypatch)

    result = graph.graph.invoke({"messages": [HumanMessage(content="loop")]})

    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 2
    assert len(scripted.calls) == 3
