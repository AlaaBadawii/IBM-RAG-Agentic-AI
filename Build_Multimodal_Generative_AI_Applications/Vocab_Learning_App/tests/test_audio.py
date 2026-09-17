"""Tests for audio-script construction and the TTS wrapper."""

import os

import pytest

from src import audio
from src.audio import TTSError, build_audio_script, synthesize_speech
from src.validation import Lesson, WordEntry


def make_lesson():
    return Lesson(
        words=(
            WordEntry(
                word="achieve",
                definition="To reach a goal",
                examples=("She worked hard to achieve her goal.", "Practice helps you achieve more."),
            ),
            WordEntry(
                word="take responsibility",
                definition="To accept that something is your duty",
                examples=("He took responsibility for the mistake.", "Managers take responsibility for their teams."),
            ),
        ),
        story="Ahmed wanted to achieve something new.",
    )


def test_script_contains_every_section():
    script = build_audio_script(make_lesson())
    assert script.startswith("Vocabulary lesson.")
    assert "Word 1. achieve." in script
    assert "Word 2. take responsibility." in script
    assert "Definition. To reach a goal." in script
    assert "Example one. She worked hard to achieve her goal." in script
    assert "Example two. Practice helps you achieve more." in script
    assert "Story." in script
    assert "Ahmed wanted to achieve something new." in script
    assert script.strip().endswith("End of lesson.")


def test_script_adds_missing_sentence_punctuation():
    lesson = Lesson(
        words=(WordEntry(word="achieve", definition="To reach a goal", examples=("One", "Two")),),
        story="A story",
    )
    script = build_audio_script(lesson)
    assert "Definition. To reach a goal." in script
    assert "Example one. One." in script


def test_script_has_no_literal_pause_instructions():
    script = build_audio_script(make_lesson())
    assert "[" not in script
    assert "]" not in script


def test_script_is_plain_text_with_blank_line_separators():
    script = build_audio_script(make_lesson())
    assert "\n\n" in script
    assert "**" not in script and "#" not in script


class FakeGTTS:
    """Stand-in for gTTS that writes a tiny file instead of calling the network."""

    calls: list[tuple[str, str, bool]] = []

    def __init__(self, text, lang="en", slow=False):
        FakeGTTS.calls.append((text, lang, slow))
        self._text = text

    def save(self, path):
        with open(path, "wb") as handle:
            handle.write(b"ID3fake-mp3-bytes")


def test_synthesize_speech_writes_an_mp3(tmp_path, monkeypatch):
    monkeypatch.setattr(audio, "gTTS", FakeGTTS)
    FakeGTTS.calls.clear()

    path = synthesize_speech("Hello learner.", output_dir=str(tmp_path))

    assert path.endswith(".mp3")
    assert os.path.exists(path)
    assert os.path.getsize(path) > 0
    assert FakeGTTS.calls == [("Hello learner.", "en", False)]


def test_synthesize_speech_uses_unique_filenames(tmp_path, monkeypatch):
    monkeypatch.setattr(audio, "gTTS", FakeGTTS)
    first = synthesize_speech("One.", output_dir=str(tmp_path))
    second = synthesize_speech("Two.", output_dir=str(tmp_path))
    assert first != second
    assert os.path.exists(first) and os.path.exists(second)


def test_synthesize_speech_rejects_empty_script(tmp_path):
    with pytest.raises(TTSError):
        synthesize_speech("   ", output_dir=str(tmp_path))


def test_synthesize_speech_wraps_engine_failures(tmp_path, monkeypatch):
    class BrokenGTTS:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(audio, "gTTS", BrokenGTTS)
    with pytest.raises(TTSError, match="Audio generation failed"):
        synthesize_speech("Hello.", output_dir=str(tmp_path))


def test_synthesize_speech_reports_empty_output(tmp_path, monkeypatch):
    class SilentGTTS:
        def __init__(self, *args, **kwargs):
            pass

        def save(self, path):
            open(path, "wb").close()

    monkeypatch.setattr(audio, "gTTS", SilentGTTS)
    with pytest.raises(TTSError, match="empty file"):
        synthesize_speech("Hello.", output_dir=str(tmp_path))
