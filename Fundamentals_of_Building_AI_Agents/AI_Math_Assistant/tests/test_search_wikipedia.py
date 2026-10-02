from unittest.mock import MagicMock, patch

from src.tools import search_wikipedia


def test_search_wikipedia_returns_summary():
    mock_wrapper = MagicMock()
    mock_wrapper.run.return_value = "Python is a programming language."
    with patch("src.tools.WikipediaAPIWrapper", return_value=mock_wrapper) as mock_cls:
        result = search_wikipedia.invoke({"query": "Python programming"})

    mock_cls.assert_called_once()
    mock_wrapper.run.assert_called_once_with("Python programming")
    assert result == "Python is a programming language."
    assert isinstance(result, str)


def test_search_wikipedia_forwards_query():
    mock_wrapper = MagicMock()
    mock_wrapper.run.return_value = "Paris is the capital of France."
    with patch("src.tools.WikipediaAPIWrapper", return_value=mock_wrapper):
        result = search_wikipedia.invoke({"query": "Capital of France"})

    mock_wrapper.run.assert_called_once_with("Capital of France")
    assert "Paris" in result


def test_search_wikipedia_tool_metadata():
    assert search_wikipedia.name == "search_wikipedia"
    assert "query" in search_wikipedia.args
