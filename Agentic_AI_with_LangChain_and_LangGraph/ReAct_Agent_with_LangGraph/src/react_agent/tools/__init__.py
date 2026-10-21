"""Tool registry for the ReAct agent.

Adding a tool is deliberately a two-line change: decorate a function with
``@tool`` in its own module, import it here, and add it to ``tools``. The
``tools_by_name`` mapping is what :mod:`react_agent.tool_execution` uses to turn
a model's ``tool_calls`` entry into a real Python call.

Module names (``web_search``, ``clothing``, ``arithmetic``, ``summarizer``)
deliberately differ from the tool function names (``search_tool``,
``remommend_clothing``, ``calculator``, ``news_summarizer``). Importing a tool
function into this package would otherwise shadow the submodule of the same
name, so ``import react_agent.tools.search_tool`` would silently return the tool
instead of the module.
"""

from .arithmetic import calculator
from .clothing import remommend_clothing
from .summarizer import news_summarizer
from .web_search import search_tool

tools = [
    remommend_clothing,
    search_tool,
    calculator,
    news_summarizer,
]

tools_by_name = {tool.name: tool for tool in tools}

__all__ = [
    "calculator",
    "news_summarizer",
    "remommend_clothing",
    "search_tool",
    "tools",
    "tools_by_name",
]
