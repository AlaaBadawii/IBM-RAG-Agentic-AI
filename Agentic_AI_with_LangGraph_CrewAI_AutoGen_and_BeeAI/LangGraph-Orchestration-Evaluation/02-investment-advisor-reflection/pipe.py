import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import get_llm
from prompt import grade_prompt, cathie_wood_prompt, ray_dalio_prompt, evaluator_prompt
from schemas import Feedback

# model client built at import time (no network request until a pipe is invoked);
# requires WATSONX_* environment variables - see ../.env.example
llm = get_llm()

grade_pipe = grade_prompt | llm
cathie_wood_pipe = cathie_wood_prompt | llm
ray_dalio_pipe = ray_dalio_prompt | llm
buffett_evaluator_pipe = evaluator_prompt | llm.with_structured_output(Feedback)
