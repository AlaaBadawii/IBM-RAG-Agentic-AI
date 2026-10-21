"""News summarizer: parsing, metadata handling, grounding, and errors."""

import json

from langchain_core.messages import AIMessage

import react_agent.tools.summarizer as ns


class _FakeLLM:
    def __init__(self, content="SUMMARY", error=None):
        self.content = content
        self.error = error
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        if self.error is not None:
            raise self.error
        return AIMessage(content=self.content)


def _patch_llm(monkeypatch, fake):
    monkeypatch.setattr(ns, "get_llm", lambda: fake)


def test_empty_input_returns_a_message_without_calling_the_model(monkeypatch):
    def _forbidden():
        raise AssertionError("the model must not be called for empty input")

    monkeypatch.setattr(ns, "get_llm", _forbidden)

    assert ns.news_summarizer.invoke({"articles": ""}) == (
        "No articles were provided to summarize."
    )
    assert ns.news_summarizer.invoke({"articles": "   "}) == (
        "No articles were provided to summarize."
    )
    assert ns.news_summarizer.invoke({"articles": "[]"}) == (
        "No articles were provided to summarize."
    )


def test_summarizes_multiple_articles(monkeypatch):
    fake = _FakeLLM(content="SUMMARY")
    _patch_llm(monkeypatch, fake)
    articles = json.dumps(
        [
            {"title": "First", "url": "https://a.example", "date": "2026-01-01", "content": "alpha"},
            {"title": "Second", "url": "https://b.example", "content": "beta"},
        ]
    )

    result = ns.news_summarizer.invoke({"articles": articles})

    assert result == "SUMMARY"
    human_text = fake.calls[0][1].content
    assert "First" in human_text
    assert "Second" in human_text
    assert "https://a.example" in human_text


def test_missing_date_and_url_are_marked(monkeypatch):
    fake = _FakeLLM(content="SUMMARY")
    _patch_llm(monkeypatch, fake)
    articles = json.dumps([{"title": "No metadata", "content": "body"}])

    ns.news_summarizer.invoke({"articles": articles})

    human_text = fake.calls[0][1].content
    assert "Date: (not provided)" in human_text
    assert "Source URL: (not provided)" in human_text


def test_plain_text_input_is_accepted(monkeypatch):
    fake = _FakeLLM(content="SUMMARY")
    _patch_llm(monkeypatch, fake)

    ns.news_summarizer.invoke({"articles": "Just a paragraph of news."})

    human_text = fake.calls[0][1].content
    assert "Just a paragraph of news." in human_text


def test_summarization_error_is_returned_as_a_string(monkeypatch):
    _patch_llm(monkeypatch, _FakeLLM(error=RuntimeError("model exploded")))

    result = ns.news_summarizer.invoke({"articles": "some article"})

    assert result.startswith("Error: failed to summarize articles:")
    assert "model exploded" in result


def test_system_prompt_demands_evidence_grounded_summaries():
    prompt = ns.SYSTEM_PROMPT
    assert "Never invent" in prompt
    assert "date not provided" in prompt
    assert "URL not provided" in prompt


def test_build_summary_messages_has_system_and_human_turns():
    messages = ns.build_summary_messages("Article 1:\nTitle: X")
    assert messages[0].type == "system"
    assert messages[1].type == "human"
    assert "Article 1" in messages[1].content
