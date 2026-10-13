import warnings

from ibm_watsonx_ai.utils.warnings import WatsonxAPIWarning

warnings.filterwarnings(
    "ignore",
    message=r"The value of 'max_tokens'.*",
    category=WatsonxAPIWarning,
)

from typing import TypedDict

from langgraph.graph import END, StateGraph

from llm import llm


class QAState(TypedDict):
    # it stores the user's question.
    question: str | None
    # stores relevant context about the guided project.
    context: str | None
    # stores the generated answer.
    answer: str | None


qa_state_example = QAState(
    question="What is the purpose of this guided project?",
    context="This project focuses on building a chatbot using Python.",
    answer=None,
)


def input_validation_node(state):
    question = state.get("question", "")

    if not question:
        return {"valid": False, "error": "Question cannot be empty."}

    return {"valid": True}


def context_provide_node(state):
    question = state.get("question", "").lower()
    if "langgraph" in question or "guided project" in question:
        context = (
            "This guided project is about using LangGraph, a Python library to design state-based workflows. "
            "LangGraph simplifies building complex applications by connecting modular nodes with conditional edges."
        )

        return {"context": context}

    return {"context": None}


def llm_qa_node(state):
    question = state.get("question", "")
    context = state.get("context", None)

    if not context:
        return {"answer": "I don't have enough context to answer your question."}

    prompt = f"Context: {context}\nQuestion: {question}\nnAnswer the question based on the provided context."

    try:
        response = llm.invoke(prompt)
        response = getattr(response, "content", str(response))
        return {"answer": response.strip()}
    except (ValueError, TypeError, RuntimeError) as e:
        return {"answer": f"An error occurred: {e!s}"}

qa_workflow = StateGraph(QAState)

qa_workflow.add_node("InputNode", input_validation_node)
qa_workflow.add_node("ContextNode", context_provide_node)
qa_workflow.add_node("QANode", llm_qa_node)

qa_workflow.set_entry_point("InputNode")

qa_workflow.add_edge("InputNode", "ContextNode")
qa_workflow.add_edge("ContextNode", "QANode")

qa_workflow.add_edge("QANode", END)

app = qa_workflow.compile()

if __name__ == "__main__":
    # Example usage
    inputs = {"question": "What is LangGraph?"}
    result = app.invoke(inputs)
    print(result)

