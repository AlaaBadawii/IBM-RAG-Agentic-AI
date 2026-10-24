import os
import sys
from pydantic import BaseModel, Field

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import get_llm

llm = get_llm()


class Router(BaseModel):
    role: str = Field(
        ...,
        description="Decide whether the user wants to summarize a passage  ouput 'summarize'  or translate text into French oupput translate.",
    )

llm_router = llm.bind_tools([Router])

if __name__ == "__main__":
    response = llm_router.invoke("summarize this I love the sun its so warm")
    print(response)