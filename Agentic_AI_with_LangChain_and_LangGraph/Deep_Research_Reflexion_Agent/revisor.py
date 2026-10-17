from functools import lru_cache

from langchain_core.runnables import RunnableLambda

from llm import get_llm
from prompt import prompt_template
from schema import ReviseAnswer

revise_instructions = """Revise your previous answer using the new information, applying the rigor and evidence-based approach of Dr. David Attia.
- Incorporate the previous critique to add clinically relevant information, focusing on mechanistic understanding and individual variability.
- You MUST include numerical citations referencing peer-reviewed research, randomized controlled trials, or meta-analyses to ensure medical accuracy.
- Distinguish between correlation and causation, and acknowledge limitations in current research.
- Address potential biomarker considerations (lipid panels, inflammatory markers, and so on) when relevant.
- Add a "References" section to the bottom of your answer (which does not count towards the word limit) in the form of:
- [1] https://example.com
- [2] https://example.com
- Use the previous critique to remove speculation and ensure claims are supported by high-quality evidence. Keep response under 250 words with precision over volume.
- When discussing nutritional interventions, consider metabolic flexibility, insulin sensitivity, and individual response variability.
"""

revisor_prompt = prompt_template.partial(first_instruction=revise_instructions)


@lru_cache(maxsize=1)
def get_revisor_chain():
    """Build (once) the revisor chain: prompt -> LLM bound to ReviseAnswer.

    The chain is built lazily so that importing this module does not create a
    watsonx.ai client or perform any network request.
    """

    return revisor_prompt | get_llm().bind_tools([ReviseAnswer], tool_choice="ReviseAnswer")


revisor_chain = RunnableLambda(lambda inputs: get_revisor_chain().invoke(inputs))
