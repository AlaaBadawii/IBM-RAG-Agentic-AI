from state import ReflectionState
from pipe import grade_pipe


def determine_target_grade(state: ReflectionState):
    """Ask the LLM to pick the best-fitting target_grade."""
    response = grade_pipe.invoke({"investor_profile": state["investor_profile"]})

    # return as a plain dict so LangGraph can merge it into the state
    content = response.content
    if isinstance(content, list):
        content = "".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in content
        )

    return {"target_grade": str(content).lower()}


if __name__ == "__main__":
    # initialize empty state except for the user inputted investor profile
    dummy_state: ReflectionState = {
        "investment_plan": "",
        "investor_profile": (
            "Age: 29\n"
            "Salary: $110,000\n"
            "Assets: $40,000\n"
            "Goal: Achieve financial independence by age 45\n"
            "Risk tolerance: High"
        ),
        "target_grade": "MISSING",
        "feedback": "",
        "grade": "MISSING",
        "n": 0,
    }

    result = determine_target_grade(dummy_state)
    print({**dummy_state, **result})
