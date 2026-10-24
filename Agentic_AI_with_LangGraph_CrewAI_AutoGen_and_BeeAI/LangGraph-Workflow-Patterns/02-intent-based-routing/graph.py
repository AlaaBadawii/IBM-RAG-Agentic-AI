import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from print_workflow_info import print_workflow_info

from langgraph.graph import StateGraph
from router_state import RouterState

from router_node import router_node
from summarize_node import summarize_node
from translate_node import translate_node
from router import router


workflow = StateGraph(RouterState)


workflow.add_node("router", router_node)
workflow.add_node("summarize", summarize_node)
workflow.add_node("translate", translate_node)

workflow.set_entry_point("router")

workflow.add_conditional_edges(
    "router", router,
    {"summarize": "summarize", "translate": "translate"},
)

workflow.set_finish_point("summarize")
workflow.set_finish_point("translate")


app = workflow.compile()


if __name__ == "__main__":
    print_workflow_info(workflow, app, output_path=os.path.join(os.path.dirname(__file__), "graph.png"))
