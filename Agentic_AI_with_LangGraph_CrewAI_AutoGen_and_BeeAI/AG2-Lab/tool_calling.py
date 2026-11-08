from typing import Annotated

from autogen import ConversableAgent, register_function

# Step 1: LLM configurat
from llm_config import llm_config


# Step 2: Define function
def is_prime(n: Annotated[int, "Positive integer"]) -> str:
    if n < 2:
        return "No"
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return "No"
    return "Yes"


# Step 3: Create agents
math_asker = ConversableAgent(
    name="math_asker",
    system_message="Ask whether a number is prime. make sure to provide a dict e.g {'n': 72}",
    llm_config=llm_config,
)

math_checker = ConversableAgent(
    name="math_checker", human_input_mode="NEVER", llm_config=llm_config
)

# Step 4: Register function
register_function(
    is_prime,
    caller=math_asker,
    executor=math_checker,
    description="Check if a number is prime. Returns Yes or No.",
)

# Step 5: Start conversation
math_checker.initiate_chat(
    recipient=math_asker, message="Is 72 a prime number?", max_turns=2
)
