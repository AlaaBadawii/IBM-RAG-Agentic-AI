"""Deep Research Reflexion Agent.

A small LangGraph reflexion workflow that drafts an answer, researches its own
critique with Tavily, and revises the answer with citations, backed by IBM
watsonx.ai.

Importing this package is intentionally side-effect free: it does not create a
watsonx client, contact IBM or Tavily, or build/run the graph. Import the
submodule you need, for example::

    from deep_research_agent.graph import app
    from deep_research_agent.llm import get_llm
"""

__version__ = "0.1.0"
