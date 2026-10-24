import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from state import State
from llm import get_llm


def translate_french(state: State) -> dict:
    response = get_llm().invoke(
        f"Translate the following text to French:\n\n{state['text']}"
    )

    return {"french": response.content.strip()}
