from state import ReflectionState
from pipe import buffett_evaluator_pipe


def evaluate_plan(state: ReflectionState) -> dict:
    """Prompts an LLM to evaluate an investment plan based on the current state."""

    current_count = state.get("n", 0) + 1

    response = buffett_evaluator_pipe.invoke(
        {
            "investment_plan": state["investment_plan"],
            "investor_profile": state["investor_profile"],
            "target_grade": state["target_grade"],
        }
    )

    response_data = (
        response
        if isinstance(response, dict)
        else response.model_dump()
    )

    return {
        "grade": response_data["grade"],
        "feedback": response_data["feedback"],
        "n": current_count,
    }
