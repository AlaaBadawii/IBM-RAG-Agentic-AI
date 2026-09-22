"""Tests for the prompt builder."""
from src.prompts.vision import CAPTION_PROMPT, QUESTION_ANSWERING_PROMPT, COUNTING_PROMPT, EXTRACTION_PROMPT, ASSESSMENT_PROMPT
from src.images.build_image_message import build_image_message


def test_caption_prompt_is_string():
    assert isinstance(CAPTION_PROMPT, str)
    assert len(CAPTION_PROMPT) > 0


def test_question_answering_prompt_is_string():
    assert isinstance(QUESTION_ANSWERING_PROMPT, str)


def test_counting_prompt_is_string():
    assert isinstance(COUNTING_PROMPT, str)


def test_extraction_prompt_is_string():
    assert isinstance(EXTRACTION_PROMPT, str)


def test_assessment_prompt_is_string():
    assert isinstance(ASSESSMENT_PROMPT, str)
    assert "damage" in ASSESSMENT_PROMPT


def test_build_image_message_structure():
    data_url = "data:image/png;base64,abc123"
    question = "What is in this image?"
    messages = build_image_message(data_url, question)
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    content = messages[0]["content"]
    assert len(content) == 2
    assert content[0]["type"] == "text"
    assert content[0]["text"] == question
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"] == data_url


def test_build_image_message_multiple_questions():
    data_url = "data:image/jpeg;base64,xyz"
    msg1 = build_image_message(data_url, "Count the cars.")
    msg2 = build_image_message(data_url, "Describe the scene.")
    assert msg1[0]["content"][0]["text"] != msg2[0]["content"][0]["text"]
    assert msg1[0]["content"][1]["image_url"]["url"] == msg2[0]["content"][1]["image_url"]["url"]
