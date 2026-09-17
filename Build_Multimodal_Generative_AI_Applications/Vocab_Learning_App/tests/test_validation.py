"""Tests for structured-response validation and vocabulary coverage."""

import pytest

from src.validation import (
    contains_term,
    find_missing_terms,
    lesson_with_story,
    validate_payload,
)


def make_payload(words, story="A story that mentions achieve, challenge and confident."):
    return {
        "words": [
            {
                "word": word,
                "definition": f"Definition of {word}.",
                "examples": [f"First example for {word}.", f"Second example for {word}."],
            }
            for word in words
        ],
        "story": story,
    }


def test_valid_payload_passes():
    payload = make_payload(["achieve", "challenge", "confident"])
    result = validate_payload(payload, ["achieve", "challenge", "confident"])
    assert result.ok
    assert result.lesson is not None
    assert [entry.word for entry in result.lesson.words] == [
        "achieve",
        "challenge",
        "confident",
    ]


def test_entries_are_reordered_and_respelled_to_match_the_request():
    payload = {
        "words": [
            {"word": "Confident", "definition": "d", "examples": ["a", "b"]},
            {"word": "achieve", "definition": "d", "examples": ["a", "b"]},
        ],
        "story": "achieve and confident",
    }
    result = validate_payload(payload, ["achieve", "confident"])
    assert result.lesson is not None
    # The user's own spelling wins, and order follows the user's list.
    assert [entry.word for entry in result.lesson.words] == ["achieve", "confident"]


def test_three_examples_are_trimmed_to_two():
    payload = make_payload(["achieve"])
    payload["words"][0]["examples"] = ["one", "two", "three"]
    result = validate_payload(payload, ["achieve"])
    assert result.lesson is not None
    assert len(result.lesson.words[0].examples) == 2


def test_single_example_is_a_structural_error():
    payload = make_payload(["achieve"])
    payload["words"][0]["examples"] = ["only one"]
    result = validate_payload(payload, ["achieve"])
    assert result.lesson is None
    assert any("fewer than 2" in error for error in result.structural_errors)


def test_missing_required_field_is_a_structural_error():
    payload = make_payload(["achieve"])
    del payload["words"][0]["definition"]
    result = validate_payload(payload, ["achieve"])
    assert result.lesson is None
    assert any("definition" in error for error in result.structural_errors)


def test_missing_story_is_a_structural_error():
    payload = make_payload(["achieve"])
    payload["story"] = ""
    result = validate_payload(payload, ["achieve"])
    assert result.lesson is None
    assert any("story" in error for error in result.structural_errors)


def test_word_absent_from_the_lesson_is_reported():
    payload = make_payload(["achieve"], story="achieve and challenge")
    result = validate_payload(payload, ["achieve", "challenge"])
    assert result.lesson is None
    assert result.missing_in_lesson == ("challenge",)


def test_word_absent_from_the_story_is_reported():
    payload = make_payload(["achieve", "challenge"], story="Only achieve appears here.")
    result = validate_payload(payload, ["achieve", "challenge"])
    assert result.lesson is not None
    assert result.missing_in_story == ("challenge",)


def test_non_dict_payload_is_rejected():
    result = validate_payload("not a dict", ["achieve"])
    assert result.lesson is None
    assert result.structural_errors


def test_non_list_words_is_rejected():
    result = validate_payload({"words": {}, "story": "x"}, ["achieve"])
    assert result.lesson is None


def test_entry_that_is_not_an_object_is_rejected():
    result = validate_payload({"words": ["achieve"], "story": "achieve"}, ["achieve"])
    assert result.lesson is None


def test_lesson_with_story_revalidates_coverage():
    payload = make_payload(["achieve", "challenge"], story="Only achieve appears here.")
    result = validate_payload(payload, ["achieve", "challenge"])
    assert result.lesson is not None

    revised = lesson_with_story(
        result.lesson, "Now both achieve and challenge appear.", ["achieve", "challenge"]
    )
    assert revised.ok
    assert revised.lesson is not None
    assert revised.lesson.story == "Now both achieve and challenge appear."


def test_lesson_with_empty_story_returns_no_lesson():
    payload = make_payload(["achieve"])
    result = validate_payload(payload, ["achieve"])
    assert result.lesson is not None
    assert lesson_with_story(result.lesson, "   ", ["achieve"]).lesson is None


# --------------------------------------------------------------------------- #
# Coverage matching
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("story", "term"),
    [
        ("She achieved her goal.", "achieve"),
        ("They are achieving a lot.", "achieve"),
        ("He took responsibility for it.", "take responsibility"),
        ("She is confident about it.", "confident"),
        ("One child waited.", "child"),
        ("The children waited.", "child"),
    ],
)
def test_inflected_forms_count_as_coverage(story, term):
    assert contains_term(story, term)


@pytest.mark.parametrize(
    ("story", "term"),
    [
        ("She worked hard.", "achieve"),
        ("He took the blame.", "take responsibility"),
        ("The story mentions nothing relevant.", "opportunity"),
    ],
)
def test_absent_terms_are_detected(story, term):
    assert not contains_term(story, term)


def test_find_missing_terms_keeps_requested_order():
    story = "This mentions achieve and confident."
    assert find_missing_terms(story, ["achieve", "challenge", "confident"]) == ("challenge",)


def test_empty_text_has_no_coverage():
    assert not contains_term("", "achieve")
    assert find_missing_terms("", ["achieve"]) == ("achieve",)
