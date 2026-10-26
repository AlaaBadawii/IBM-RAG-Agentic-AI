from state import ReflectionState

def route_investment(state: ReflectionState, iteration_limit: int = 5):
    """Route investment based on risk grade evaluation"""
    # get grades
    current_grade = state.get("grade", "MISSING")
    target_grade = state.get("target_grade", "MISSING")
    # check if grades match
    match = current_grade == target_grade

    # print out the tracked values
    print("=== ROUTING  ===")
    print(f"Current grade: '{current_grade}'")
    print(f"Target risk profile: '{target_grade}'")
    print(f"Match: {match}")
    print(f"Number of trials: {state['n']}")

    # routing logic
    if match:  # grades match
        print("→ Routing to: Accepted")
        return "Accepted"
    elif state["n"] > iteration_limit:  # review iterations exceeds limit
        print("→ Too many iterations, stopping")
        return "Accepted"
    else:  # grades don't match
        print("→ Routing to: Rejected + Feedback")
        return "Rejected + Feedback"

