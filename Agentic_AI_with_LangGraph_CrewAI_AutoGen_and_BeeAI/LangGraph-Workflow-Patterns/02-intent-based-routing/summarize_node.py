import os
import sys
from typing import cast

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from router_state import RouterState
from llm import get_llm


def summarize_node(state: RouterState) -> RouterState:
    llm = get_llm()

    prompt = f"Please summarize the following passage: \n\n{state['user_input']}"

    response = llm.invoke(prompt)

    return cast(RouterState, {**state, "task_type": "summarize", "output": response.content})
