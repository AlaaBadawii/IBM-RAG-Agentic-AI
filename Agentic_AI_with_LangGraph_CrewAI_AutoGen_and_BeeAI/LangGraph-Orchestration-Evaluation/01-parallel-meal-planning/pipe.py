import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import get_llm
from schemas import Dishes
from prompt import dish_prompt, chef_prompt

# model client built at import time (no network request until a pipe is invoked);
# requires WATSONX_* environment variables - see ../.env.example
llm = get_llm()

planner_pipe = dish_prompt | llm.with_structured_output(Dishes)
chef_pipe = chef_prompt | llm
