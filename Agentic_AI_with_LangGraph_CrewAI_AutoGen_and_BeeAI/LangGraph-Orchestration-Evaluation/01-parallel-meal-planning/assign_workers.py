from state import OrchestrationState
from langgraph.types import Send


def assign_workers(state: OrchestrationState):
    """Assign a worker to each section in the plan"""

    return [Send("chef_worker", {"section": s}) for s in state["sections"]]
