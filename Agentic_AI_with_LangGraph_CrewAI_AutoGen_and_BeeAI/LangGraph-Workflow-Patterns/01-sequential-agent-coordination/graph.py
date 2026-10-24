import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from print_workflow_info import print_workflow_info

from langgraph.graph import StateGraph
from chain_state import ChainState
from generate_cover_letter import generate_cover_letter
from generate_resume_summary import generate_resume_summary


workflow = StateGraph(ChainState)

workflow.add_node("generate_resume_summary", generate_resume_summary)
workflow.add_node("generate_cover_letter", generate_cover_letter)

workflow.set_entry_point("generate_resume_summary")

workflow.add_edge("generate_resume_summary", "generate_cover_letter")

workflow.set_finish_point("generate_cover_letter")

app = workflow.compile()


if __name__ == "__main__":
    print_workflow_info(workflow, app, output_path=os.path.join(os.path.dirname(__file__), "graph.png"))
