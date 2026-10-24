import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import cast

from chain_state import ChainState
from llm import get_llm

llm = get_llm()


def generate_resume_summary(state: ChainState) -> ChainState:
    prompt = f"""
You're a resume assistant. Read the following job description and
summarize the key qualifications and experience the ideal candidate should have,
phrased as if from the perspective of a strong applicant's resume summary.
Job Description:
{state["job_description"]}
"""
    response = llm.invoke(prompt)

    return cast(
        ChainState,
        {**state, "resume_summary": cast(str, response.content)},
    )
