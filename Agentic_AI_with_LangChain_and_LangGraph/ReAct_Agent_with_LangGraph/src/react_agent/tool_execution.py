"""The ``tools`` node: execute the model's tool calls.

This node is the "act" half of the ReAct cycle. For every tool call in the last
``AIMessage`` it:

1. looks the tool up by name in the registry,
2. validates and runs it, and
3. returns a ``ToolMessage`` linked to the originating ``tool_call_id``.

The link matters: it is how the model associates a result with the call that
requested it. The node never raises for a bad tool call -- an unknown tool, a
malformed argument, or a tool failure all become an ``Error: ...`` string in the
``ToolMessage`` so the model can see the problem and try again.
"""

import json

from langchain_core.messages import AIMessage, ToolMessage

from .agent_state import AgentState
from .tools import tools_by_name


def stringify_result(result: object) -> str:
    """Serialize a tool result to a plain string.

    watsonx.ai accepts only string content (or content blocks carrying a
    ``type`` field) for a message. Tools such as the Tavily search tool return a
    list of dictionaries; sent verbatim, that list is rejected by the API with
    ``The Json field 'type' is required``. Strings pass through unchanged;
    everything else is JSON-encoded.
    """

    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False, default=str)


def tool_node(state: AgentState) -> dict:
    """Execute every tool call on the last message and return the results."""

    messages = state["messages"]
    if not messages or not isinstance(messages[-1], AIMessage):
        return {"messages": []}

    outputs = []
    for tool_call in messages[-1].tool_calls:
        name = tool_call.get("name")
        call_id = tool_call.get("id")
        args = tool_call.get("args")

        tool = tools_by_name.get(name)
        if tool is None:
            content = f"Error: unknown tool {name!r}."
        elif not isinstance(args, dict):
            content = f"Error: arguments for tool {name!r} must be an object."
        else:
            try:
                content = stringify_result(tool.invoke(args))
            except Exception as exc:  # noqa: BLE001 - surfaced to the model
                content = f"Error: tool {name!r} failed: {exc}"

        outputs.append(
            ToolMessage(content=content, name=name, tool_call_id=call_id)
        )

    return {"messages": outputs}
