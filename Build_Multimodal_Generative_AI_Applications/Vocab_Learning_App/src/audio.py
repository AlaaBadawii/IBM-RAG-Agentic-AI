"""Audio-script construction and text-to-speech.

The script is assembled in Python from validated data, so the wording of the
lesson never depends on the model following formatting instructions. The TTS
engine is isolated behind ``synthesize_speech`` so another provider can be
dropped in later.
"""

from __future__ import annotations

import os
import tempfile
import uuid

from gtts import gTTS

from .validation import Lesson

DEFAULT_LANG = "en"


class TTSError(RuntimeError):
    """Raised when the audio lesson could not be produced."""


def _as_sentence(text: str) -> str:
    """Make sure a fragment ends with punctuation, so TTS pauses naturally."""
    text = text.strip()
    if not text:
        return ""
    if text[-1] not in ".!?":
        text += "."
    return text


def build_audio_script(lesson: Lesson) -> str:
    """Turn a validated lesson into a spoken-word script.

    Sections are separated by blank lines and natural sentence boundaries rather
    than by literal pause instructions, which the TTS engine would read aloud.
    """
    lines: list[str] = ["Vocabulary lesson.", ""]

    for index, entry in enumerate(lesson.words, start=1):
        lines.append(f"Word {index}. {_as_sentence(entry.word)}")
        lines.append("")
        lines.append(f"Definition. {_as_sentence(entry.definition)}")
        lines.append("")
        lines.append(f"Example one. {_as_sentence(entry.examples[0])}")
        lines.append("")
        lines.append(f"Example two. {_as_sentence(entry.examples[1])}")
        lines.append("")

    lines.append("Story.")
    lines.append("")
    lines.append(lesson.story.strip())
    lines.append("")
    lines.append("End of lesson.")

    return "\n".join(lines)


def synthesize_speech(
    script: str, lang: str = DEFAULT_LANG, output_dir: str | None = None
) -> str:
    """Convert a script to an MP3 file and return its path.

    Each call writes a uniquely named file so concurrent generations cannot
    overwrite one another.
    """
    if not script or not script.strip():
        raise TTSError("There was no lesson text to convert to audio.")

    directory = output_dir or tempfile.gettempdir()
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError as exc:
        raise TTSError("Could not prepare a folder for the audio file.") from exc

    path = os.path.join(directory, f"vocabulary_lesson_{uuid.uuid4().hex}.mp3")

    try:
        gTTS(text=script, lang=lang, slow=False).save(path)
    except Exception as exc:  # gTTS raises its own error type plus network errors
        raise TTSError(
            "Audio generation failed. Check your internet connection and try again."
        ) from exc

    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise TTSError("Audio generation produced an empty file.")

    return path
