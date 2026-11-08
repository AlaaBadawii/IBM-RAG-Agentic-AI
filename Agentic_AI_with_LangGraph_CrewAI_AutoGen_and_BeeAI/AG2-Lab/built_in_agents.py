import logging
import os

from autogen import AssistantAgent, UserProxyAgent
from autogen.coding import LocalCommandLineCodeExecutor

from llm_config import llm_config

logging.getLogger("autogen.aoi.client").setLevel(logging.ERROR)

#  Create a coding assistant agent
coding_assistant = AssistantAgent(
    name="coding_assistant",
    system_message="You are a coding assistant with expertise in Python, who writes and expalins code clearly and concisely.",
    llm_config=llm_config,
)

user_proxy = UserProxyAgent(
    name="user_proxy",
    human_input_mode="NEVER",
    llm_config=llm_config,
    max_consecutive_auto_reply=5,
    code_execution_config={
        "executor": LocalCommandLineCodeExecutor(work_dir='coding', timeout=30)
    },
)

chat_result = user_proxy.initiate_chat(
    recipient=coding_assistant,
    message="Plot a sine wave using matplotlib from -2π to 2π and save the plot as sine_wave.png.",
    max_turns=2,
    summary_method="reflection_with_llm"
)


image_path = "coding/sine_wave.png"
if os.path.exists(image_path):
    print("Image generated successfully")
else:
    print("Plot not found.")

print("\nFinal Summary:")
print(chat_result.summary)