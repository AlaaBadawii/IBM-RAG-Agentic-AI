from state import OrchestrationState
from pipe import planner_pipe


def orchestrator(state: OrchestrationState):
    """
    Orchestrator that generates a structured dish list from the given meals.
    """
    dish_secriptions = planner_pipe.invoke({"meals": state["meals"]})

    sections = (
        dish_secriptions.get("sections")
        if isinstance(dish_secriptions, dict)
        else getattr(dish_secriptions, "sections", None)
    )

    return {"sections": sections}

