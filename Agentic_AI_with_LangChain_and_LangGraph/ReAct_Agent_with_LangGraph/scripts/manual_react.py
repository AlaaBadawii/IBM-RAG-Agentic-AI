"""Run the ReAct cycle by hand, without LangGraph's compiled graph.

This script exists for learning: it shows exactly what the graph nodes do,
step by step, so the "magic" of ``graph.invoke`` is demystified. It is *not*
the recommended way to run the agent -- :mod:`react_agent.graph` is -- but it
makes the loop explicit.

It performs live watsonx.ai and Tavily calls and therefore needs a populated
``.env`` and network access.

Usage (from the repository root, with the package installed)::

    python scripts/manual_react.py
"""

from typing import cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.graph.message import add_messages

from react_agent.model_react import get_model_react
from react_agent.should_continue import should_continue
from react_agent.tools import tools_by_name
from react_agent.tool_execution import stringify_result

QUESTION = "What's the weather in Zurich, and what should I wear?"
MAX_STEPS = 6


def main() -> None:
    messages: list[BaseMessage] = [HumanMessage(content=QUESTION)]
    model = get_model_react()

    for step in range(1, MAX_STEPS + 1):
        print(f"\n===== Step {step}: ask the model =====")
        response = cast(AIMessage, model.invoke({"scratch_pad": messages}))
        messages = list(add_messages(messages, [response]))

        # would_continue inspects the last message and the tool history.
        decision = should_continue({"messages": messages})
        if not response.tool_calls or decision == "end":
            print("\n===== Final answer =====")
            print(response.content)
            return

        print(f"Model requested {len(response.tool_calls)} tool call(s).")
        outputs = []
        for tool_call in response.tool_calls:
            name = tool_call["name"]
            tool = tools_by_name.get(name)
            if tool is None:
                content = f"Error: unknown tool {name!r}."
            else:
                try:
                    content = stringify_result(tool.invoke(tool_call["args"]))
                except Exception as exc:  # noqa: BLE001 - surfaced to the model
                    content = f"Error: tool {name!r} failed: {exc}"
            print(f"  {name}({tool_call['args']}) -> {content}")
            outputs.append(
                ToolMessage(
                    content=content, name=name, tool_call_id=tool_call["id"]
                )
            )

        messages = list(add_messages(messages, outputs))

    print("\nReached the step limit without a final answer.")


if __name__ == "__main__":
    main()
