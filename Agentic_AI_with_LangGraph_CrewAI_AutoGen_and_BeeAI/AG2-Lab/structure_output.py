import logging
from typing import Any, cast

from autogen import ConversableAgent
from pydantic import BaseModel

from llm_config import llm_config

logging.getLogger("autogen.aoi.client").setLevel(logging.ERROR)


# Define structured output model
class TicketSummary(BaseModel):
    customer_name: str
    issue_type: str
    urgency_level: str
    recommended_action: str

cast(Any, llm_config)["response_format"] = TicketSummary

# Create agent
support_agent = ConversableAgent(
    name="support_agent",
    system_message=(
        "You are a support assistant. Summarize a customer ticket using:"
        "\n- customer_name"
        "\n- issue_type (e.g. login issue, billing problem, bug report)"
        "\n- urgency_level (Low, Medium, High)"
        "\n- recommended_action"
    ),
    llm_config=llm_config,
)

# Start conversation
support_agent.initiate_chat(
    recipient=support_agent,
    message="Ticket: John Doe is unable to reset his password and has an important meeting in 30 minutes.",
    max_turns=1,
)
