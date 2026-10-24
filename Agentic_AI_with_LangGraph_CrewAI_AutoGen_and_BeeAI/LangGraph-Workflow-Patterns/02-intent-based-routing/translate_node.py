import os
import sys
from typing import cast

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from router_state import RouterState
from llm import get_llm


def translate_node(state: RouterState) -> RouterState:
    llm = get_llm()
    prompt = f"Translate the following txt to France:\n\n{state['user_input']}"

    response = llm.invoke(prompt)

    return cast( RouterState,{**state, 'task_type': 'translate', 'output': response.content})
