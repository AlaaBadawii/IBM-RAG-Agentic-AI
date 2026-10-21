"""Run the ReAct agent on a sample question and pretty-print each step.

This is the main demonstration entry point. It performs live watsonx.ai and
Tavily calls, so it needs a populated ``.env`` and network access.

Usage (from the repository root, with the package installed)::

    python scripts/run_agent.py
"""

from langchain_core.messages import HumanMessage

from react_agent.graph import graph

QUESTION = (
    "What's the weather like in Zurich, and what should I wear based on the "
    "temperature?"
)


def print_stream(stream) -> None:
    """Print the newest message of every streamed graph state."""

    for step in stream:
        message = step["messages"][-1]
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()


def main() -> None:
    inputs = {"messages": [HumanMessage(content=QUESTION)]}
    print_stream(graph.stream(inputs, stream_mode="values"))


if __name__ == "__main__":
    main()
