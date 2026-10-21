"""End-to-end workflow tests using the real agent classes with fake models.

Only ``ModelInference`` and the retriever are replaced. The real
``RelevanceChecker``, ``ResearchAgent``, ``VerificationAgent``, prompts, and
parsers participate, so these tests can detect interface mismatches between
the workflow and the agents.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from langchain_core.documents import Document

import agents.relevance_checker as relevance_module
import agents.research_agent as research_module
import agents.verification_agent as verification_module
from agents.workflow import (
    IRRELEVANT_MESSAGE,
    UNVERIFIED_MESSAGE,
    AgentWorkflow,
)
from config.settings import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent

VERIFIED_REPORT = (
    "Supported: YES\n"
    "Unsupported Claims: None\n"
    "Contradictions: None\n"
    "Relevant: YES\n"
    "Additional Details: The answer is grounded in the documents."
)
UNSUPPORTED_REPORT = (
    "Supported: NO\n"
    "Unsupported Claims: Alpha is the last letter.\n"
    "Contradictions: None\n"
    "Relevant: YES\n"
    "Additional Details: The draft contradicts the documents."
)
IRRELEVANT_REPORT = (
    "Supported: YES\n"
    "Unsupported Claims: None\n"
    "Contradictions: None\n"
    "Relevant: NO\n"
    "Additional Details: The answer does not address the question."
)


class _InertModelInference:
    """Constructor-only stand-in used until a test installs a scripted model."""

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs

    def chat(self, messages):  # pragma: no cover - defensive
        raise AssertionError("A model was called without a scripted response.")


class ScriptedModel:
    """Deterministic chat model that returns responses in order."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)

        assert self.responses, "Unexpected extra model call."

        item = self.responses.pop(0)

        if isinstance(item, BaseException):
            raise item

        return item


def _chat(content):
    return {"choices": [{"message": {"content": content}}]}


def _documents():
    return [
        Document(
            page_content="Alpha is the first letter of the Greek alphabet.",
            metadata={"source": "alpha.md", "page": 1},
        ),
        Document(
            page_content="Beta is the second letter of the Greek alphabet.",
            metadata={"source": "beta.md", "page": 2},
        ),
    ]


class FakeRetriever:
    def __init__(self, documents=None, error=None):
        self.documents = _documents() if documents is None else documents
        self.error = error
        self.calls = []

    def invoke(self, question):
        self.calls.append(question)

        if self.error is not None:
            raise self.error

        return self.documents


@pytest.fixture
def offline_agents(monkeypatch):
    for module in (research_module, verification_module, relevance_module):
        monkeypatch.setattr(module, "ModelInference", _InertModelInference)

    monkeypatch.setattr(settings, "WATSONX_API_KEY", "offline-test-key")
    monkeypatch.setattr(settings, "WATSONX_PROJECT_ID", "offline-test-project")
    monkeypatch.setattr(settings, "WATSONX_URL", "https://offline.invalid")
    monkeypatch.setattr(settings, "WATSONX_MODEL_ID", "ibm/offline-test-model")


def build_workflow(
    *,
    relevance="CAN_ANSWER",
    research=("Draft answer.",),
    verification=(VERIFIED_REPORT,),
    max_attempts=3,
):
    workflow = AgentWorkflow(max_research_attempts=max_attempts)
    workflow.relevance_checker.model = ScriptedModel([_chat(relevance)])
    workflow.researcher.model = ScriptedModel([_chat(text) for text in research])
    workflow.verifier.model = ScriptedModel([_chat(report) for report in verification])
    return workflow


def test_relevant_question_is_verified_end_to_end(offline_agents):
    workflow = build_workflow(research=("Alpha is the first letter.",))
    retriever = FakeRetriever()
    documents = retriever.documents
    seen = {}

    original_check = workflow.relevance_checker.check

    def check(question, documents):
        seen["relevance"] = documents
        return original_check(question=question, documents=documents)

    original_research = workflow.researcher.research

    def research(question, documents):
        seen["research"] = documents
        return original_research(question, documents)

    original_verify = workflow.verifier.verify

    def verify(answer, documents):
        seen["verification"] = documents
        return original_verify(answer, documents)

    workflow.relevance_checker.check = check
    workflow.researcher.research = research
    workflow.verifier.verify = verify

    result = workflow.full_pipeline("What is alpha?", retriever)

    assert result == {
        "draft_answer": "Alpha is the first letter.",
        "verification_report": VERIFIED_REPORT,
        "status": "verified",
    }
    assert retriever.calls == ["What is alpha?"]
    assert seen["relevance"] is documents
    assert seen["research"] is documents
    assert seen["verification"] is documents

    prompts = {
        "relevance": workflow.relevance_checker.model.calls[0][0]["content"],
        "research": workflow.researcher.model.calls[0][0]["content"],
        "verification": workflow.verifier.model.calls[0][0]["content"],
    }

    for prompt in prompts.values():
        for document in documents:
            assert document.page_content in prompt

    assert "Alpha is the first letter." in prompts["verification"]


def test_partial_relevance_proceeds_through_research(offline_agents):
    workflow = build_workflow(relevance="PARTIAL")

    result = workflow.full_pipeline("What is alpha?", FakeRetriever())

    assert result["status"] == "verified"
    assert len(workflow.researcher.model.calls) == 1
    assert len(workflow.verifier.model.calls) == 1


def test_no_match_stops_without_research_or_verification(offline_agents):
    workflow = build_workflow(relevance="NO_MATCH")

    result = workflow.full_pipeline("Unrelated question?", FakeRetriever())

    assert result["status"] == "irrelevant"
    assert result["draft_answer"] == IRRELEVANT_MESSAGE
    assert result["verification_report"]
    assert len(workflow.relevance_checker.model.calls) == 1
    assert workflow.researcher.model.calls == []
    assert workflow.verifier.model.calls == []


def test_empty_retrieval_is_irrelevant_without_model_calls(offline_agents):
    workflow = build_workflow()
    retriever = FakeRetriever(documents=[])

    result = workflow.full_pipeline("Unrelated question?", retriever)

    assert result["status"] == "irrelevant"
    assert result["draft_answer"] == IRRELEVANT_MESSAGE
    assert len(retriever.calls) == 1
    assert workflow.relevance_checker.model.calls == []
    assert workflow.researcher.model.calls == []
    assert workflow.verifier.model.calls == []


def test_retry_after_unsupported_answer_then_success(offline_agents):
    workflow = build_workflow(
        research=("First draft.", "Second draft."),
        verification=(UNSUPPORTED_REPORT, VERIFIED_REPORT),
    )
    retriever = FakeRetriever()

    result = workflow.full_pipeline("What is alpha?", retriever)

    assert result["status"] == "verified"
    assert result["draft_answer"] == "Second draft."
    assert result["verification_report"] == VERIFIED_REPORT
    assert len(retriever.calls) == 1
    assert len(workflow.researcher.model.calls) == 2
    assert len(workflow.verifier.model.calls) == 2

    # Documented limitation: no verifier feedback is passed to research, so
    # both attempts use the same question and evidence.
    first_prompt = workflow.researcher.model.calls[0][0]["content"]
    second_prompt = workflow.researcher.model.calls[1][0]["content"]
    assert first_prompt == second_prompt


def test_retry_exhaustion_returns_explicit_unverified_result(offline_agents):
    workflow = build_workflow(
        max_attempts=2,
        research=("First draft.", "Second draft."),
        verification=(UNSUPPORTED_REPORT, UNSUPPORTED_REPORT),
    )
    retriever = FakeRetriever()

    result = workflow.full_pipeline("What is alpha?", retriever)

    assert result["status"] == "unverified"
    assert result["draft_answer"] == UNVERIFIED_MESSAGE
    assert result["verification_report"] == UNSUPPORTED_REPORT
    assert len(retriever.calls) == 1
    assert len(workflow.researcher.model.calls) == 2
    assert len(workflow.verifier.model.calls) == 2


def test_retrieval_exception_propagates_without_model_calls(offline_agents):
    workflow = build_workflow()
    retriever = FakeRetriever(error=RuntimeError("vector store unavailable"))

    with pytest.raises(RuntimeError, match="vector store unavailable"):
        workflow.full_pipeline("What is alpha?", retriever)

    assert workflow.relevance_checker.model.calls == []


def test_relevance_model_exception_propagates(offline_agents):
    workflow = build_workflow()
    workflow.relevance_checker.model = ScriptedModel(
        [RuntimeError("classifier unavailable")]
    )

    with pytest.raises(RuntimeError, match="classifier unavailable"):
        workflow.full_pipeline("What is alpha?", FakeRetriever())

    assert workflow.researcher.model.calls == []
    assert workflow.verifier.model.calls == []


def test_research_model_exception_propagates(offline_agents):
    workflow = build_workflow()
    workflow.researcher.model = ScriptedModel([RuntimeError("generation unavailable")])

    with pytest.raises(RuntimeError, match="Failed to generate an answer"):
        workflow.full_pipeline("What is alpha?", FakeRetriever())

    assert workflow.verifier.model.calls == []


def test_verification_model_exception_propagates(offline_agents):
    workflow = build_workflow()
    workflow.verifier.model = ScriptedModel([RuntimeError("verifier unavailable")])

    with pytest.raises(RuntimeError, match="Failed to verify the draft answer"):
        workflow.full_pipeline("What is alpha?", FakeRetriever())


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {}}]},
        _chat(""),
        _chat("   "),
        _chat(None),
    ],
)
def test_invalid_research_model_responses_raise(offline_agents, response):
    workflow = build_workflow()
    workflow.researcher.model = ScriptedModel([response])

    with pytest.raises(ValueError):
        workflow.full_pipeline("What is alpha?", FakeRetriever())

    assert workflow.verifier.model.calls == []


@pytest.mark.parametrize(
    "report",
    [
        "Everything looks fine.",
        "Supported: YES",
        "Relevant: YES",
        "Supported: YES\nRelevant: MAYBE",
        "Supported: YES\nSupported: NO\nRelevant: YES",
    ],
)
def test_malformed_or_incomplete_verification_reports_never_verify(
    offline_agents, report
):
    workflow = build_workflow(
        max_attempts=1,
        verification=(report,),
    )

    with pytest.raises(ValueError):
        workflow.full_pipeline("What is alpha?", FakeRetriever())


def test_all_exits_return_consistent_result_shape(offline_agents):
    scenarios = [
        ("CAN_ANSWER", (VERIFIED_REPORT,), 3, "verified"),
        ("CAN_ANSWER", (UNSUPPORTED_REPORT, UNSUPPORTED_REPORT), 2, "unverified"),
        ("NO_MATCH", (VERIFIED_REPORT,), 3, "irrelevant"),
    ]

    for relevance, reports, max_attempts, expected_status in scenarios:
        drafts = tuple(f"Draft {index}." for index in range(max_attempts))
        workflow = build_workflow(
            relevance=relevance,
            research=drafts,
            verification=reports,
            max_attempts=max_attempts,
        )

        result = workflow.full_pipeline("What is alpha?", FakeRetriever())

        assert set(result) == {"draft_answer", "verification_report", "status"}
        assert result["status"] == expected_status
        assert isinstance(result["draft_answer"], str) and result["draft_answer"]
        assert isinstance(result["verification_report"], str)
        assert result["verification_report"]


def test_importing_app_and_workflow_offline_needs_no_credentials(tmp_path):
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.upper().startswith("WATSONX_")
    }
    environment["PYTHONPATH"] = str(PROJECT_ROOT)

    completed = subprocess.run(
        [sys.executable, "-c", "import app; import agents.workflow"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert completed.returncode == 0, completed.stderr
