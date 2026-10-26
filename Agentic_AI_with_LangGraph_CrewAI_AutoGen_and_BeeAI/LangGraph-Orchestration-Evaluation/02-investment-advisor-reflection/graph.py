import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, START, END
from state import ReflectionState
from evaluate_plan import evaluate_plan
from route_investment import route_investment
from determine_target_grade import determine_target_grade
from investment_plan_generator import investment_plan_generator


optmizier_builder = StateGraph(ReflectionState)

optmizier_builder.add_node("determine_target_grade", determine_target_grade)
optmizier_builder.add_node("investment_plan_generator", investment_plan_generator)
optmizier_builder.add_node("evaluate_plan", evaluate_plan)

# define flow edges
optmizier_builder.add_edge(START, "determine_target_grade")
optmizier_builder.add_edge("determine_target_grade", "investment_plan_generator")
optmizier_builder.add_edge("investment_plan_generator", "evaluate_plan")

# add conditional edges based on the routing logic
optmizier_builder.add_conditional_edges(
    "evaluate_plan",
    lambda state: route_investment(state),
    {"Accepted": END, "Rejected + Feedback": "investment_plan_generator"},
)

optimizer_workflow = optmizier_builder.compile()


if __name__ == "__main__":
    from print_workflow_info import print_workflow_info

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "graph.png")
    print_workflow_info(optmizier_builder, optimizer_workflow, output_path=output_path)
