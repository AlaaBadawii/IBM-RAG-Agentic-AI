"""Offline tests for the LangGraph ``AgentWorkflow``.

All agents and retrievers are deterministic stubs: no credentials, network,
or model calls are involved. The real agent classes only need to be
importable (their constructor must not require credentials).
"""

import pytest
from langchain_core.documents import Document
from langgraph.graph import StateGraph

import agents.relevance_checker as relevance_module
import agents.research_agent as research_module
import agents.verification_agent as verification_module
import agents.workflow as workflow_module
from agents.workflow import (
    IRRELEVANT_MESSAGE,
    UNVERIFIED_MESSAGE,
    AgentWorkflow,
)
from config.settings import settings


class _OfflineModelInference:
    """Constructor-only Watsonx stand-in for tests using the real checker."""

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs

    def chat(self, messages):  # pragma: no cover - defensive
        raise AssertionError("Workflow tests must not call the Watsonx API.")


@pytest.fixture(autouse=True)
def _offline_watsonx(monkeypatch):
    """Keep tests offline when the real ``RelevanceChecker`` is constructed."""

    monkeypatch.setattr(relevance_module, "ModelInference", _OfflineModelInference)
    monkeypatch.setattr(research_module, "ModelInference", _OfflineModelInference)
    monkeypatch.setattr(verification_module, "ModelInference", _OfflineModelInference)
    monkeypatch.setattr(settings, "WATSONX_API_KEY", "offline-test-key")
    monkeypatch.setattr(settings, "WATSONX_PROJECT_ID", "offline-test-project")
    monkeypatch.setattr(settings, "WATSONX_URL", "https://offline.invalid")
    monkeypatch.setattr(settings, "WATSONX_MODEL_ID", "ibm/offline-test-model")


def _documents():
    return [
        Document(page_content="Alpha content.", metadata={"source": "alpha.md"}),
        Document(page_content="Beta content.", metadata={"source": "beta.md"}),
    ]


VERIFIED_REPORT = "Supported: YES\nRelevant: YES"
UNSUPPORTED_REPORT = "Supported: NO\nRelevant: YES"
IRRELEVANT_REPORT = "Supported: YES\nRelevant: NO"


class StubRetriever:
    """Duck-typed retriever that records invocations."""

    def __init__(self, documents=None, error=None):
        self.documents = _documents() if documents is None else documents
        self.error = error
        self.calls = []

    def invoke(self, question):
        self.calls.append(question)
        if self.error is not None:
            raise self.error
        return self.documents


class StubRelevanceChecker:
    def __init__(self, classification="CAN_ANSWER"):
        self.classification = classification
        self.calls = []

    def check(self, question, documents):
        self.calls.append((question, documents))
        if isinstance(self.classification, BaseException):
            raise self.classification
        return self.classification


class StubResearchAgent:
    def __init__(self, drafts=None):
        self.results = (
            list(drafts) if drafts is not None else [{"draft_answer": "Draft answer."}]
        )
        self.calls = []

    def research(self, question, documents):
        self.calls.append((question, documents))
        result = self.results[min(len(self.calls) - 1, len(self.results) - 1)]
        if isinstance(result, BaseException):
            raise result
        return result


class StubVerificationAgent:
    def __init__(self, reports=None):
        self.results = (
            list(reports)
            if reports is not None
            else [{"verification_report": VERIFIED_REPORT}]
        )
        self.calls = []

    def verify(self, draft_answer, documents):
        self.calls.append((draft_answer, documents))
        result = self.results[min(len(self.calls) - 1, len(self.results) - 1)]
        if isinstance(result, BaseException):
            raise result
        return result


def build_workflow(
    monkeypatch,
    *,
    classification="CAN_ANSWER",
    drafts=None,
    reports=None,
    documents=None,
    max_attempts=3,
):
    """Construct a workflow wired to recording stubs."""

    relevance = StubRelevanceChecker(classification)
    research = StubResearchAgent(drafts)
    verification = StubVerificationAgent(reports)

    monkeypatch.setattr(workflow_module, "RelevanceChecker", lambda: relevance)
    monkeypatch.setattr(workflow_module, "ResearchAgent", lambda: research)
    monkeypatch.setattr(workflow_module, "VerificationAgent", lambda: verification)

    workflow = AgentWorkflow(max_research_attempts=max_attempts)
    retriever = StubRetriever(documents)

    return workflow, relevance, research, verification, retriever


# ---------------------------------------------------------------------------
# 1. Construction and one-time graph compilation
# ---------------------------------------------------------------------------


def test_constructor_initializes_components_and_compiles_graph_once(monkeypatch):
    compile_calls = []
    real_compile = StateGraph.compile

    def counting_compile(self, *args, **kwargs):
        compile_calls.append(1)
        return real_compile(self, *args, **kwargs)

    monkeypatch.setattr(StateGraph, "compile", counting_compile)

    workflow = AgentWorkflow()

    assert isinstance(workflow.researcher, workflow_module.ResearchAgent)
    assert isinstance(workflow.verifier, workflow_module.VerificationAgent)
    assert isinstance(workflow.relevance_checker, workflow_module.RelevanceChecker)
    assert workflow.researcher is not workflow.verifier
    assert workflow.compiled_workflow is not None
    assert len(compile_calls) == 1

    compiled = workflow.compiled_workflow
    retriever = StubRetriever(documents=[])
    first = workflow.full_pipeline("Any question?", retriever)
    second = workflow.full_pipeline("Another question?", retriever)

    assert first["status"] == "irrelevant"
    assert second["status"] == "irrelevant"
    assert workflow.compiled_workflow is compiled
    assert len(compile_calls) == 1


@pytest.mark.parametrize("value", [0, -1, True, "3", 2.0, None])
def test_invalid_max_research_attempts_rejected(value):
    with pytest.raises(ValueError, match="positive integer"):
        AgentWorkflow(max_research_attempts=value)


# ---------------------------------------------------------------------------
# 2. Relevance branches and rejection without downstream calls
# ---------------------------------------------------------------------------


def test_can_answer_proceeds_to_research_and_verification(monkeypatch):
    workflow, relevance, research, verification, retriever = build_workflow(
        monkeypatch, classification="CAN_ANSWER"
    )

    result = workflow.full_pipeline("What is alpha?", retriever)

    assert result["status"] == "verified"
    assert result["draft_answer"] == "Draft answer."
    assert result["verification_report"] == VERIFIED_REPORT
    assert len(relevance.calls) == 1
    assert len(research.calls) == 1
    assert len(verification.calls) == 1


def test_partial_relevance_proceeds(monkeypatch):
    workflow, relevance, research, verification, retriever = build_workflow(
        monkeypatch, classification="PARTIAL"
    )

    result = workflow.full_pipeline("What is alpha?", retriever)

    assert result["status"] == "verified"
    assert len(research.calls) == 1
    assert len(verification.calls) == 1


def test_no_match_rejects_without_research_or_verification(monkeypatch):
    workflow, relevance, research, verification, retriever = build_workflow(
        monkeypatch, classification="NO_MATCH"
    )

    result = workflow.full_pipeline("Unrelated question?", retriever)

    assert result["status"] == "irrelevant"
    assert result["draft_answer"] == IRRELEVANT_MESSAGE
    assert result["verification_report"]
    assert research.calls == []
    assert verification.calls == []
    assert len(relevance.calls) == 1
    assert len(retriever.calls) == 1


def test_no_documents_rejects_without_calling_checker(monkeypatch):
    workflow, relevance, research, verification, retriever = build_workflow(
        monkeypatch, documents=[]
    )

    result = workflow.full_pipeline("Anything?", retriever)

    assert result["status"] == "irrelevant"
    assert relevance.calls == []
    assert research.calls == []
    assert verification.calls == []


def test_unexpected_relevance_classification_raises(monkeypatch):
    workflow, relevance, research, verification, retriever = build_workflow(
        monkeypatch, classification="PROBABLY"
    )

    with pytest.raises(ValueError, match="unexpected classification"):
        workflow.full_pipeline("What is alpha?", retriever)

    assert research.calls == []
    assert verification.calls == []


@pytest.mark.parametrize("classification", [None, "", "can_answer ", 3])
def test_missing_or_invalid_classification_raises(monkeypatch, classification):
    workflow, _, research, _, retriever = build_workflow(
        monkeypatch, classification=classification
    )

    with pytest.raises(ValueError, match="unexpected classification"):
        workflow.full_pipeline("What is alpha?", retriever)

    assert research.calls == []


# ---------------------------------------------------------------------------
# 3. Retrieval ownership
# ---------------------------------------------------------------------------


def test_retrieval_happens_once_and_documents_are_shared(monkeypatch):
    documents = _documents()
    workflow, relevance, research, verification, retriever = build_workflow(
        monkeypatch, documents=documents
    )

    result = workflow.full_pipeline("  What is alpha?  ", retriever)

    assert result["status"] == "verified"
    assert retriever.calls == ["What is alpha?"]
    assert len(retriever.calls) == 1

    assert relevance.calls[0][0] == "What is alpha?"
    assert relevance.calls[0][1] is documents
    assert research.calls[0][1] is documents
    assert verification.calls[0][1] is documents
    assert [d.metadata["source"] for d in research.calls[0][1]] == [
        "alpha.md",
        "beta.md",
    ]


def test_retrieval_is_not_repeated_across_research_retries(monkeypatch):
    workflow, _, research, _, retriever = build_workflow(
        monkeypatch,
        max_attempts=3,
        drafts=[{"draft_answer": "v1"}, {"draft_answer": "v2"}, {"draft_answer": "v3"}],
        reports=[
            {"verification_report": UNSUPPORTED_REPORT},
            {"verification_report": UNSUPPORTED_REPORT},
            {"verification_report": UNSUPPORTED_REPORT},
        ],
    )

    result = workflow.full_pipeline("What is alpha?", retriever)

    assert result["status"] == "unverified"
    assert len(retriever.calls) == 1
    assert len(research.calls) == 3
    assert research.calls[0][1] is research.calls[1][1] is research.calls[2][1]


# ---------------------------------------------------------------------------
# 4. Success and retry behavior
# ---------------------------------------------------------------------------


def test_verified_first_attempt(monkeypatch):
    workflow, _, research, verification, retriever = build_workflow(
        monkeypatch,
        drafts=[{"draft_answer": "Alpha is A."}],
        reports=[{"verification_report": VERIFIED_REPORT}],
    )

    result = workflow.full_pipeline("What is alpha?", retriever)

    assert result == {
        "draft_answer": "Alpha is A.",
        "verification_report": VERIFIED_REPORT,
        "status": "verified",
    }
    assert len(research.calls) == 1
    assert verification.calls[0][0] == "Alpha is A."


def test_retry_after_failed_verification_then_success(monkeypatch):
    workflow, _, research, verification, retriever = build_workflow(
        monkeypatch,
        drafts=[{"draft_answer": "first draft"}, {"draft_answer": "second draft"}],
        reports=[
            {"verification_report": UNSUPPORTED_REPORT},
            {"verification_report": VERIFIED_REPORT},
        ],
    )

    result = workflow.full_pipeline("What is alpha?", retriever)

    assert result["status"] == "verified"
    assert result["draft_answer"] == "second draft"
    assert result["verification_report"] == VERIFIED_REPORT
    assert len(research.calls) == 2
    assert len(verification.calls) == 2
    assert verification.calls[1][0] == "second draft"
    # Documented limitation: no feedback argument, so retries reuse inputs.
    assert research.calls[0] == research.calls[1]


def test_repeated_failures_end_unverified_without_claiming_success(monkeypatch):
    drafts = [
        {"draft_answer": "v1"},
        {"draft_answer": "v2"},
        {"draft_answer": "v3"},
    ]
    workflow, _, research, verification, retriever = build_workflow(
        monkeypatch,
        max_attempts=3,
        drafts=drafts,
        reports=[{"verification_report": UNSUPPORTED_REPORT}],
    )

    result = workflow.full_pipeline("What is alpha?", retriever)

    assert result["status"] == "unverified"
    assert result["draft_answer"] == UNVERIFIED_MESSAGE
    assert result["draft_answer"] not in {"v1", "v2", "v3"}
    assert result["verification_report"] == UNSUPPORTED_REPORT
    assert len(research.calls) == 3
    assert len(verification.calls) == 3


@pytest.mark.parametrize("max_attempts", [1, 2, 5])
def test_retry_limit_boundary(monkeypatch, max_attempts):
    workflow, _, research, verification, retriever = build_workflow(
        monkeypatch,
        max_attempts=max_attempts,
        drafts=[{"draft_answer": "draft"}],
        reports=[{"verification_report": UNSUPPORTED_REPORT}],
    )

    result = workflow.full_pipeline("What is alpha?", retriever)

    assert result["status"] == "unverified"
    assert len(research.calls) == max_attempts
    assert len(verification.calls) == max_attempts


def test_many_attempts_do_not_trip_langgraph_recursion_limit(monkeypatch):
    workflow, _, research, _, retriever = build_workflow(
        monkeypatch,
        max_attempts=20,
        drafts=[{"draft_answer": "draft"}],
        reports=[{"verification_report": UNSUPPORTED_REPORT}],
    )

    result = workflow.full_pipeline("What is alpha?", retriever)

    assert result["status"] == "unverified"
    assert len(research.calls) == 20


# ---------------------------------------------------------------------------
# 5. Verification report parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("report", "expected_status"),
    [
        (VERIFIED_REPORT, "verified"),
        ("supported: yes\nrelevant: yes", "verified"),
        ("  Supported : YES  \n\tRelevant: YES.", "verified"),
        ("Supported: YES\nRelevant: YES\nExplanation: grounded.", "verified"),
        (UNSUPPORTED_REPORT, "unverified"),
        (IRRELEVANT_REPORT, "unverified"),
        ("Supported: NO\nRelevant: NO", "unverified"),
        ("Relevant: YES", "unverified"),
        ("Supported: YES", "unverified"),
        ("Everything looks fine.", "unverified"),
        ("Supported: MAYBE\nRelevant: YES", "unverified"),
        (
            "Supported: YES\nSupported: NO\nRelevant: YES",
            "unverified",
        ),
    ],
)
def test_verification_report_parsing(monkeypatch, report, expected_status):
    workflow, _, _, _, retriever = build_workflow(
        monkeypatch,
        max_attempts=1,
        drafts=[{"draft_answer": "draft"}],
        reports=[{"verification_report": report}],
    )

    result = workflow.full_pipeline("What is alpha?", retriever)

    assert result["status"] == expected_status
    assert result["verification_report"] == report


def test_malformed_report_never_verifies_even_with_yes_substrings(monkeypatch):
    workflow, _, _, _, retriever = build_workflow(
        monkeypatch,
        max_attempts=1,
        drafts=[{"draft_answer": "draft"}],
        reports=[
            {
                "verification_report": (
                    "The answer says Supported: YES but is not Relevant: YES"
                )
            }
        ],
    )

    result = workflow.full_pipeline("What is alpha?", retriever)

    assert result["status"] == "unverified"


# ---------------------------------------------------------------------------
# 6. Malformed / missing agent results
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("draft", "error"),
    [
        (None, TypeError),
        ({}, ValueError),
        ({"draft_answer": None}, ValueError),
        ({"draft_answer": "   "}, ValueError),
        ({"draft_answer": 42}, ValueError),
    ],
)
def test_invalid_research_results_raise(monkeypatch, draft, error):
    workflow, _, _, _, retriever = build_workflow(
        monkeypatch,
        drafts=[draft],
    )

    with pytest.raises(error):
        workflow.full_pipeline("What is alpha?", retriever)


@pytest.mark.parametrize(
    ("result", "error"),
    [
        (None, TypeError),
        ({}, ValueError),
        ({"verification_report": None}, ValueError),
        ({"verification_report": "   "}, ValueError),
        ({"verification_report": 7}, ValueError),
    ],
)
def test_invalid_verification_results_raise(monkeypatch, result, error):
    workflow, _, _, _, retriever = build_workflow(
        monkeypatch,
        reports=[result],
    )

    with pytest.raises(error):
        workflow.full_pipeline("What is alpha?", retriever)


# ---------------------------------------------------------------------------
# 7. Execution failures stay visible
# ---------------------------------------------------------------------------


def test_retrieval_exception_propagates(monkeypatch):
    workflow, _, research, _, retriever = build_workflow(monkeypatch)
    retriever.error = RuntimeError("vector store unavailable")

    with pytest.raises(RuntimeError, match="vector store unavailable"):
        workflow.full_pipeline("What is alpha?", retriever)

    assert research.calls == []


def test_relevance_exception_propagates(monkeypatch):
    workflow, _, research, _, retriever = build_workflow(
        monkeypatch,
        classification=RuntimeError("classifier unavailable"),
    )

    with pytest.raises(RuntimeError, match="classifier unavailable"):
        workflow.full_pipeline("What is alpha?", retriever)

    assert research.calls == []


def test_research_exception_propagates(monkeypatch):
    workflow, _, _, verification, retriever = build_workflow(
        monkeypatch,
        drafts=[RuntimeError("research failed")],
    )

    with pytest.raises(RuntimeError, match="research failed"):
        workflow.full_pipeline("What is alpha?", retriever)

    assert verification.calls == []


def test_verification_exception_propagates(monkeypatch):
    workflow, _, _, _, retriever = build_workflow(
        monkeypatch,
        reports=[RuntimeError("verifier failed")],
    )

    with pytest.raises(RuntimeError, match="verifier failed"):
        workflow.full_pipeline("What is alpha?", retriever)


# ---------------------------------------------------------------------------
# 8. Consistent result shape / input validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("classification", "reports", "max_attempts", "expected_status"),
    [
        ("NO_MATCH", None, 3, "irrelevant"),
        ("CAN_ANSWER", None, 3, "verified"),
        (
            "CAN_ANSWER",
            [{"verification_report": UNSUPPORTED_REPORT}],
            1,
            "unverified",
        ),
    ],
)
def test_all_normal_exits_return_consistent_keys(
    monkeypatch, classification, reports, max_attempts, expected_status
):
    workflow, _, _, _, retriever = build_workflow(
        monkeypatch,
        classification=classification,
        reports=reports,
        max_attempts=max_attempts,
    )

    result = workflow.full_pipeline("What is alpha?", retriever)

    assert set(result) == {"draft_answer", "verification_report", "status"}
    assert result["status"] == expected_status
    assert isinstance(result["draft_answer"], str) and result["draft_answer"]
    assert isinstance(result["verification_report"], str)
    assert result["verification_report"]


@pytest.mark.parametrize("question", ["", "   ", "\n\t", None, 42])
def test_invalid_question_rejected_before_retrieval(question):
    workflow = AgentWorkflow()
    retriever = StubRetriever()

    with pytest.raises(ValueError, match="non-empty string"):
        workflow.full_pipeline(question, retriever)

    assert retriever.calls == []
