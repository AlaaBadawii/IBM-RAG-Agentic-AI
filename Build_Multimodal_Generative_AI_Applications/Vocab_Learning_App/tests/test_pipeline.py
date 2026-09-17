"""End-to-end tests for the orchestration in app.py.

The LLM and the TTS engine are the only things replaced; everything else -
parsing, validation, retries, script construction - runs for real.
"""

import pytest

import app
from src.config import Config
from src.llm import LLMError

CONFIG = Config(
    api_key="test-key",
    base_url="https://example.invalid/api/v1",
    model="test-model",
    max_vocabulary_items=15,
    request_timeout=5,
)

WORDS = ["achieve", "challenge", "confident"]


def lesson_payload(words=WORDS, story=None):
    return {
        "words": [
            {
                "word": word,
                "definition": f"Simple definition of {word}.",
                "examples": [f"First example with {word}.", f"Second example with {word}."],
            }
            for word in words
        ],
        "story": story or f"A story that uses {', '.join(words)} naturally.",
    }


class FakeClient:
    """Replays scripted responses and records what it was asked for."""

    def __init__(self, payloads=(), stories=()):
        self.payloads = list(payloads)
        self.stories = list(stories)
        self.lesson_calls: list[list[str]] = []
        self.story_calls: list[tuple] = []

    def generate_lesson(self, words):
        self.lesson_calls.append(list(words))
        response = self.payloads.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def revise_story(self, words, story, missing):
        self.story_calls.append((list(words), story, list(missing)))
        response = self.stories.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def ui(monkeypatch):
    """Wire app.generate_lesson up to fakes and capture the audio script."""
    captured = {}

    def fake_synthesize(script, lang="en", output_dir=None):
        captured["script"] = script
        return "/tmp/fake_lesson.mp3"

    monkeypatch.setattr(app, "load_config", lambda: CONFIG)
    monkeypatch.setattr(app, "synthesize_speech", fake_synthesize)
    return captured


def run(client, text, monkeypatch, ui):
    monkeypatch.setattr(app, "LLMClient", lambda config: client)
    return app.generate_lesson(text, progress=lambda *a, **k: None)


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #


def test_full_workflow_succeeds(monkeypatch, ui):
    client = FakeClient(payloads=[lesson_payload()])
    status, lesson_md, story_md, audio = run(client, "\n".join(WORDS), monkeypatch, ui)

    assert status.startswith("✅")
    assert "3 words" in status
    assert "### 1. achieve" in lesson_md
    assert "**Definition:** Simple definition of achieve." in lesson_md
    assert story_md
    assert audio == "/tmp/fake_lesson.mp3"
    assert client.lesson_calls == [WORDS]
    assert client.story_calls == []


def test_audio_script_covers_every_word(monkeypatch, ui):
    client = FakeClient(payloads=[lesson_payload()])
    run(client, "\n".join(WORDS), monkeypatch, ui)

    script = ui["script"]
    assert script.startswith("Vocabulary lesson.")
    assert script.strip().endswith("End of lesson.")
    for word in WORDS:
        assert f"Definition. Simple definition of {word}." in script


def test_numbered_and_duplicated_input_is_normalised_before_the_llm(monkeypatch, ui):
    client = FakeClient(payloads=[lesson_payload()])
    run(client, "1- achieve\n2. challenge\n3- achieve\n4- confident", monkeypatch, ui)

    assert client.lesson_calls == [WORDS]


# --------------------------------------------------------------------------- #
# Validation and recovery
# --------------------------------------------------------------------------- #


def test_structural_failure_triggers_one_regeneration(monkeypatch, ui):
    broken = lesson_payload()
    broken["words"][0]["examples"] = ["only one"]

    client = FakeClient(payloads=[broken, lesson_payload()])
    status, lesson_md, _, audio = run(client, "\n".join(WORDS), monkeypatch, ui)

    assert status.startswith("✅")
    assert len(client.lesson_calls) == 2
    assert audio == "/tmp/fake_lesson.mp3"


def test_missing_word_in_story_triggers_a_story_revision(monkeypatch, ui):
    incomplete = lesson_payload(story="A story that only mentions achieve.")
    revised = "A story that mentions achieve, challenge and confident."

    client = FakeClient(payloads=[incomplete], stories=[revised])
    status, _, story_md, audio = run(client, "\n".join(WORDS), monkeypatch, ui)

    assert status.startswith("✅")
    assert story_md == revised
    assert audio == "/tmp/fake_lesson.mp3"
    assert client.story_calls[0][2] == ["challenge", "confident"]


def test_story_revisions_are_bounded_and_failure_is_reported(monkeypatch, ui):
    incomplete = lesson_payload(story="A story that only mentions achieve.")

    client = FakeClient(
        payloads=[incomplete],
        stories=[incomplete["story"], incomplete["story"], incomplete["story"]],
    )
    status, lesson_md, story_md, audio = run(client, "\n".join(WORDS), monkeypatch, ui)

    assert status.startswith("❌")
    assert "challenge" in status
    # Nothing is presented as a finished lesson.
    assert (lesson_md, story_md, audio) == ("", "", None)
    assert len(client.story_calls) == app.MAX_STORY_REVISIONS


def test_second_structural_failure_is_reported(monkeypatch, ui):
    broken = lesson_payload()
    del broken["words"][0]["definition"]

    client = FakeClient(payloads=[broken, broken])
    status, lesson_md, _, audio = run(client, "\n".join(WORDS), monkeypatch, ui)

    assert status.startswith("❌")
    assert "definition" in status
    assert (lesson_md, audio) == ("", None)
    assert len(client.lesson_calls) == app.MAX_GENERATION_ATTEMPTS


# --------------------------------------------------------------------------- #
# Failure handling
# --------------------------------------------------------------------------- #


def test_empty_input_makes_no_llm_request(monkeypatch, ui):
    client = FakeClient(payloads=[])
    status, lesson_md, story_md, audio = run(client, "   \n\n", monkeypatch, ui)

    assert status.startswith("❌")
    assert "at least one" in status
    assert client.lesson_calls == []
    assert (lesson_md, story_md, audio) == ("", "", None)


def test_too_many_words_is_rejected_before_the_llm(monkeypatch, ui):
    client = FakeClient(payloads=[])
    text = "\n".join(f"word{i}" for i in range(CONFIG.max_vocabulary_items + 1))
    status, *_ = run(client, text, monkeypatch, ui)

    assert "at most" in status
    assert client.lesson_calls == []


def test_llm_failure_is_reported_without_a_traceback(monkeypatch, ui):
    client = FakeClient(
        payloads=[
            LLMError("The language model request timed out."),
            LLMError("The language model request timed out."),
        ]
    )
    status, lesson_md, _, audio = run(client, "\n".join(WORDS), monkeypatch, ui)

    assert status.startswith("❌")
    assert "timed out" in status
    assert (lesson_md, audio) == ("", None)


def test_malformed_json_response_is_reported(monkeypatch, ui):
    client = FakeClient(
        payloads=[
            LLMError("The language model did not return valid JSON."),
            LLMError("The language model did not return valid JSON."),
        ]
    )
    status, *_ = run(client, "\n".join(WORDS), monkeypatch, ui)
    assert "valid JSON" in status


def test_tts_failure_still_shows_the_written_lesson(monkeypatch, ui):
    def broken_tts(script, lang="en", output_dir=None):
        from src.audio import TTSError

        raise TTSError("Audio generation failed.")

    monkeypatch.setattr(app, "synthesize_speech", broken_tts)
    client = FakeClient(payloads=[lesson_payload()])
    status, lesson_md, story_md, audio = run(client, "\n".join(WORDS), monkeypatch, ui)

    assert status.startswith("⚠️")
    assert "audio failed" in status
    assert "### 1. achieve" in lesson_md
    assert story_md
    assert audio is None


def test_story_revision_error_keeps_the_original_story(monkeypatch, ui):
    incomplete = lesson_payload(story="A story that only mentions achieve.")
    client = FakeClient(
        payloads=[incomplete],
        stories=[LLMError("network died"), LLMError("network died")],
    )
    status, _, _, audio = run(client, "\n".join(WORDS), monkeypatch, ui)

    assert status.startswith("❌")
    assert audio is None
    assert len(client.story_calls) <= app.MAX_STORY_REVISIONS


# --------------------------------------------------------------------------- #
# Retry policy
# --------------------------------------------------------------------------- #


def test_transient_llm_error_is_retried(monkeypatch, ui):
    client = FakeClient(payloads=[LLMError("The language model returned an empty response."),
                                  lesson_payload()])
    status, _, _, audio = run(client, "\n".join(WORDS), monkeypatch, ui)

    assert status.startswith("✅")
    assert len(client.lesson_calls) == 2
    assert audio == "/tmp/fake_lesson.mp3"


def test_transient_error_on_every_attempt_is_reported(monkeypatch, ui):
    client = FakeClient(
        payloads=[LLMError("empty response"), LLMError("empty response")]
    )
    status, lesson_md, _, audio = run(client, "\n".join(WORDS), monkeypatch, ui)

    assert status.startswith("❌")
    assert "empty response" in status
    assert (lesson_md, audio) == ("", None)
    assert len(client.lesson_calls) == app.MAX_GENERATION_ATTEMPTS


def test_non_retryable_llm_error_is_not_retried(monkeypatch, ui):
    client = FakeClient(
        payloads=[LLMError("The language model rejected the API key.", retryable=False)]
    )
    status, *_ = run(client, "\n".join(WORDS), monkeypatch, ui)

    assert status.startswith("❌")
    assert "API key" in status
    assert len(client.lesson_calls) == 1
