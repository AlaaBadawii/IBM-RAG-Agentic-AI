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


# --- Step 7: notification configuration --------------------------------------

def test_smtp_has_no_default_addresses():
    """The mechanism is decided; the addresses are the user's (PLAN.md §12.2 C).

    A hardcoded sender or recipient would be a value this repository chose for
    somebody else's mailbox, so the required settings start empty and the
    application runs without them.
    """
    assert config.SMTP_HOST == ""
    assert config.SMTP_SENDER == ""
    assert config.SMTP_RECIPIENT == ""
    assert config.SMTP_PASSWORD == ""


def test_smtp_defaults_are_bounded_and_encrypted():
    assert config.SMTP_PORT == 587
    assert config.SMTP_TLS == "starttls"
    assert config.SMTP_TIMEOUT_SECONDS == 30.0
    assert config.SMTP_REPEAT_AFTER_HOURS == 24.0


def test_smtp_settings_read_from_env(monkeypatch):
    _reload_with(
        monkeypatch,
        SMTP_HOST="smtp.gmail.com",
        SMTP_PORT="465",
        SMTP_SENDER="owner@example.com",
        SMTP_RECIPIENT="owner@example.com",
        SMTP_PASSWORD="app-password",
        SMTP_TLS="ssl",
    )
    assert config.SMTP_HOST == "smtp.gmail.com"
    assert config.SMTP_PORT == 465
    assert config.SMTP_SENDER == "owner@example.com"
    assert config.SMTP_PASSWORD == "app-password"
    assert config.SMTP_TLS == "ssl"


def test_an_unknown_tls_mode_is_a_configuration_error(monkeypatch):
    """A typo in TLS mode must not become a silently unencrypted connection."""
    with pytest.raises(ConfigError, match="SMTP_TLS"):
        _reload_with(monkeypatch, SMTP_TLS="STARTLS")
