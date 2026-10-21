"""Configuration, laziness and import-safety tests."""

import subprocess
import sys
from pathlib import Path

import pytest

from react_agent import llm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"

# Import the whole project inside a fresh interpreter where both the network and
# the watsonx client are booby-trapped. If any module authenticates, connects,
# or constructs the client at import time, the assertion fails.
_IMPORT_SAFETY_SCRIPT = r"""
import os, socket

for _key, _value in {
    "WATSONX_PROJECT_ID": "test-project-id",
    "WATSONX_URL": "https://eu-de.ml.cloud.ibm.com",
    "WATSONX_MODEL_ID": "ibm/granite-4-h-small",
    "WATSONX_API_KEY": "test-api-key",
    "TAVILY_API_KEY": "test-tavily-api-key",
}.items():
    os.environ.setdefault(_key, _value)

_original_socket = socket.socket


class _BlockedSocket(_original_socket):
    def connect(self, *args, **kwargs):
        raise AssertionError("network connection attempted during import")

    def connect_ex(self, *args, **kwargs):
        raise AssertionError("network connection attempted during import")


socket.socket = _BlockedSocket
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(
    AssertionError("network connection attempted during import")
)

import langchain_ibm


class _ForbiddenChatWatsonx:
    def __init__(self, *args, **kwargs):
        raise AssertionError("ChatWatsonx constructed during import")


langchain_ibm.ChatWatsonx = _ForbiddenChatWatsonx

from react_agent import (
    agent_state,
    call_model,
    graph,
    llm,
    model_react,
    prompt,
    should_continue,
    tool_execution,
)
from react_agent.tools import arithmetic, clothing, summarizer, web_search
from react_agent.tools import tools

assert graph.graph is not None
assert len(tools) == 4
print("IMPORT_OK")
"""


def test_missing_env_vars_produce_actionable_error(monkeypatch):
    for var in llm.REQUIRED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    llm.get_llm.cache_clear()

    with pytest.raises(OSError) as excinfo:
        llm.get_llm()

    message = str(excinfo.value)
    for var in llm.REQUIRED_ENV_VARS:
        assert var in message
    assert ".env.example" in message


def test_missing_env_vars_helper(monkeypatch):
    for var in llm.REQUIRED_ENV_VARS:
        monkeypatch.setenv(var, "set")
    assert llm.missing_env_vars() == []

    monkeypatch.delenv("WATSONX_MODEL_ID")
    assert llm.missing_env_vars() == ["WATSONX_MODEL_ID"]


def test_blank_env_var_counts_as_missing(monkeypatch):
    monkeypatch.setenv("WATSONX_API_KEY", "")
    assert "WATSONX_API_KEY" in llm.missing_env_vars()


def test_get_llm_builds_client_lazily_and_caches_it(monkeypatch):
    built = []

    class _FakeChatWatsonx:
        def __init__(self, **kwargs):
            built.append(kwargs)

    monkeypatch.setattr(llm, "ChatWatsonx", _FakeChatWatsonx)
    llm.get_llm.cache_clear()

    first = llm.get_llm()
    second = llm.get_llm()

    assert first is second
    assert len(built) == 1
    llm.get_llm.cache_clear()


def test_importing_core_modules_does_not_touch_network():
    env = dict(**__import__("os").environ)
    env["PYTHONPATH"] = str(SRC)

    result = subprocess.run(
        [sys.executable, "-c", _IMPORT_SAFETY_SCRIPT],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert "IMPORT_OK" in result.stdout
