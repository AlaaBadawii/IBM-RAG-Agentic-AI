from router_state import RouterState
from llm_router import llm_router


def router_node(state: RouterState):
    routing_prompt = f"""
    You are an AI task classifier.

    Decide whether the user wants to:
    - "summarize" a passage
    - or "translate" text into French
    
    Respond with just one word: 'summarize' or 'translate'.
    
    User Input: "{state["user_input"]}"
    """

    response = llm_router.invoke(routing_prompt)

    if response.tool_calls:
        task_type = response.tool_calls[0]["args"]["role"]
    else:
        text = (response.content or "").strip().lower()
        if "translate" in text:
            task_type = "translate"
        elif "summarize" in text:
            task_type = "summarize"
        else:
            task_type = text if text in ("translate", "summarize") else "summarize"

    return {**state, "task_type": task_type}
