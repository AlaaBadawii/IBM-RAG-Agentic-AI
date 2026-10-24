import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from print_workflow_info import print_workflow_info


from langgraph.graph import StateGraph, START, END
from state import State

from translate_french import translate_french
from translate_spanish import translate_spanish
from translate_japanese import translate_japanese
from aggregator import aggregator

graph = StateGraph(State)

graph.add_node("translate_french", translate_french)
graph.add_node("translate_spanish", translate_spanish)
graph.add_node("translate_japanese", translate_japanese)
graph.add_node("aggregator", aggregator)

# Connect parallel translation nodes from START
graph.add_edge(START, "translate_french")
graph.add_edge(START, "translate_spanish")
graph.add_edge(START, "translate_japanese")

# Connect translation nodes to aggregator
graph.add_edge("translate_french", "aggregator")
graph.add_edge("translate_spanish", "aggregator")
graph.add_edge("translate_japanese", "aggregator")

graph.add_edge("aggregator", END)

app = graph.compile()


if __name__ == "__main__":
    print_workflow_info(graph, app, output_path=os.path.join(os.path.dirname(__file__), "graph.png"))