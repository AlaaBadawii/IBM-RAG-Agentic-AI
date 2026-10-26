import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Any, cast

from langgraph.graph import StateGraph, END, START
from state import OrchestrationState
from orchestrator import orchestrator
from chef_worker import chef_worker
from synthesizer import synthesizer
from assign_workers import assign_workers

# instantiate the builder
orchestrator_worker_builder = StateGraph(OrchestrationState)

# add the nodes
orchestrator_worker_builder.add_node("orchestrator", orchestrator)
orchestrator_worker_builder.add_node("chef_worker", chef_worker)
orchestrator_worker_builder.add_node("synthesizer", synthesizer)

orchestrator_worker_builder.add_conditional_edges(
    "orchestrator",
    cast(Any, assign_workers),
    ["chef_worker"],  # source node, routing function, list of allowed targets
)

# add the edges, connections between nodes
orchestrator_worker_builder.add_edge(START, "orchestrator")
orchestrator_worker_builder.add_edge("chef_worker", "synthesizer")
orchestrator_worker_builder.add_edge("synthesizer", END)

# compile the builder to get a complete workflow executable
orchestrator_worker = orchestrator_worker_builder.compile()


if __name__ == "__main__":
    from print_workflow_info import print_workflow_info

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "graph.png")
    print_workflow_info(orchestrator_worker_builder, orchestrator_worker, output_path=output_path)
