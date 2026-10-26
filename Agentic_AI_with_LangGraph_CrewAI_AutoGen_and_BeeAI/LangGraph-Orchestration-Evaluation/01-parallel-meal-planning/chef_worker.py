from state import WorkerState
from pipe import chef_pipe


def chef_worker(state: WorkerState):
    """Worker node that generates the cooking instructions for one meal section."""

    meal_plan = chef_pipe.invoke(
        {
            "name": state["section"].name,
            "location": state["section"].location,
            "ingredients": state["section"].ingredients,
        }
    )

    # Return the generated meal plan wrapped in a list under completed_sections
    # This will be merged into the main state using operator.add in LangGraph
    return {"completed_menu": [meal_plan.content]}

