"""The ReAct chain: the prompt wired to the tool-bound chat model.

``bind_tools`` only *advertises* the tools to the model. It does not run them:
the model replies with an ``AIMessage`` whose ``tool_calls`` list names each
tool and its arguments. Executing those calls is the job of the ``tools`` node
(:mod:`react_agent.tool_execution`). This is the core ReAct insight -- the model
proposes, the graph disposes.

The chain is built lazily. Importing this module must not create the watsonx.ai
client (it needs credentials and, in principle, network access); the client is
only built when :func:`get_model_react` is first called at run time.
"""

from functools import lru_cache

from langchain_core.runnables import Runnable

from .llm import get_llm
from .prompt import chat_prompt
from .tools import tools


@lru_cache(maxsize=1)
def get_model_react() -> Runnable:
    """Return the cached ``prompt | model.bind_tools(tools)`` chain."""

    return chat_prompt | get_llm().bind_tools(tools)
