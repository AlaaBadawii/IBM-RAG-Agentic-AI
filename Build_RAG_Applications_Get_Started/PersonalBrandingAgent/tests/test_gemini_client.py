"""Tests for app.gemini: the retry boundary around the pinned model.

Everything here is offline: the SDK client is replaced with a scripted
stand-in, and sleeps are recorded, never taken. What is pinned is the
policy — 503s get chances, 4xx errors do not, and the total number of
chances is bounded.
"""
import pytest

from google.genai import errors

from app import config
from app.gemini import (
    MAX_ATTEMPTS,
    RETRY_BACKOFF_SECONDS,
    GeminiJsonClient,
)

SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
}


def _503():
    return errors.ServerError(503, {"error": {"status": "UNAVAILABLE"}})


def _400():
    return errors.ClientError(400, {"error": {"status": "INVALID_ARGUMENT"}})


class _ScriptedModels:
    """generate_content with a script: exceptions raise, strings answer."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        outcome = self.script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome

        class _Response:
            text = outcome

        return _Response()


class _ScriptedClient:
    """genai.Client stand-in: records the key, serves the script."""

    instance = None

    def __init__(self, script, *, api_key=None):
        self.api_key = api_key
        self.models = _ScriptedModels(script)
        _ScriptedClient.instance = self


@pytest.fixture
def scripted(monkeypatch):
    """Install a scripted client; return (script_holder, sleeps)."""
    holder: dict = {}
    sleeps: list = []
    import time

    def factory(script):
        holder["script"] = script

        def make_client(*args, **kwargs):
            return _ScriptedClient(script, *args, **kwargs)

        monkeypatch.setattr("google.genai.Client", make_client)
        return holder

    monkeypatch.setattr(time, "sleep", sleeps.append)
    monkeypatch.setattr(config, "GOOGLE_API_KEY", "AIza-test-key")
    return factory, sleeps, holder


def _client():
    return GeminiJsonClient(
        model_id="gemini-test-model",
        max_output_tokens=7,
        response_schema=SCHEMA,
    )


def test_success_costs_one_call_and_no_sleep(scripted):
    factory, sleeps, holder = scripted
    factory(['{"ok": true}'])

    response = _client().invoke([{"role": "user", "content": "hi"}])

    assert response.content == '{"ok": true}'
    assert _ScriptedClient.instance.models.calls == 1
    assert sleeps == []


def test_two_sheds_then_success_uses_both_backoffs(scripted):
    factory, sleeps, holder = scripted
    factory([_503(), _503(), '{"ok": true}'])

    response = _client().invoke([{"role": "user", "content": "hi"}])

    assert response.content == '{"ok": true}'
    assert _ScriptedClient.instance.models.calls == 3
    assert sleeps == list(RETRY_BACKOFF_SECONDS)


def test_three_sheds_raise_the_last_one_closed(scripted):
    """Exhausted retries fail exactly as a single failure would: raised."""
    factory, sleeps, holder = scripted
    factory([_503(), _503(), _503()])

    with pytest.raises(errors.ServerError):
        _client().invoke([{"role": "user", "content": "hi"}])

    assert _ScriptedClient.instance.models.calls == MAX_ATTEMPTS
    assert sleeps == list(RETRY_BACKOFF_SECONDS)


def test_a_400_is_never_retried(scripted):
    """Bad auth, unknown model, rejected schema: retrying cannot fix them."""
    factory, sleeps, holder = scripted
    factory([_400()])

    with pytest.raises(errors.ClientError):
        _client().invoke([{"role": "user", "content": "hi"}])

    assert _ScriptedClient.instance.models.calls == 1
    assert sleeps == []


def test_missing_key_is_a_configuration_error_before_any_call(scripted,
                                                             monkeypatch):
    from app.errors import ConfigError

    factory, sleeps, holder = scripted
    factory(['{"ok": true}'])
    monkeypatch.setattr(config, "GOOGLE_API_KEY", "")

    with pytest.raises(ConfigError, match="GOOGLE_API_KEY"):
        _client().invoke([{"role": "user", "content": "hi"}])

    assert sleeps == []


def test_system_message_becomes_the_instruction_not_content(scripted):
    """Roles are mapped, not passed through: the SDK has no system role."""
    from google.genai import types as sdk_types

    seen = {}

    class _RecordingModels(_ScriptedModels):
        def generate_content(self, **kwargs):
            seen["config"] = kwargs["config"]
            seen["contents"] = kwargs["contents"]
            return super().generate_content(**kwargs)

    class _RecordingClient(_ScriptedClient):
        def __init__(self, script, *, api_key=None):
            self.api_key = api_key
            self.models = _RecordingModels(script)

    import google.genai
    import unittest.mock as mock

    factory, sleeps, holder = scripted
    script = ['{"ok": true}']
    with mock.patch.object(google.genai, "Client",
                           lambda *a, **k: _RecordingClient(script, *a, **k)):
        _client().invoke([
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "hi"},
            ("assistant", "hello"),
        ])

    assert seen["config"].system_instruction == "be brief"
    assert [c.role for c in seen["contents"]] == ["user", "model"]
    assert isinstance(seen["config"].response_schema, sdk_types.Schema)
