"""M7.1: production model configuration resolves without silent fallback.

The scheduled job inherits almost no shell environment, so the model must
come from the committed template / local .env chain, never from an
interactive export. These tests pin the mechanism; the live resolution was
additionally verified with a stripped environment (see milestone report).
"""
import importlib

import pytest

import app.config as config
from tests.test_config import _reload_with


@pytest.fixture(autouse=True)
def restore_config():
    """Reload the real config after each test so env tweaks don't leak."""
    yield
    importlib.reload(config)


def test_env_override_selects_the_working_model(monkeypatch):
    """The known-working model wins whenever the environment names it —
    which is exactly what production .env does."""
    _reload_with(monkeypatch, GEMINI_MODEL_ID="gemini-3.5-flash-lite")

    assert config.GEMINI_MODEL_ID == "gemini-3.5-flash-lite"


def test_default_pin_is_stable_never_preview(monkeypatch):
    """Without an override the default must be a GA model, not a preview or
    experiment — unattended runs must never route to one silently."""
    _reload_with(monkeypatch)

    assert config.GEMINI_MODEL_ID == "gemini-3.6-flash"
    assert "-preview" not in config.GEMINI_MODEL_ID
    assert "-exp" not in config.GEMINI_MODEL_ID


def test_template_default_matches_code_default(monkeypatch):
    """The commented template pin and the code default cannot drift apart:
    uncommenting the template must reproduce production behavior."""
    from pathlib import Path

    _reload_with(monkeypatch)
    lines = (Path(config.__file__).resolve().parents[1] / ".env.example"
             ).read_text(encoding="utf-8").splitlines()
    pinned = [line.split("=", 1)[1].strip() for line in lines
              if line.strip().startswith("# GEMINI_MODEL_ID=")]
    assert pinned == [config.GEMINI_MODEL_ID]


def test_agent_reasoner_and_judge_follow_the_configured_model(monkeypatch):
    """Both live call sites default to the configured pin, not a hardcoded
    slug — changing the model is a config edit, never a code edit."""
    from app.agent.llm import LlmContentReasoner
    from app.verification.judge import LlmSupportJudge

    _reload_with(monkeypatch, GEMINI_MODEL_ID="gemini-3.5-flash-lite")

    assert LlmContentReasoner().model_id == "gemini-3.5-flash-lite"
    assert LlmSupportJudge()._model_id == "gemini-3.5-flash-lite"
