import pytest
from pydantic import ValidationError

from deep_research_agent.schema import AnswerQuestion, Reflection, ReviseAnswer


def test_valid_answer_question_parses_nested_reflection():
    answer = AnswerQuestion(
        answer="Eat eggs.",
        reflection={"missing": "evidence", "superfluous": "opinions"},
        search_queries=["egg nutrition", "breakfast trials"],
    )

    assert answer.answer == "Eat eggs."
    assert isinstance(answer.reflection, Reflection)
    assert answer.reflection.missing == "evidence"
    assert answer.reflection.superfluous == "opinions"
    assert answer.search_queries == ["egg nutrition", "breakfast trials"]


def test_answer_question_requires_every_field():
    with pytest.raises(ValidationError):
        AnswerQuestion(answer="only an answer")

    with pytest.raises(ValidationError):
        AnswerQuestion(
            answer="a",
            reflection={"missing": "m"},
            search_queries=["q"],
        )


def test_reflection_requires_both_fields():
    assert Reflection(missing="m", superfluous="s").missing == "m"

    with pytest.raises(ValidationError):
        Reflection(missing="m")


@pytest.mark.parametrize("bad_value", ["not-a-list", [1, 2], None, 5])
def test_search_queries_must_be_a_list_of_strings(bad_value):
    with pytest.raises(ValidationError):
        AnswerQuestion(
            answer="a",
            reflection={"missing": "m", "superfluous": "s"},
            search_queries=bad_value,
        )


def test_nested_reflection_rejects_wrong_types():
    with pytest.raises(ValidationError):
        AnswerQuestion(
            answer="a",
            reflection="not-an-object",
            search_queries=["q"],
        )


def test_revise_answer_extends_answer_question_with_references():
    revised = ReviseAnswer(
        answer="revised",
        reflection={"missing": "m", "superfluous": "s"},
        search_queries=["q"],
        references=["[1] https://example.com"],
    )

    assert isinstance(revised, AnswerQuestion)
    assert revised.references == ["[1] https://example.com"]


def test_revise_answer_requires_references():
    with pytest.raises(ValidationError):
        ReviseAnswer(
            answer="revised",
            reflection={"missing": "m", "superfluous": "s"},
            search_queries=["q"],
        )
