"""Verify all agents build their Watsonx clients from centralized settings."""

import pytest

import agents.relevance_checker as relevance_module
import agents.research_agent as research_module
import agents.verification_agent as verification_module
from agents.relevance_checker import RelevanceChecker
from agents.research_agent import ResearchAgent
from agents.verification_agent import VerificationAgent
from config.settings import settings


class _CapturingModelInference:
    instances = []

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        self.chat_calls = []
        _CapturingModelInference.instances.append(self)

    def chat(self, messages):  # pragma: no cover - not used here
        self.chat_calls.append(messages)
        raise AssertionError("Configuration tests must not call the model.")


@pytest.fixture
def capturing_watsonx(monkeypatch):
    _CapturingModelInference.instances = []

    for module in (research_module, verification_module, relevance_module):
        monkeypatch.setattr(module, "ModelInference", _CapturingModelInference)

    monkeypatch.setattr(settings, "WATSONX_API_KEY", "test-api-key")
    monkeypatch.setattr(settings, "WATSONX_PROJECT_ID", "test-project-id")
    monkeypatch.setattr(settings, "WATSONX_PROJECT_NAME", "test-project-name")
    monkeypatch.setattr(settings, "WATSONX_URL", "https://watsonx.example.invalid")
    monkeypatch.setattr(settings, "WATSONX_MODEL_ID", "ibm/test-model")

    return _CapturingModelInference


def test_all_agents_receive_the_centralized_watsonx_configuration(capturing_watsonx):
    ResearchAgent()
    VerificationAgent()
    RelevanceChecker()

    models = capturing_watsonx.instances
    assert len(models) == 3

    for model in models:
        kwargs = model.init_kwargs
        assert kwargs["model_id"] == "ibm/test-model"
        assert kwargs["credentials"] == {
            "url": "https://watsonx.example.invalid",
            "apikey": "test-api-key",
        }
        assert kwargs["project_id"] == "test-project-id"

    assert [model.init_kwargs["params"] for model in models] == [
        {"max_tokens": 300, "temperature": 0.3},
        {"max_tokens": 200, "temperature": 0.0},
        {"temperature": 0, "max_tokens": 10},
    ]


@pytest.mark.parametrize(
    "agent_class",
    [ResearchAgent, VerificationAgent, RelevanceChecker],
)
def test_agents_require_an_api_key_at_initialization(
    monkeypatch, capturing_watsonx, agent_class
):
    monkeypatch.setattr(settings, "WATSONX_API_KEY", None)

    with pytest.raises(ValueError, match="WATSONX_API_KEY"):
        agent_class()

    assert capturing_watsonx.instances == []
