from leftover import LeftoversCrew
from llm import get_llm

leftpvers_cb = LeftoversCrew(llm=get_llm())
yaml_leftover_manager = leftpvers_cb.leftover_manager()
yaml_leftover_task = leftpvers_cb.leftover_task()
