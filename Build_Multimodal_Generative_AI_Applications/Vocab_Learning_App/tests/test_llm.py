"""Tests for LLM prompt construction, response parsing and error handling."""

import json

import pytest
import requests

from src import llm
from src.config import Config
from src.llm import LLMClient, LLMError, build_lesson_prompt, extract_json_object

CONFIG = Config(
    api_key="secret-test-key",
    base_url="https://example.invalid/api/v1",
    model="test-model",
    max_vocabulary_items=15,
    request_timeout=5,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.ok = 200 <= status_code < 300

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def completion(content: str, status_code: int = 200):
    return FakeResponse(status_code, {"choices": [{"message": {"content": content}}]})


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #


def test_lesson_prompt_lists_every_word():
    prompt = build_lesson_prompt(["achieve", "take responsibility"])
    assert "- achieve" in prompt
    assert "- take responsibility" in prompt
    assert "exactly two" in prompt
    assert '"story"' in prompt


def test_revision_prompt_names_the_missing_words():
    prompt = llm.build_story_revision_prompt(
        ["achieve", "challenge"], "An old story.", ["challenge"]
    )
    assert "- challenge" in prompt
    assert "An old story." in prompt
    assert "achieve" in prompt


# --------------------------------------------------------------------------- #
# JSON extraction
# --------------------------------------------------------------------------- #


def test_plain_json_is_parsed():
    assert extract_json_object('{"story": "hi"}') == {"story": "hi"}


def test_fenced_json_is_parsed():
    raw = 'Here you go:\n```json\n{"story": "hi"}\n```\nHope that helps!'
    assert extract_json_object(raw) == {"story": "hi"}


def test_json_wrapped_in_prose_is_parsed():
    raw = 'Sure! {"words": [], "story": "hi"} Let me know if you need more.'
    assert extract_json_object(raw) == {"words": [], "story": "hi"}


def test_braces_inside_strings_do_not_confuse_the_scanner():
    raw = 'prefix {"story": "he said {hello} loudly"} suffix'
    assert extract_json_object(raw) == {"story": "he said {hello} loudly"}


def test_malformed_json_raises_llm_error():
    with pytest.raises(LLMError, match="valid JSON"):
        extract_json_object('{"story": "unterminated')


def test_non_object_json_raises_llm_error():
    with pytest.raises(LLMError):
        extract_json_object("[1, 2, 3]")


def test_empty_response_raises_llm_error():
    with pytest.raises(LLMError):
        extract_json_object("   ")


# --------------------------------------------------------------------------- #
# HTTP handling
# --------------------------------------------------------------------------- #


def test_complete_returns_content(monkeypatch):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: completion('{"ok": true}'))
    assert LLMClient(CONFIG).complete("prompt") == '{"ok": true}'


def test_json_mode_is_requested(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(json)
        return completion('{"ok": true}')

    monkeypatch.setattr(llm.requests, "post", fake_post)
    LLMClient(CONFIG).complete("prompt")
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["model"] == "test-model"


def test_unsupported_json_mode_is_retried_without_it(monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(dict(json))
        if len(calls) == 1:
            return FakeResponse(400, text="response_format is not supported")
        return completion('{"ok": true}')

    monkeypatch.setattr(llm.requests, "post", fake_post)
    assert LLMClient(CONFIG).complete("prompt") == '{"ok": true}'
    assert len(calls) == 2
    assert "response_format" not in calls[1]


def test_timeout_becomes_llm_error(monkeypatch):
    def fake_post(*args, **kwargs):
        raise requests.Timeout("slow")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    with pytest.raises(LLMError, match="timed out"):
        LLMClient(CONFIG).complete("prompt")


def test_network_error_becomes_llm_error(monkeypatch):
    def fake_post(*args, **kwargs):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    with pytest.raises(LLMError, match="Could not reach"):
        LLMClient(CONFIG).complete("prompt")


def test_bad_api_key_message_does_not_leak_the_key(monkeypatch):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: FakeResponse(401, text="unauthorized"))
    with pytest.raises(LLMError) as excinfo:
        LLMClient(CONFIG).complete("prompt")
    assert "LLM_API_KEY" in str(excinfo.value)
    assert CONFIG.api_key not in str(excinfo.value)


def test_server_error_becomes_llm_error(monkeypatch):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: FakeResponse(500, text="boom"))
    with pytest.raises(LLMError, match="HTTP 500"):
        LLMClient(CONFIG).complete("prompt")


def test_non_json_body_becomes_llm_error(monkeypatch):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: FakeResponse(200, None, "not json"))
    with pytest.raises(LLMError, match="not JSON"):
        LLMClient(CONFIG).complete("prompt")


def test_missing_content_becomes_llm_error(monkeypatch):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: FakeResponse(200, {"choices": []}))
    with pytest.raises(LLMError, match="did not contain"):
        LLMClient(CONFIG).complete("prompt")


def test_generate_lesson_parses_the_payload(monkeypatch):
    payload = {"words": [], "story": "hi"}
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: completion(json.dumps(payload)))
    assert LLMClient(CONFIG).generate_lesson(["achieve"]) == payload


def test_revise_story_returns_the_new_story(monkeypatch):
    monkeypatch.setattr(
        llm.requests, "post", lambda *a, **k: completion('{"story": "A brand new story."}')
    )
    assert (
        LLMClient(CONFIG).revise_story(["achieve"], "Old story.", ["achieve"])
        == "A brand new story."
    )


def test_revise_story_without_a_story_is_an_error(monkeypatch):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: completion('{"story": ""}'))
    with pytest.raises(LLMError):
        LLMClient(CONFIG).revise_story(["achieve"], "Old story.", ["achieve"])
