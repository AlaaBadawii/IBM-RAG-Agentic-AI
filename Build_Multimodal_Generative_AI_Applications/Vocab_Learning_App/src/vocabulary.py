"""Parsing and normalisation of the user's vocabulary input.

Everything here is deterministic: the LLM never sees the raw textbox contents,
only the clean list this module produces.
"""

from __future__ import annotations

import re

from .config import DEFAULT_MAX_VOCABULARY_ITEMS


class VocabularyError(ValueError):
    """Raised when the user's vocabulary input cannot be turned into a word list."""


# "1- word", "2. word", "3) word", "(4) word", "5: word"
_NUMBER_PREFIX = re.compile(r"^(?:\(\d{1,3}\)\s*|\d{1,3}\s*[.\-):–—]\s*)")
# "- word", "* word", "• word", "– word"
_BULLET_PREFIX = re.compile(r"^[\-*•·–—+]\s+")
_QUOTE_CHARS = "\"'“”‘’`"
_TRAILING_PUNCTUATION = ".,;:"


def _clean_line(line: str) -> str:
    """Strip list markers, quotes and stray punctuation from a single line."""
    text = line.strip()
    if not text:
        return ""

    # Peel markers twice so "- 1. word" is fully unwrapped.
    for _ in range(2):
        stripped = _NUMBER_PREFIX.sub("", _BULLET_PREFIX.sub("", text)).strip()
        if stripped == text:
            break
        text = stripped

    text = text.strip(_QUOTE_CHARS).strip()
    text = re.sub(r"\s+", " ", text)
    text = text.strip(_TRAILING_PUNCTUATION).strip()

    # A line of markers alone ("-", "1.", "...") is not a vocabulary item.
    if not any(character.isalnum() for character in text):
        return ""
    return text


def parse_vocabulary(
    raw_text: str, max_items: int = DEFAULT_MAX_VOCABULARY_ITEMS
) -> list[str]:
    """Turn raw textbox contents into a clean, de-duplicated list of vocabulary items.

    Accepts one word or phrase per line, tolerates numbered and bulleted lists,
    preserves the original order and casing of the first occurrence, and never
    invents items the user did not type.
    """
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise VocabularyError("Please enter at least one vocabulary word or phrase.")

    items: list[str] = []
    seen: set[str] = set()

    for line in raw_text.splitlines():
        cleaned = _clean_line(line)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        items.append(cleaned)

    if not items:
        raise VocabularyError(
            "No vocabulary words found. Enter one word or phrase per line."
        )
    if len(items) > max_items:
        raise VocabularyError(
            f"Please enter at most {max_items} vocabulary items "
            f"(you provided {len(items)})."
        )
    return items
