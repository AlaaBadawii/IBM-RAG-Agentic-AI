"""Gradio interface and application orchestration.

Flow: vocabulary list -> LLM -> JSON -> validation -> story coverage retries ->
audio script -> text-to-speech -> UI.

All of the control flow lives here; the modules under ``src/`` stay single-purpose.
"""

from __future__ import annotations

import os

import gradio as gr

from src.audio import TTSError, build_audio_script, synthesize_speech
from src.config import DEFAULT_MAX_VOCABULARY_ITEMS, ConfigError, load_config
from src.llm import LLMClient, LLMError
from src.validation import (
    Lesson,
    ValidationResult,
    lesson_with_story,
    validate_payload,
)
from src.vocabulary import VocabularyError, parse_vocabulary

# Bounded retries: never regenerate forever.
MAX_GENERATION_ATTEMPTS = 2
MAX_STORY_REVISIONS = 2

TITLE = "Vocabulary Audio Storyteller"

INTRO = """
Turn a list of vocabulary words into an audio lesson: learn the meaning, hear
practical examples, and listen to a story that puts all the words into context.
"""

PLACEHOLDER = (
    "Enter one word or phrase per line.\n\n"
    "Example:\n"
    "achieve\n"
    "challenge\n"
    "confident\n"
    "opportunity\n"
    "improve"
)

_ICONS = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}


def _status(message: str, kind: str = "info") -> str:
    return f"{_ICONS.get(kind, '')} {message}".strip()


def _fail(message: str) -> tuple[str, str, str, None]:
    """Uniform 'nothing was produced' result for the UI outputs."""
    return _status(message, "error"), "", "", None


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def render_lesson(lesson: Lesson) -> str:
    """Format the validated lesson as Markdown."""
    blocks = []
    for index, entry in enumerate(lesson.words, start=1):
        examples = "\n".join(f"- {example}" for example in entry.examples)
        blocks.append(
            f"### {index}. {entry.word}\n\n"
            f"**Definition:** {entry.definition}\n\n"
            f"**Examples:**\n{examples}"
        )
    return "\n\n".join(blocks)


def _describe_failure(result: ValidationResult) -> str:
    """Turn a failed validation into something a learner can act on."""
    parts = list(result.structural_errors[:3])
    if result.missing_in_lesson:
        parts.append(f"The lesson was missing: {', '.join(result.missing_in_lesson)}.")
    if result.missing_in_story:
        parts.append(f"The story did not use: {', '.join(result.missing_in_story)}.")
    return " ".join(parts) or "The lesson could not be generated correctly."


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def _generate_valid_lesson(
    client: LLMClient, words: list[str], progress: gr.Progress
) -> ValidationResult:
    """Ask the model for a lesson, retrying if it fails or comes back malformed."""
    result: ValidationResult | None = None
    last_error: LLMError | None = None

    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        if attempt > 1:
            progress(0.35, desc="The first response was unusable - asking again...")
        try:
            result = validate_payload(client.generate_lesson(words), words)
        except LLMError as exc:
            last_error = exc
            if not exc.retryable:
                raise
            continue
        if result.lesson is not None:
            return result

    if result is None and last_error is not None:
        raise last_error
    return result  # type: ignore[return-value]


def _ensure_story_coverage(
    client: LLMClient,
    result: ValidationResult,
    words: list[str],
    progress: gr.Progress,
) -> ValidationResult:
    """Rewrite the story until it uses every word, within a bounded retry count."""
    revisions = 0
    while (
        result.lesson is not None
        and result.missing_in_story
        and revisions < MAX_STORY_REVISIONS
    ):
        revisions += 1
        progress(
            0.6,
            desc=f"Rewriting the story to include: {', '.join(result.missing_in_story)}",
        )
        try:
            story = client.revise_story(words, result.lesson.story, result.missing_in_story)
        except LLMError as exc:
            # A failed rewrite is not fatal: keep the story we already have.
            if not exc.retryable:
                break
            continue

        revised = lesson_with_story(result.lesson, story, words)
        if revised.lesson is None:
            break
        result = revised

    return result


def generate_lesson(
    raw_text: str, progress: gr.Progress = gr.Progress()
) -> tuple[str, str, str, str | None]:
    """Run the full pipeline for one set of vocabulary words."""
    progress(0.0, desc="Reading your vocabulary list...")

    try:
        config = load_config()
        words = parse_vocabulary(raw_text, max_items=config.max_vocabulary_items)
    except (ConfigError, VocabularyError) as exc:
        return _fail(str(exc))

    client = LLMClient(config)

    progress(0.15, desc="Writing definitions, examples and a story...")
    try:
        result = _generate_valid_lesson(client, words, progress)
        if result.lesson is not None:
            result = _ensure_story_coverage(client, result, words, progress)
    except LLMError as exc:
        return _fail(str(exc))

    if result.lesson is None or result.missing_in_story:
        return _fail(_describe_failure(result))

    lesson = result.lesson
    lesson_markdown = render_lesson(lesson)

    progress(0.85, desc="Recording the audio lesson...")
    try:
        audio_path = synthesize_speech(build_audio_script(lesson))
    except TTSError as exc:
        # The written lesson is still good, so show it and be honest about the audio.
        return (
            _status(f"Lesson and story are ready, but the audio failed: {exc}", "warning"),
            lesson_markdown,
            lesson.story,
            None,
        )

    summary = (
        f"Lesson ready: {len(lesson.words)} words, "
        f"{len(lesson.story.split())} words in the story, audio generated."
    )
    return _status(summary, "success"), lesson_markdown, lesson.story, audio_path


# --------------------------------------------------------------------------- #
# Interface
# --------------------------------------------------------------------------- #


def build_interface() -> gr.Blocks:
    """Assemble the Gradio UI."""
    with gr.Blocks(title=TITLE) as demo:
        gr.Markdown(f"# {TITLE}")
        gr.Markdown(INTRO)

        with gr.Row():
            with gr.Column(scale=2):
                vocab_input = gr.Textbox(
                    label="Vocabulary Words",
                    placeholder=PLACEHOLDER,
                    lines=10,
                    max_lines=24,
                    info=(
                        "One word or phrase per line. Numbered and bulleted lists are fine. "
                        f"Up to {DEFAULT_MAX_VOCABULARY_ITEMS} items."
                    ),
                )
                generate_button = gr.Button("Generate Lesson", variant="primary")
                status_output = gr.Markdown(_status("Add your words, then generate a lesson."))

            with gr.Column(scale=3):
                lesson_output = gr.Markdown(label="Vocabulary Lesson", value="")

        story_output = gr.Markdown(label="Story", value="")
        audio_output = gr.Audio(
            label="Audio Lesson",
            type="filepath",
            sources=[],
            buttons=["download"],
            interactive=False,
        )

        outputs = [status_output, lesson_output, story_output, audio_output]
        generate_button.click(generate_lesson, inputs=[vocab_input], outputs=outputs)
        vocab_input.submit(generate_lesson, inputs=[vocab_input], outputs=outputs)

    return demo


def main() -> None:
    interface = build_interface()
    interface.queue()
    share = (os.getenv("GRADIO_SHARE") or "").strip().lower() in {"1", "true", "yes"}
    interface.launch(share=share)


if __name__ == "__main__":
    main()
