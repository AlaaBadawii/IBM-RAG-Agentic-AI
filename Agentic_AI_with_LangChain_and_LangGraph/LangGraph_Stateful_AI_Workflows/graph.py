from langgraph.graph import END, StateGraph

from states import (
    AuthState,
    failure_node,
    input_node,
    router,
    success_node,
    validate_credentials_node,
)

# Create an instance of StateGraph with the GraphState structure
workflow = StateGraph(AuthState)

# Add Nodes
workflow.add_node("InputNode", input_node)
workflow.add_node("ValidateCredential", validate_credentials_node)
workflow.add_node("Success", success_node)
workflow.add_node("Failuer", failure_node)

# Add edges
workflow.add_edge("InputNode", "ValidateCredential")
workflow.add_edge("Success", END)
workflow.add_edge("Failuer", "InputNode")
workflow.add_conditional_edges(
    "ValidateCredential", router, {
        "success_node": "Success",
        "failure_node": "Failuer"
    }
)

# Add Start point
workflow.set_entry_point("InputNode")

