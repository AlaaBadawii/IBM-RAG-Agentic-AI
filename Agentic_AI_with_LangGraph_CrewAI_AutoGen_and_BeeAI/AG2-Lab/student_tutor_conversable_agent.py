import logging

from autogen import ConversableAgent

from llm_config import llm_config

logging.getLogger("autogen.aoi.client").setLevel(logging.ERROR)

student = ConversableAgent(
    name="student",
    system_message="You are a curious student. You ask clear, specific quesions to learn new concepts",
    human_input_mode="NEVER",
    llm_config=llm_config
)

tutor = ConversableAgent(
    name="tutor",
    system_message="you are a helpful tutor who provides clear and concise explnations suitable for a biginner.",
    human_input_mode="NEVER",
    llm_config=llm_config
)

chat_result = student.initiate_chat(
    recipient=tutor,
    message="Can you explain what a neural network is?",
    max_turns=2,
    summary_method="reflection_with_llm"
)

print("\nFinal summary:")
print(chat_result.summary)
