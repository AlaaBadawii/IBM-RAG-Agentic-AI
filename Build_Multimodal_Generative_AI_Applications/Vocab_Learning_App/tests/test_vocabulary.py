"""Tests for user input parsing."""

import pytest

from src.vocabulary import VocabularyError, parse_vocabulary


def test_plain_list_preserves_order():
    assert parse_vocabulary("achieve\nchallenge\nconfident") == [
        "achieve",
        "challenge",
        "confident",
    ]


def test_numbered_input_is_normalised():
    raw = "1- achieve\n2. challenge\n3) confident\n(4) opportunity"
    assert parse_vocabulary(raw) == ["achieve", "challenge", "confident", "opportunity"]


def test_bulleted_input_is_normalised():
    raw = "- achieve\n* challenge\n• confident"
    assert parse_vocabulary(raw) == ["achieve", "challenge", "confident"]


def test_nested_markers_are_peeled():
    assert parse_vocabulary("- 1. achieve") == ["achieve"]


def test_blank_lines_and_padding_are_ignored():
    raw = "  achieve  \n\n\n   challenge\n\t\n"
    assert parse_vocabulary(raw) == ["achieve", "challenge"]


def test_duplicates_are_removed_preserving_first_occurrence():
    raw = "1- achieve\n2- challenge\n3- achieve\nACHIEVE"
    assert parse_vocabulary(raw) == ["achieve", "challenge"]


def test_multi_word_phrases_are_preserved():
    raw = "take responsibility\nmake progress"
    assert parse_vocabulary(raw) == ["take responsibility", "make progress"]


def test_quotes_and_trailing_punctuation_are_stripped():
    raw = '"achieve."\n“challenge”'
    assert parse_vocabulary(raw) == ["achieve", "challenge"]


def test_empty_input_is_rejected():
    with pytest.raises(VocabularyError):
        parse_vocabulary("   \n  \n")


def test_marker_only_input_is_rejected():
    with pytest.raises(VocabularyError):
        parse_vocabulary("1-\n2.\n-")


def test_non_string_input_is_rejected():
    with pytest.raises(VocabularyError):
        parse_vocabulary(None)  # type: ignore[arg-type]


def test_too_many_items_is_rejected():
    raw = "\n".join(f"word{i}" for i in range(6))
    with pytest.raises(VocabularyError, match="at most 5"):
        parse_vocabulary(raw, max_items=5)


def test_limit_is_configurable():
    raw = "\n".join(f"word{i}" for i in range(6))
    assert len(parse_vocabulary(raw, max_items=6)) == 6


def test_no_words_are_invented():
    raw = "1- achieve\n2- challenge"
    assert parse_vocabulary(raw) == ["achieve", "challenge"]
