"""Deterministic validation of the structured lesson returned by the model.

The LLM is asked to produce a specific JSON shape; this module decides whether
what actually came back is usable. It also owns the vocabulary-coverage checks,
because "did the story use every word?" is a question Python can answer exactly
and an LLM cannot be trusted to answer about itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Any, Iterable, Sequence

REQUIRED_FIELDS = ("word", "definition", "examples")
EXAMPLES_PER_WORD = 2

# Irregular forms a story may legitimately use instead of the base form the user
# supplied ("take responsibility" -> "took responsibility"). Kept deliberately
# small: it exists to avoid false "missing word" failures, not to be a stemmer.
_IRREGULAR: dict[str, frozenset[str]] = {
    "be": frozenset({"am", "is", "are", "was", "were", "been", "being"}),
    "become": frozenset({"became", "becoming"}),
    "begin": frozenset({"began", "begun", "beginning"}),
    "bring": frozenset({"brought"}),
    "build": frozenset({"built"}),
    "buy": frozenset({"bought"}),
    "catch": frozenset({"caught"}),
    "choose": frozenset({"chose", "chosen"}),
    "come": frozenset({"came"}),
    "do": frozenset({"did", "done", "doing"}),
    "drive": frozenset({"drove", "driven"}),
    "feel": frozenset({"felt"}),
    "find": frozenset({"found"}),
    "get": frozenset({"got", "gotten"}),
    "give": frozenset({"gave", "given"}),
    "go": frozenset({"went", "gone"}),
    "grow": frozenset({"grew", "grown"}),
    "have": frozenset({"has", "had"}),
    "hold": frozenset({"held"}),
    "keep": frozenset({"kept"}),
    "know": frozenset({"knew", "known"}),
    "leave": frozenset({"left"}),
    "lose": frozenset({"lost"}),
    "make": frozenset({"made"}),
    "meet": frozenset({"met"}),
    "pay": frozenset({"paid"}),
    "run": frozenset({"ran", "running"}),
    "say": frozenset({"said"}),
    "see": frozenset({"saw", "seen"}),
    "sell": frozenset({"sold"}),
    "send": frozenset({"sent"}),
    "show": frozenset({"shown"}),
    "speak": frozenset({"spoke", "spoken"}),
    "spend": frozenset({"spent"}),
    "stand": frozenset({"stood"}),
    "take": frozenset({"took", "taken", "taking"}),
    "teach": frozenset({"taught"}),
    "tell": frozenset({"told"}),
    "think": frozenset({"thought"}),
    "understand": frozenset({"understood"}),
    "win": frozenset({"won"}),
    "write": frozenset({"wrote", "written"}),
}

_IRREGULAR_PLURALS: dict[str, str] = {
    "child": "children",
    "foot": "feet",
    "life": "lives",
    "man": "men",
    "person": "people",
    "tooth": "teeth",
    "woman": "women",
}

# Only used when matching a multi-word phrase loosely.
_STOPWORDS = frozenset(
    {"a", "an", "the", "of", "to", "in", "on", "at", "by", "for", "with", "and", "or", "up"}
)

_WORD_RE = re.compile(r"[a-z0-9']+")
_VOWELS = frozenset("aeiou")


@dataclass(frozen=True)
class WordEntry:
    """One validated vocabulary item."""

    word: str
    definition: str
    examples: tuple[str, ...]


@dataclass(frozen=True)
class Lesson:
    """A validated lesson: every requested word, plus the story that uses them."""

    words: tuple[WordEntry, ...]
    story: str


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of validating one model response against the requested words."""

    lesson: Lesson | None
    structural_errors: tuple[str, ...] = ()
    missing_in_lesson: tuple[str, ...] = ()
    missing_in_story: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return (
            self.lesson is not None
            and not self.structural_errors
            and not self.missing_in_lesson
            and not self.missing_in_story
        )


# --------------------------------------------------------------------------- #
# Text matching
# --------------------------------------------------------------------------- #


def _tokens(text: str) -> list[str]:
    """Lowercase word tokens of a piece of text."""
    return _WORD_RE.findall(text.casefold())


@lru_cache(maxsize=4096)
def _candidate_forms(token: str) -> frozenset[str]:
    """Plausible surface forms of a token, so 'achieve' also matches 'achieved'."""
    forms = {token}
    forms.update(_IRREGULAR.get(token, ()))

    # If the user supplied an inflected form, also accept its base and siblings.
    for base, inflected in _IRREGULAR.items():
        if token in inflected:
            forms.add(base)
            forms.update(inflected)

    plural = _IRREGULAR_PLURALS.get(token)
    if plural:
        forms.add(plural)
    for base, plural_form in _IRREGULAR_PLURALS.items():
        if token == plural_form:
            forms.add(base)

    length = len(token)
    if length >= 3:
        if token.endswith("y") and token[-2] not in _VOWELS:
            forms.add(token[:-1] + "ies")
        else:
            forms.add(token + "s")
        forms.add(token + "es")

    if length >= 2:
        forms.add(token + "d" if token.endswith("e") else token + "ed")
        forms.add(token[:-1] + "ing" if token.endswith("e") else token + "ing")

    # Consonant doubling for short words: stop -> stopped / stopping.
    if length >= 3 and token[-1] not in _VOWELS and token[-2] in _VOWELS and token[-3] not in _VOWELS:
        forms.add(token + token[-1] + "ing")
        forms.add(token + token[-1] + "ed")

    # De-inflection, in case the user's own item was already inflected.
    if token.endswith("ies") and length > 4:
        forms.add(token[:-3] + "y")
    if token.endswith("es") and length > 3:
        forms.add(token[:-2])
    if token.endswith("s") and length > 3:
        forms.add(token[:-1])
    if token.endswith("ing") and length > 5:
        forms.add(token[:-3])
        forms.add(token[:-3] + "e")
    if token.endswith("ed") and length > 4:
        forms.add(token[:-2])
        forms.add(token[:-1])
    if token.endswith("ly") and length > 4:
        forms.add(token[:-2])

    return frozenset(forms)


def _matches_token(text_token: str, term_token: str) -> bool:
    return text_token in _candidate_forms(term_token)


def _ordered_match(text_tokens: Sequence[str], term_tokens: Sequence[str], span_slack: int = 3) -> bool:
    """True if the term tokens appear in order, allowing a few words between them."""
    span = len(term_tokens) + span_slack
    for start in range(len(text_tokens)):
        cursor = start
        limit = min(len(text_tokens), start + span)
        for term_token in term_tokens:
            while cursor < limit and not _matches_token(text_tokens[cursor], term_token):
                cursor += 1
            if cursor >= limit:
                break
            cursor += 1
        else:
            return True
    return False


def contains_term(text: str, term: str) -> bool:
    """True if ``text`` uses ``term``, allowing common inflected forms.

    Multi-word phrases are matched in order when possible, and otherwise fall
    back to requiring every content word of the phrase to be present.
    """
    term_tokens = _tokens(term)
    if not term_tokens:
        return False

    text_tokens = _tokens(text)
    if not text_tokens:
        return False

    if len(term_tokens) == 1:
        return any(_matches_token(token, term_tokens[0]) for token in text_tokens)

    if _ordered_match(text_tokens, term_tokens):
        return True

    content = [token for token in term_tokens if token not in _STOPWORDS] or term_tokens
    return all(
        any(_matches_token(token, wanted) for token in text_tokens) for wanted in content
    )


def find_missing_terms(text: str, terms: Iterable[str]) -> tuple[str, ...]:
    """Return the terms, in order, that ``text`` does not use."""
    return tuple(term for term in terms if not contains_term(text, term))


def _same_term(candidate: str, requested: str) -> bool:
    """True if a model-reported word is the word the user asked for."""
    candidate_tokens = _tokens(candidate)
    requested_tokens = _tokens(requested)
    if not candidate_tokens or not requested_tokens:
        return False
    if candidate_tokens == requested_tokens:
        return True
    return contains_term(candidate, requested) and contains_term(requested, candidate)


# --------------------------------------------------------------------------- #
# Payload validation
# --------------------------------------------------------------------------- #


def _align(entries: Sequence[WordEntry], requested: Sequence[str]) -> tuple[list[WordEntry], tuple[str, ...]]:
    """Order the model's entries to match the user's list, reporting any gaps."""
    remaining = list(entries)
    aligned: list[WordEntry] = []
    missing: list[str] = []

    for term in requested:
        match = next((entry for entry in remaining if _same_term(entry.word, term)), None)
        if match is None:
            missing.append(term)
            continue
        remaining.remove(match)
        # Always display the user's own spelling of the word.
        aligned.append(replace(match, word=term))

    return aligned, tuple(missing)


def _parse_entries(raw_words: Any, structural_errors: list[str]) -> list[WordEntry]:
    """Validate the ``words`` array into WordEntry objects, collecting problems."""
    if not isinstance(raw_words, list) or not raw_words:
        structural_errors.append("The response did not contain a 'words' list.")
        return []

    entries: list[WordEntry] = []
    for index, item in enumerate(raw_words, start=1):
        if not isinstance(item, dict):
            structural_errors.append(f"Vocabulary entry {index} was not an object.")
            continue

        absent = [field for field in REQUIRED_FIELDS if not item.get(field)]
        if absent:
            structural_errors.append(
                f"Vocabulary entry {index} is missing: {', '.join(absent)}."
            )
            continue

        word, definition, examples = item["word"], item["definition"], item["examples"]
        if not isinstance(word, str) or not isinstance(definition, str):
            structural_errors.append(
                f"Vocabulary entry {index} has a non-text word or definition."
            )
            continue
        if not isinstance(examples, list):
            structural_errors.append(f"The examples for '{word}' were not a list.")
            continue

        usable = [example.strip() for example in examples if isinstance(example, str) and example.strip()]
        if len(usable) < EXAMPLES_PER_WORD:
            structural_errors.append(
                f"'{word}' has fewer than {EXAMPLES_PER_WORD} usable example sentences."
            )
            continue

        # Normalise to exactly two examples so downstream code has one shape.
        entries.append(
            WordEntry(word=word.strip(), definition=definition.strip(), examples=tuple(usable[:EXAMPLES_PER_WORD]))
        )

    return entries


def validate_payload(payload: Any, requested: Sequence[str]) -> ValidationResult:
    """Validate a raw model response against the words the user supplied."""
    if not isinstance(payload, dict):
        return ValidationResult(
            lesson=None, structural_errors=("The model did not return a JSON object.",)
        )

    structural_errors: list[str] = []
    entries = _parse_entries(payload.get("words"), structural_errors)

    story = payload.get("story")
    if not isinstance(story, str) or not story.strip():
        structural_errors.append("The response did not contain a story.")
        story = ""
    else:
        story = story.strip()

    aligned, missing_in_lesson = _align(entries, requested)
    missing_in_story = find_missing_terms(story, requested) if story else tuple(requested)

    if structural_errors or missing_in_lesson:
        return ValidationResult(
            lesson=None,
            structural_errors=tuple(structural_errors),
            missing_in_lesson=missing_in_lesson,
            missing_in_story=missing_in_story,
        )

    return ValidationResult(
        lesson=Lesson(words=tuple(aligned), story=story),
        missing_in_story=missing_in_story,
    )


def lesson_with_story(lesson: Lesson, story: str, requested: Sequence[str]) -> ValidationResult:
    """Re-validate a lesson after its story has been rewritten."""
    story = (story or "").strip()
    if not story:
        return ValidationResult(
            lesson=None,
            structural_errors=("The revised story was empty.",),
            missing_in_story=tuple(requested),
        )
    return ValidationResult(
        lesson=replace(lesson, story=story),
        missing_in_story=find_missing_terms(story, requested),
    )
