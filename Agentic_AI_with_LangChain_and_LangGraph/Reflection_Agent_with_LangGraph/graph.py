from collections.abc import Sequence
from typing import cast

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langgraph.graph import END, MessageGraph

from chains import generation_chain, reflection_chain

# Create a graph builder
graph = MessageGraph()


# Generating nodes
def generation_node(state: Sequence[AnyMessage]):
    generated_post = generation_chain.invoke({"messages": state})

    return [AIMessage(content=generated_post.content)]


def reflection_node(state: Sequence[AnyMessage]):
    reflection = reflection_chain.invoke({"messages": state})

    return [HumanMessage(content=reflection.content)]


# Add nodes to graph
graph.add_node("generate", generation_node)
graph.add_node("reflect", reflection_node)

# Set the entry point
graph.set_entry_point("generate")

# Add Edge
graph.add_edge("reflect", "generate")


# Define the router node
def should_continue(state: list[AnyMessage]):
    if len(state) > 6:
        return END

    return "reflect"


# Adding the router node
graph.add_conditional_edges("generate", should_continue)


# Complining the workflow
workflow = graph.compile()

if __name__ == "__main__":
    inputs = HumanMessage(
        content="""Write a linkedin post on getting a software developer job at IBM under 160 characters"""
    )

    response = workflow.invoke(inputs)

    final_post = cast(Sequence[AnyMessage], response)[-1].content

    print(final_post)