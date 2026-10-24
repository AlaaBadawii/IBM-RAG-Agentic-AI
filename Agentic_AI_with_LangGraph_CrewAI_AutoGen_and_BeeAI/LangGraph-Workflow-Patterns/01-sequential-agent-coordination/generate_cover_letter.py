import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import cast

from chain_state import ChainState
from llm import get_llm

llm = get_llm()


def generate_cover_letter(state: ChainState) -> ChainState:
    prompt = f"""
You're a cover letter writing assistant. Using the resume summary below,
write a professional and personalized cover letter for the following job.
Resume Summary:
{state["resume_summary"]}

Job Description:
{state["job_description"]}
"""
    response = llm.invoke(prompt)

    return cast(
        ChainState,
        {**state, "cover_letter": cast(str, response.content)},
    )
