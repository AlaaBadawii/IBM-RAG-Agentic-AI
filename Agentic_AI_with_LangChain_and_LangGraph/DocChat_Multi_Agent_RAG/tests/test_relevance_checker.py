"""Offline tests for ``RelevanceChecker`` and its Watsonx wiring.

``ModelInference`` is always replaced with a recording fake, so no API key,
network connection, or real model is required.
"""

import inspect
import os
import subprocess
import sys
from pathlib import Path

import pytest
from langchain_core.documents import Document

import agents.relevance_checker as relevance_module
import agents.research_agent as research_module
import agents.verification_agent as verification_module
import agents.workflow as workflow_module
from agents.relevance_checker import RelevanceChecker
from config.settings import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class RecordingModelInference:
    """Fake ``ModelInference`` that records constructor and ``chat`` calls."""

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        self.chat_calls = []
        self.response = {"choices": [{"message": {"content": "CAN_ANSWER"}}]}
        self.error = None

    def chat(self, messages):
        self.chat_calls.append(messages)
        if self.error is not None:
            raise self.error
        return self.response


@pytest.fixture
def configured_watsonx(monkeypatch):
    monkeypatch.setattr(settings, "WATSONX_API_KEY", "test-api-key")
    monkeypatch.setattr(settings, "WATSONX_PROJECT_ID", "test-project-id")
    monkeypatch.setattr(settings, "WATSONX_PROJECT_NAME", "test-project-name")
    monkeypatch.setattr(settings, "WATSONX_URL", "https://watsonx.example.invalid")
    monkeypatch.setattr(settings, "WATSONX_MODEL_ID", "ibm/test-model")


@pytest.fixture
def recorded_models(monkeypatch):
    models = []

    class CapturingModelInference(RecordingModelInference):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            models.append(self)

    monkeypatch.setattr(relevance_module, "ModelInference", CapturingModelInference)
    monkeypatch.setattr(research_module, "ModelInference", CapturingModelInference)
    monkeypatch.setattr(verification_module, "ModelInference", CapturingModelInference)
    return models


@pytest.fixture
def checker(configured_watsonx, recorded_models):
    return RelevanceChecker(), recorded_models[0]


def _documents(count=4):
    return [
        Document(
            page_content=f"Passage number {index}.",
            metadata={"source": f"doc-{index}.md"},
        )
        for index in range(count)
    ]


def test_checker_passes_configured_watsonx_values_to_model(
    configured_watsonx, recorded_models
):
    RelevanceChecker()

    assert len(recorded_models) == 1
    assert recorded_models[0].init_kwargs == {
        "model_id": "ibm/test-model",
        "credentials": {
            "url": "https://watsonx.example.invalid",
            "apikey": "test-api-key",
        },
        "project_id": "test-project-id",
        "params": {"temperature": 0, "max_tokens": 10},
    }


@pytest.mark.parametrize("api_key", [None, ""])
def test_missing_api_key_fails_when_checker_is_initialized(
    monkeypatch, recorded_models, api_key
):
    monkeypatch.setattr(settings, "WATSONX_API_KEY", api_key)

    with pytest.raises(ValueError, match="WATSONX_API_KEY"):
        RelevanceChecker()

    assert recorded_models == []


def test_check_uses_only_the_supplied_documents(checker):
    relevance, model = checker
    documents = _documents()

    result = relevance.check("What is passage number 1?", documents)

    assert result == "CAN_ANSWER"
    assert len(model.chat_calls) == 1

    messages = model.chat_calls[0]
    assert messages[0]["role"] == "user"
    prompt = messages[0]["content"]
    assert "What is passage number 1?" in prompt
    for document in documents[:3]:
        assert document.page_content in prompt
    assert documents[3].page_content not in prompt


def test_check_signature_has_no_retriever_argument():
    parameters = list(inspect.signature(RelevanceChecker.check).parameters)

    assert parameters == ["self", "question", "documents"]


def test_no_documents_returns_no_match_without_calling_the_model(checker):
    relevance, model = checker

    assert relevance.check("Any question?", []) == "NO_MATCH"
    assert model.chat_calls == []


@pytest.mark.parametrize(
    ("raw_response", "expected"),
    [
        ("CAN_ANSWER", "CAN_ANSWER"),
        ("can_answer", "CAN_ANSWER"),
        ("  PARTIAL \n", "PARTIAL"),
        ("`NO_MATCH`", "NO_MATCH"),
        ("No_Match.", "NO_MATCH"),
        ("**CAN_ANSWER**", "CAN_ANSWER"),
    ],
)
def test_valid_labels_are_parsed(checker, raw_response, expected):
    relevance, model = checker
    model.response = {"choices": [{"message": {"content": raw_response}}]}

    assert relevance.check("Question?", _documents()) == expected


@pytest.mark.parametrize(
    "raw_response",
    [
        "",
        "I think it is CAN_ANSWER",
        "CAN_ANSWER PARTIAL",
        "CAN_ANSWER\nPARTIAL",
        "PARTIALLY",
        "NO_MATCH?",
    ],
)
def test_malformed_labels_raise_value_error(checker, raw_response):
    relevance, model = checker
    model.response = {"choices": [{"message": {"content": raw_response}}]}

    with pytest.raises(ValueError, match="relevance classification"):
        relevance.check("Question?", _documents())


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": {}}]},
        ["not", "a", "mapping"],
    ],
)
def test_unexpected_response_structures_raise_value_error(checker, response):
    relevance, model = checker
    model.response = response

    with pytest.raises(ValueError, match="relevance classification"):
        relevance.check("Question?", _documents())


@pytest.mark.parametrize("content", [None, 42, ["CAN_ANSWER"]])
def test_non_text_content_raises_value_error(checker, content):
    relevance, model = checker
    model.response = {"choices": [{"message": {"content": content}}]}

    with pytest.raises(ValueError, match="non-text content"):
        relevance.check("Question?", _documents())


def test_inference_errors_are_not_converted_to_no_match(checker):
    relevance, model = checker
    model.error = RuntimeError("simulated inference failure")

    with pytest.raises(RuntimeError, match="simulated inference failure"):
        relevance.check("Question?", _documents())

    assert len(model.chat_calls) == 1


def test_workflow_passes_retrieved_documents_to_the_real_checker(
    configured_watsonx, recorded_models
):
    class SequencedRetriever:
        def __init__(self, documents):
            self.documents = documents
            self.calls = []

        def invoke(self, question):
            self.calls.append(question)
            return self.documents

    documents = _documents()
    retriever = SequencedRetriever(documents)

    # Construct the workflow so the checker exists, then set the response.
    workflow = workflow_module.AgentWorkflow()
    model = workflow.relevance_checker.model
    model.response = {"choices": [{"message": {"content": "NO_MATCH"}}]}

    result = workflow.full_pipeline("What is passage number 2?", retriever)

    assert result["status"] == "irrelevant"
    assert retriever.calls == ["What is passage number 2?"]
    assert len(model.chat_calls) == 1

    prompt = model.chat_calls[0][0]["content"]
    for document in documents[:3]:
        assert document.page_content in prompt


def test_importing_workflow_without_watsonx_credentials_succeeds(tmp_path):
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.upper().startswith("WATSONX_")
    }
    environment["PYTHONPATH"] = str(PROJECT_ROOT)

    completed = subprocess.run(
        [sys.executable, "-c", "import agents.workflow"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stderr
