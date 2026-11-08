import logging

from autogen import ConversableAgent
from dotenv import load_dotenv

from llm_config import llm_config

load_dotenv()
logging.getLogger("autogen.aoi.client").setLevel(logging.ERROR)


# Create a Technical agent

tech_expert = ConversableAgent(
    name="tech_expert",
    system_message="""
You are a senior software engineer with expertise in Python, AI, and system design.
Provide technical, detailed explanations with code examples when appropriate.
Always consider best practices and performance implications.
""",
    llm_config=llm_config,
    human_input_mode="NEVER"
)

creative_writer = ConversableAgent(
    name="creative_writer",
    system_message="""
You are a creative writer with expertise in storytelling, character development, and engaging narratives.
Provide imaginative, detailed explanations with examples when appropriate.
""",
    llm_config=llm_config,
    human_input_mode="NEVER"
)

business_analyst = ConversableAgent(
    name="business_analyst",
    system_message="""
You are a business analyst focused on ROI, efficiency, and strategic planning.
Always consider business impact, costs, and practical implementation.
Provide actionable recommendations with clear metrics.
""",
    llm_config=llm_config,
    human_input_mode="NEVER"
)

agents = [tech_expert, creative_writer, business_analyst]

print("Specialized agents created!")
for agent in agents:
    print(f"- {agent.name}: {agent.system_message.split('.')[0]}.")


