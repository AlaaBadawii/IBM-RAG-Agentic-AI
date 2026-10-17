"""Tavily web-search integration for the Deep Research Reflexion Agent.

This module deliberately lives in ``search.py`` rather than ``tavily.py``:
a local file called ``tavily.py`` would shadow the third-party ``tavily``
package (installed via ``tavily-python``) and break
``langchain_community``'s ``TavilySearchResults`` wrapper.
"""

import os

from dotenv import load_dotenv
from langchain_community.tools.tavily_search import TavilySearchResults

load_dotenv()

if not os.environ.get("TAVILY_API_KEY"):
    raise OSError(
        "TAVILY_API_KEY is not set in the environment. Copy .env.example to "
        ".env and add your own Tavily API key, or export TAVILY_API_KEY "
        "before running the agent."
    )


tavily_tool = TavilySearchResults(max_results=3)


if __name__ == "__main__":
    # Smoke-test the Tavily wrapper. This performs a real network request and
    # therefore requires valid Tavily credentials.
    query = "healthy breakfast recipes"
    result = tavily_tool.invoke(query)
    print(f"Query: {query}\nResult: {result}")
