"""Search tool: lazy client, actionable error, delegated search."""

import pytest

from react_agent.tools import web_search as search_tool_module


def test_missing_key_raises_actionable_error(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    search_tool_module._get_search_client.cache_clear()

    with pytest.raises(OSError) as excinfo:
        search_tool_module._get_search_client()

    message = str(excinfo.value)
    assert "TAVILY_API_KEY" in message
    assert ".env.example" in message


def test_tool_delegates_to_the_search_client(monkeypatch):
    class _FakeClient:
        def __init__(self):
            self.queries = []

        def invoke(self, query):
            self.queries.append(query)
            return [{"title": "t", "url": "u", "content": "c", "score": 1.0}]

    fake = _FakeClient()
    monkeypatch.setattr(search_tool_module, "_get_search_client", lambda: fake)

    result = search_tool_module.search_tool.invoke({"query": "weather Zurich"})

    assert result == [{"title": "t", "url": "u", "content": "c", "score": 1.0}]
    assert fake.queries == ["weather Zurich"]
