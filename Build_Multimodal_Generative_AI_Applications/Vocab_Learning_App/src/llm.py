"""LLM communication: prompt construction and OpenRouter-compatible chat calls.

This module only produces language content. Deciding whether that content is
acceptable is ``validation.py``'s job, and turning it into audio is
``audio.py``'s job.
"""

from __future__ import annotations

import json
from typing import Sequence

import requests

from .config import Config

SYSTEM_PROMPT = (
    "You are an English vocabulary learning assistant. You write clear, friendly "
    "material for intermediate learners and you always answer with valid JSON."
)

MAX_TOKENS = 4000
TEMPERATURE = 0.7


class LLMError(RuntimeError):
    """Raised when the model request fails or returns content we cannot use.

    ``retryable`` marks failures that are worth another attempt - timeouts,
    throttling and transient empty responses - as opposed to a misconfigured or
    rejected API key, where retrying only wastes the user's time.
    """

    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #


def _story_length_range(word_count: int) -> tuple[int, int]:
    """Target story length, scaled by how many words must fit inside it."""
    target = max(300, min(500, 250 + 20 * word_count))
    return target - 50, target + 50


def _bulleted(words: Sequence[str]) -> str:
    return "\n".join(f"- {word}" for word in words)


def build_lesson_prompt(words: Sequence[str]) -> str:
    """Prompt asking for definitions, examples and a story in one JSON object."""
    low, high = _story_length_range(len(words))
    return f"""Create an English vocabulary lesson for an intermediate learner using exactly these vocabulary items:

{_bulleted(words)}

For each vocabulary item, in the same order as the list above, provide:
- "word": the item spelled exactly as given above.
- "definition": one or two short, conversational sentences explaining the meaning in everyday English. Do not use harder words than the word you are explaining.
- "examples": exactly two natural, practical sentences that show the meaning. The two sentences must describe different situations, not two versions of the same one.

Then write one "story" that:
- uses every one of the {len(words)} vocabulary items above, naturally and meaningfully
- makes the meaning of each item clear from the surrounding context
- is engaging, not a list of definitions
- is written in simple English that an intermediate learner can follow
- is between {low} and {high} words long
- does not simply repeat the example sentences

Reply with a single JSON object and nothing else, using exactly this structure:
{{
  "words": [
    {{"word": "...", "definition": "...", "examples": ["...", "..."]}}
  ],
  "story": "..."
}}"""


def build_story_revision_prompt(
    words: Sequence[str], story: str, missing: Sequence[str]
) -> str:
    """Prompt asking for the story to be rewritten so it covers every word."""
    return f"""You wrote the story below for an English vocabulary lesson.

Rewrite it so that every one of these vocabulary items appears in the story, used naturally and with its meaning clear from the context:
{_bulleted(missing)}

Requirements:
- keep the story in simple English that an intermediate learner can follow
- keep it engaging and roughly the same length as the original
- keep using these other vocabulary items from the lesson as well: {", ".join(words)}
- do not turn the story into a list of definitions

Story to rewrite:
\"\"\"{story}\"\"\"

Reply with a single JSON object and nothing else, using exactly this structure:
{{"story": "..."}}"""


# --------------------------------------------------------------------------- #
# Response parsing
# --------------------------------------------------------------------------- #


def _first_json_object(text: str) -> str | None:
    """Return the first balanced ``{...}`` block, ignoring braces inside strings."""
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None


def extract_json_object(text: str) -> dict:
    """Parse a JSON object out of a model response, tolerating prose and code fences."""
    if not isinstance(text, str) or not text.strip():
        raise LLMError("The language model returned an empty response.")

    stripped = text.strip()
    candidates = [stripped]

    if "```" in stripped:
        fenced = stripped.split("```")
        # Odd indices are the contents of a fenced block.
        for chunk in fenced[1::2]:
            body = chunk.strip()
            if body.lower().startswith("json"):
                body = body[4:].strip()
            if body:
                candidates.append(body)

    balanced = _first_json_object(stripped)
    if balanced:
        candidates.append(balanced)

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed

    raise LLMError(
        "The language model did not return valid JSON. Try generating the lesson again."
    )


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #


class LLMClient:
    """Thin wrapper around an OpenRouter-compatible chat completions endpoint."""

    def __init__(self, config: Config) -> None:
        self._config = config

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }

    def _post(self, payload: dict) -> requests.Response:
        try:
            return requests.post(
                f"{self._config.base_url}/chat/completions",
                headers=self._headers,
                json=payload,
                timeout=self._config.request_timeout,
            )
        except requests.Timeout as exc:
            raise LLMError(
                "The language model request timed out. Please try again."
            ) from exc
        except requests.RequestException as exc:
            raise LLMError(
                "Could not reach the language model service. "
                "Check your internet connection and LLM_BASE_URL."
            ) from exc

    def complete(self, prompt: str, json_mode: bool = True) -> str:
        """Send one chat completion request and return the assistant's text."""
        payload: dict = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        response = self._post(payload)

        # Not every provider supports response_format; retry once without it.
        if response.status_code == 400 and json_mode and "response_format" in response.text.lower():
            payload.pop("response_format")
            response = self._post(payload)

        if response.status_code in (401, 403):
            raise LLMError(
                "The language model rejected the API key. Check LLM_API_KEY in your .env file.",
                retryable=False,
            )
        if response.status_code == 429:
            raise LLMError(
                "The language model is rate limiting requests. Please wait a moment and try again."
            )
        if not response.ok:
            raise LLMError(
                f"The language model returned an error (HTTP {response.status_code})."
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMError("The language model returned a response that was not JSON.") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(
                "The language model response did not contain any lesson content."
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMError("The language model returned an empty response.")

        return content

    def generate_lesson(self, words: Sequence[str]) -> dict:
        """Ask for a full lesson payload (definitions, examples and story)."""
        return extract_json_object(self.complete(build_lesson_prompt(words)))

    def revise_story(self, words: Sequence[str], story: str, missing: Sequence[str]) -> str:
        """Ask for the story to be rewritten so that it covers ``missing``."""
        payload = extract_json_object(
            self.complete(build_story_revision_prompt(words, story, missing))
        )
        revised = payload.get("story")
        if not isinstance(revised, str) or not revised.strip():
            raise LLMError("The language model returned no story to use.")
        return revised.strip()
