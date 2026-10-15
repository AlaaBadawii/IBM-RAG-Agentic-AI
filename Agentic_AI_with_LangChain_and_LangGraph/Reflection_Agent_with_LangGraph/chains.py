from llm import llm
from prompts import generation_prompt, reflection_prompt

generation_chain = generation_prompt | llm
reflection_chain = reflection_prompt | llm
