"""Offline end-to-end test of the complete reflection workflow.

Every external dependency is mocked: the responder and revisor chains, and the
Tavily search tool. The real LangGraph structure, the real ``execute_tools``
node, and the real ``event_loop`` router all run.
"""

import json
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import deep_research_agent.execute_tools as execute_tools_module
from deep_research_agent import graph, responder, revisor
from deep_research_agent.event_loop import MAX_ITERATIONS


class _FakeRunnable:
    def __init__(self, func):
        self._func = func

    def invoke(self, inputs, config=None, **kwargs):
        return self._func(inputs)


def _tool_call(name, answer, queries, tool_id, references=None):
    args = {
        "answer": answer,
        "reflection": {"missing": "m", "superfluous": "s"},
        "search_queries": queries,
    }
    if references is not None:
        args["references"] = references
    return {"name": name, "args": args, "id": tool_id}


@pytest.fixture
def offline_workflow(monkeypatch):
    calls = {"respond": 0, "revise": 0, "tavily": [], "revise_inputs": []}

    def responder_factory():
        def run(_inputs):
            calls["respond"] += 1
            return AIMessage(
                content="",
                tool_calls=[
                    _tool_call(
                        "AnswerQuestion",
                        "initial draft",
                        ["query one", "query two"],
                        "respond-call",
                    )
                ],
            )

        return _FakeRunnable(run)

    def revisor_factory():
        def run(inputs):
            calls["revise"] += 1
            state = inputs.get("messages", inputs) if isinstance(inputs, dict) else inputs
            calls["revise_inputs"].append(state)
            return AIMessage(
                content="",
                tool_calls=[
                    _tool_call(
                        "ReviseAnswer",
                        f"revised answer {calls['revise']}",
                        ["follow-up query"],
                        f"revise-call-{calls['revise']}",
                        references=["[1] https://example.com"],
                    )
                ],
            )

        return _FakeRunnable(run)

    tavily = MagicMock()

    def tavily_invoke(query):
        calls["tavily"].append(query)
        return {"query": query, "results": [f"result for {query}"]}

    tavily.invoke.side_effect = tavily_invoke

    def forbidden_llm():
        raise AssertionError("the watsonx client must not be built in offline tests")

    monkeypatch.setattr(responder, "get_responder_chain", responder_factory)
    monkeypatch.setattr(revisor, "get_revisor_chain", revisor_factory)
    monkeypatch.setattr(responder, "get_llm", forbidden_llm)
    monkeypatch.setattr(revisor, "get_llm", forbidden_llm)
    monkeypatch.setattr(execute_tools_module, "tavily_tool", tavily)

    return calls


def test_end_to_end_runs_every_stage_in_order(offline_workflow):
    calls = offline_workflow

    messages = graph.app.invoke([HumanMessage(content="What should I eat?")])

    assert calls["respond"] == 1
    assert calls["revise"] == MAX_ITERATIONS
    assert calls["tavily"] == ["query one", "query two"] + ["follow-up query"] * (
        MAX_ITERATIONS - 1
    )

    answers = graph.extract_answers(messages)
    assert answers[0] == "initial draft"
    assert answers[-1] == f"revised answer {MAX_ITERATIONS}"
    assert len(answers) == MAX_ITERATIONS + 1


def test_research_results_reach_the_revision_stage(offline_workflow):
    calls = offline_workflow

    graph.app.invoke([HumanMessage(content="What should I eat?")])

    first_revision_state = calls["revise_inputs"][0]
    tool_messages = [m for m in first_revision_state if isinstance(m, ToolMessage)]
    assert tool_messages, "the revisor must see the accumulated research"

    payload = json.loads(tool_messages[0].content)
    assert payload["query one"] == {
        "query": "query one",
        "results": ["result for query one"],
    }


def test_workflow_terminates_with_a_tool_message_per_iteration(offline_workflow):
    messages = graph.app.invoke([HumanMessage(content="What should I eat?")])
    tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
    assert len(tool_messages) == MAX_ITERATIONS
