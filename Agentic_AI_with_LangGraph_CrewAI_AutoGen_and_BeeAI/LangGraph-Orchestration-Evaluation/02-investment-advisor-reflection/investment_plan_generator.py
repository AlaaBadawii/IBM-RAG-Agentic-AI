from state import ReflectionState
from pipe import cathie_wood_pipe, ray_dalio_pipe


def investment_plan_generator(state: ReflectionState) -> dict:
    """Prompts an LLM to generate or improve an investment plan based on the current state."""

    if state.get("feedback"):
        # use Ray Dalio–style generator when feedback is available
        response = ray_dalio_pipe.invoke(
            {
                "investor_profile": state["investor_profile"],
                "grade": state["grade"],
                "feedback": state["feedback"],
            }
        )
    else:
        # use Cathie Wood–style generator for initial plan
        response = cathie_wood_pipe.invoke(
            {"investor_profile": state["investor_profile"]}
        )

    return {"investment_plan": response.content}


if __name__ == "__main__":
    # get the investment plan
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

    initial_investment_plan = investment_plan_generator(dummy_state)
    # update the dummy state with generated plan
    dummy_state.update(initial_investment_plan)
    print(f"Investment Plan: {dummy_state['investment_plan']}")
    print(f"Investor Profile: {dummy_state['investor_profile']}")

