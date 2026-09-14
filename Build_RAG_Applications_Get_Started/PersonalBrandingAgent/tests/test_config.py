"""Tests for app.config: defaults, env overrides, lazy secret validation."""
import importlib

import pytest

import app.config as config
from app.errors import ConfigError


def _reload_with(monkeypatch, **env):
    # Patch inside the dotenv package: app.config re-executes
    # "from dotenv import load_dotenv" during importlib.reload, so patching
    # the app.config attribute would be overwritten. Patch the source module.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **kw: None)
    for key in list(env.keys()) + ["OPENAI_API_KEY", "OPENROUTER_API_KEY"]:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return importlib.reload(config)


@pytest.fixture(autouse=True)
def restore_config():
    """Reload the real config after each test so env tweaks don't leak."""
    yield
    importlib.reload(config)


def test_defaults():
    assert config.CHUNK_SIZE == 1000
    assert config.CHUNK_OVERLAP == 200
    assert config.TOP_K == 5
    assert config.RRF_K == 60
    assert config.EXCLUDE_READMES is True
    assert config.EMBEDDING_MODEL == "sentence-transformers/all-MiniLM-L6-v2"
    assert config.OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1"


def test_env_overrides(monkeypatch):
    _reload_with(monkeypatch, CHUNK_SIZE="500", TOP_K="3", RRF_K="10")
    assert config.CHUNK_SIZE == 500
    assert config.TOP_K == 3
    assert config.RRF_K == 10


def test_openrouter_key_reads_openai_api_key(monkeypatch):
    _reload_with(monkeypatch, OPENAI_API_KEY="sk-or-v1-test-key")
    assert config.OPENROUTER_API_KEY == "sk-or-v1-test-key"


def test_openrouter_key_prefers_dedicated_var(monkeypatch):
    _reload_with(
        monkeypatch,
        OPENAI_API_KEY="sk-or-v1-compat",
        OPENROUTER_API_KEY="sk-or-v1-dedicated",
    )
    assert config.OPENROUTER_API_KEY == "sk-or-v1-dedicated"


def test_require_openrouter_key_raises_when_missing(monkeypatch):
    _reload_with(monkeypatch)
    assert config.OPENROUTER_API_KEY is None
    with pytest.raises(ConfigError, match="OpenRouter"):
        config.require_openrouter_key()


def test_require_openrouter_key_returns_key_when_present(monkeypatch):
    _reload_with(monkeypatch, OPENAI_API_KEY="sk-or-v1-test-key")
    assert config.require_openrouter_key() == "sk-or-v1-test-key"


def test_generation_params_use_openai_compatible_names():
    """Watsonx-style max_new_tokens must NOT appear in OpenRouter config."""
    assert "max_tokens" in config.GENERATION_PARAMS
    assert "max_new_tokens" not in config.GENERATION_PARAMS
