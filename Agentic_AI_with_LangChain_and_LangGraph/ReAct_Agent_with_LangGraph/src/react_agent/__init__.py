"""A small, educational ReAct agent built with LangGraph and IBM watsonx.ai.

The package is intentionally import-safe: importing :mod:`react_agent` (or any
of its submodules) never authenticates with IBM Cloud, never constructs a
watsonx.ai client, and never contacts the network. The chat model, the Tavily
search client, and the summarizer chain are all created lazily on first use.

See ``README.md`` for the learning objectives and a guided tour of the code.
"""

__version__ = "0.1.0"
