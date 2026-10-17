import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

import responder
import revisor
from schema import AnswerQuestion, ReviseAnswer


class _FakeLLM:
    """Minimal stand-in for ``ChatWatsonx`` that records how it was bound."""

    def __init__(self, response):
        self.response = response
        self.bound_tools = None
        self.tool_choice = None
        self.received = None

    def _record(self, inputs):
        self.received = inputs
        return self.response

    def bind_tools(self, tools, tool_choice=None, **kwargs):
        self.bound_tools = tools
        self.tool_choice = tool_choice
        # Must be a real Runnable so it composes with the prompt via ``|``,
        # exactly like ``ChatWatsonx.bind_tools`` does in production.
        return RunnableLambda(self._record)


def _prime_responder(monkeypatch, response):
    fake = _FakeLLM(response)
    monkeypatch.setattr(responder, "get_llm", lambda: fake)
    responder.get_responder_chain.cache_clear()
    return fake


def _prime_revisor(monkeypatch, response):
    fake = _FakeLLM(response)
    monkeypatch.setattr(revisor, "get_llm", lambda: fake)
    revisor.get_revisor_chain.cache_clear()
    return fake


def _answer_message():
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "AnswerQuestion",
                "args": {
                    "answer": "draft",
                    "reflection": {"missing": "m", "superfluous": "s"},
                    "search_queries": ["q"],
                },
                "id": "call-1",
            }
        ],
    )


def test_responder_binds_the_answer_question_tool(monkeypatch):
    response = _answer_message()
    fake = _prime_responder(monkeypatch, response)

    out = responder.responder_chain.invoke(
        {"messages": [HumanMessage(content="healthy breakfast?")]}
    )

    assert fake.bound_tools == [AnswerQuestion]
    assert fake.tool_choice == "AnswerQuestion"
    assert out is response


def test_responder_prompt_receives_the_rendered_instructions_and_question(monkeypatch):
    fake = _prime_responder(monkeypatch, _answer_message())

    responder.responder_chain.invoke(
        {"messages": [HumanMessage(content="healthy breakfast?")]}
    )

    messages = fake.received.to_messages()
    human_messages = [message for message in messages if message.type == "human"]
    assert [message.content for message in human_messages] == ["healthy breakfast?"]
    rendered = "\n".join(message.content for message in messages)
    assert "Provide a detailed ~250 word answer" in rendered


def test_revisor_binds_the_revise_answer_tool(monkeypatch):
    response = AIMessage(content="", tool_calls=[])
    fake = _prime_revisor(monkeypatch, response)

    out = revisor.revisor_chain.invoke(
        [
            HumanMessage(content="healthy breakfast?"),
            _answer_message(),
        ]
    )

    assert fake.bound_tools == [ReviseAnswer]
    assert fake.tool_choice == "ReviseAnswer"
    assert out is response


def test_revisor_prompt_contains_the_revision_instructions(monkeypatch):
    fake = _prime_revisor(monkeypatch, AIMessage(content="", tool_calls=[]))

    revisor.revisor_chain.invoke([HumanMessage(content="q")])

    rendered = "\n".join(message.content for message in fake.received.to_messages())
    assert "Revise your previous answer using the new information" in rendered


def test_responder_chain_is_lazy_until_invoked(monkeypatch):
    build_calls = []

    def _explode():
        build_calls.append("built")
        raise AssertionError("chain must not be built at import time")

    responder.get_responder_chain.cache_clear()
    monkeypatch.setattr(responder, "get_llm", _explode)

    assert build_calls == []

    with pytest.raises(AssertionError):
        responder.responder_chain.invoke({"messages": [HumanMessage(content="q")]})

    assert build_calls == ["built"]
