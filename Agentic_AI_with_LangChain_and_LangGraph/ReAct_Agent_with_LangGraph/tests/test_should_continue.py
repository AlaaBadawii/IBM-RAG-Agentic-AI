"""Termination logic of the conditional edge."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from react_agent.should_continue import (
    DEFAULT_MAX_ITERATIONS,
    _max_iterations,
    should_continue,
)


def _answer():
    return AIMessage(content="the answer")


def _tool_call_message():
    return AIMessage(
        content="",
        tool_calls=[{"name": "calculator", "args": {"expression": "1"}, "id": "c"}],
    )


def _tool_result():
    return ToolMessage(content="1", tool_call_id="c")


def test_returns_end_when_the_model_answers():
    state = {"messages": [HumanMessage(content="q"), _answer()]}
    assert should_continue(state) == "end"


def test_returns_continue_when_the_model_requests_tools():
    state = {"messages": [HumanMessage(content="q"), _tool_call_message()]}
    assert should_continue(state) == "continue"


def test_returns_end_once_the_round_limit_is_reached(monkeypatch):
    monkeypatch.setenv("REACT_MAX_ITERATIONS", "2")
    state = {
        "messages": [
            HumanMessage(content="q"),
            _tool_call_message(),
            _tool_result(),
            _tool_call_message(),
            _tool_result(),
            _tool_call_message(),
        ]
    }
    assert should_continue(state) == "end"


def test_continues_below_the_round_limit(monkeypatch):
    monkeypatch.setenv("REACT_MAX_ITERATIONS", "2")
    state = {
        "messages": [
            HumanMessage(content="q"),
            _tool_call_message(),
            _tool_result(),
            _tool_call_message(),
        ]
    }
    assert should_continue(state) == "continue"


def test_invalid_or_missing_limit_falls_back_to_the_default(monkeypatch):
    monkeypatch.delenv("REACT_MAX_ITERATIONS", raising=False)
    assert _max_iterations() == DEFAULT_MAX_ITERATIONS

    monkeypatch.setenv("REACT_MAX_ITERATIONS", "not-a-number")
    assert _max_iterations() == DEFAULT_MAX_ITERATIONS

    monkeypatch.setenv("REACT_MAX_ITERATIONS", "0")
    assert _max_iterations() == DEFAULT_MAX_ITERATIONS
