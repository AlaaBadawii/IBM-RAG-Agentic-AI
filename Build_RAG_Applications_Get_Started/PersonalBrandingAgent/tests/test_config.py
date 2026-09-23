"""Tests for app.config: defaults, env overrides, lazy secret validation."""
import importlib

import pytest

import app.config as config
from app.errors import ConfigError

#: The settings Step 7 added. Named here so the reload helper can clear them:
#: what these tests assert are the *code's* defaults, and a real `.env` in the
#: working tree must not be able to change what that means.
SMTP_ENV_VARS = (
    "SMTP_HOST", "SMTP_PORT", "SMTP_SENDER", "SMTP_RECIPIENT",
    "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_TLS",
    "SMTP_TIMEOUT_SECONDS", "SMTP_REPEAT_AFTER_HOURS",
)


def _reload_with(monkeypatch, **env):
    # Patch inside the dotenv package: app.config re-executes
    # "from dotenv import load_dotenv" during importlib.reload, so patching
    # the app.config attribute would be overwritten. Patch the source module.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **kw: None)
    # Every variable these tests assert a *default* for has to be cleared
    # first, including the ones .env supplies: a default is a property of the
    # code, and a test that read the developer's local .env would start
    # asserting the developer's mailbox instead. app.config calls
    # load_dotenv(ENV_FILE) at import, which has already put .env into
    # os.environ by the time any test runs, so patching load_dotenv to a no-op
    # is not enough on its own.
    for key in (list(env.keys())
                + ["OPENAI_API_KEY", "OPENROUTER_API_KEY"]
                + list(SMTP_ENV_VARS)):
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

def test_smtp_has_no_default_addresses(monkeypatch):
    """The mechanism is decided; the addresses are the user's (PLAN.md §12.2 C).

    A hardcoded sender or recipient would be a value this repository chose for
    somebody else's mailbox, so the required settings start empty and the
    application runs without them. Asserted with the environment cleared, so
    the claim is about the code and not about whoever is running the tests.
    """
    _reload_with(monkeypatch)
    assert config.SMTP_HOST == ""
    assert config.SMTP_SENDER == ""
    assert config.SMTP_RECIPIENT == ""
    assert config.SMTP_PASSWORD == ""


def test_smtp_defaults_are_bounded_and_encrypted(monkeypatch):
    _reload_with(monkeypatch)
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


# --- OpenRouter provider configuration ---------------------------------------

#: Obviously fake, in the OpenRouter family. Never a real secret: the clients
#: below are constructed but never invoked, so no packet leaves the machine.
FAKE_OPENROUTER_KEY = "sk-or-v1-test-key-0000"


def _client_defaults():
    from app.agent.llm import _make_llm as agent_make_llm
    from app.generation.generator import _make_llm as generation_make_llm
    from app.verification.judge import _make_llm as judge_make_llm

    return {
        "agent reasoner": agent_make_llm,
        "generation": generation_make_llm,
        "support judge": judge_make_llm,
    }


def test_configured_key_reaches_the_openrouter_endpoint(monkeypatch):
    """Correctly configured: the key is sent to the OpenRouter provider.

    Every LLM boundary (Agent reasoner, generator, advisory judge) builds
    the same OpenAI-compatible client against OPENROUTER_BASE_URL. Building
    the client object opens nothing — this test pins the wiring, offline.
    """
    _reload_with(monkeypatch, OPENROUTER_API_KEY=FAKE_OPENROUTER_KEY)
    for name, make_llm in _client_defaults().items():
        client = make_llm("deepseek/deepseek-test", {"temperature": 0.0})
        assert client.openai_api_key.get_secret_value() == FAKE_OPENROUTER_KEY, name
        assert client.openai_api_base == "https://openrouter.ai/api/v1", name
        assert client.model_name == "deepseek/deepseek-test", name


def test_provider_mismatch_is_not_masked_in_code(monkeypatch):
    """Incorrectly configured: a non-OpenRouter endpoint is passed through.

    The code does not validate or rewrite the provider — an OpenAI-family
    key against the OpenRouter endpoint (or vice versa) fails at call time
    as an authentication error, classified downstream, never silently fixed
    up here.
    """
    _reload_with(monkeypatch, OPENROUTER_API_KEY=FAKE_OPENROUTER_KEY,
                 OPENROUTER_BASE_URL="https://api.openai.com/v1")
    for name, make_llm in _client_defaults().items():
        client = make_llm("deepseek/deepseek-test", {"temperature": 0.0})
        assert client.openai_api_base == "https://api.openai.com/v1", name
        assert client.openai_api_key.get_secret_value() == FAKE_OPENROUTER_KEY


def test_missing_key_names_the_openrouter_variable(monkeypatch):
    """Missing: the error names the expected variable, not the alias."""
    _reload_with(monkeypatch)
    with pytest.raises(ConfigError, match="OPENROUTER_API_KEY"):
        config.require_openrouter_key()


def test_env_example_names_the_openrouter_key():
    """The template must expect an OpenRouter key, unambiguously."""
    from pathlib import Path

    lines = (Path(config.__file__).resolve().parents[1] / ".env.example"
             ).read_text(encoding="utf-8").splitlines()
    values = {
        line.split("=", 1)[0].strip(): line.split("=", 1)[1].strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#") and "=" in line
    }
    assert "OPENROUTER_API_KEY" in values
    assert "YOUR" in values["OPENROUTER_API_KEY"]
    assert "sk-or-v1" in "\n".join(lines)
