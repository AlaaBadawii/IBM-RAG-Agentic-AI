"""Deep Research Reflexion Agent graph.

The workflow is a small reflection loop built with LangGraph's ``MessageGraph``:

    respond -> execute_tools -> revisor -> (execute_tools | END)

* ``respond`` writes an initial answer plus a self-critique and 1-3 search
  queries (an ``AnswerQuestion`` tool call).
* ``execute_tools`` runs those queries through Tavily and returns the results
  as ``ToolMessage`` objects.
* ``revisor`` rewrites the answer using the research results (a
  ``ReviseAnswer`` tool call) and proposes a fresh set of queries.
* ``event_loop`` routes back to ``execute_tools`` until ``MAX_ITERATIONS``
  rounds of tool messages have accumulated, then ends the run.
"""

from langchain_core.messages import HumanMessage
from langgraph.graph import END, MessageGraph

from .event_loop import event_loop
from .execute_tools import execute_tools
from .responder import responder_chain
from .revisor import revisor_chain


def build_graph():
    """Construct and compile the reflection workflow."""

    graph = MessageGraph()
    graph.add_node("respond", responder_chain)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("revisor", revisor_chain)
    graph.add_edge("respond", "execute_tools")
    graph.add_edge("execute_tools", "revisor")
    graph.add_conditional_edges(
        "revisor",
        event_loop,
        {"execute_tools": "execute_tools", END: END},
    )
    graph.set_entry_point("respond")
    return graph.compile()


def extract_answers(messages) -> list[str]:
    """Return every ``answer`` field found in the message history, in order.

    The initial draft is first and the final revised answer is last. Messages
    without tool calls, or tool calls without an ``answer`` argument, are
    ignored.
    """

    answers = []
    for message in messages:
        if isinstance(message, str):
            continue
        for tool_call in getattr(message, "tool_calls", None) or []:
            answer = (tool_call.get("args") or {}).get("answer")
            if answer:
                answers.append(answer)
    return answers


app = build_graph()


if __name__ == "__main__":
    question = (
        "I'm pre-diabetic and need to lower my blood sugar, and I have heart "
        "issues. What breakfast foods should I eat and avoid?"
    )

    responses = app.invoke([HumanMessage(content=question)])
    answers = extract_answers(responses)

    print("--- Initial Draft Answer ---")
    print(answers[0] if answers else "No initial answer found.")
    print()

    print("--- Final Revised Answer with References ---")
    print(answers[-1] if answers else "No revised answer found.")
