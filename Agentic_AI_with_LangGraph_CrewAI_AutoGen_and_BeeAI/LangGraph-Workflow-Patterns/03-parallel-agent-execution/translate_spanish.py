import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from state import State
from llm import get_llm


def translate_spanish(state: State) -> dict:
    response = get_llm().invoke(
        f"Translate the following text to Spanish:\n\n{state['text']}"
    )

    return {"spanish": response.content.strip()}
