"""
LLM client and prompt template example for the BeeAI Framework lab.

Supports any model identifier accepted by BeeAI's ChatModel provider
registry, such as:
- watsonx:ibm/granite-4-h-small
- gemini:gemini-3.5-flash-lite
"""

import asyncio
import logging
import os

from dotenv import load_dotenv

# Load environment configuration before importing BeeAI.
load_dotenv(override=True)

# Work around the unclosed aiohttp session issue in LiteLLM.
os.environ.setdefault("DISABLE_AIOHTTP_TRANSPORT", "True")

from beeai_framework.backend import (
    ChatModel,
    ChatModelParameters,
    SystemMessage,
    UserMessage,
)


def get_llm(model_name: str) -> ChatModel:
    """Initialize a BeeAI chat model."""
    models = {
        "watsonx": "watsonx:ibm/granite-4-h-small",
        "gemini": "gemini:gemini-3.5-flash-lite",
    }

    return ChatModel.from_name(
        models[model_name],
        ChatModelParameters(temperature=0),
    )


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    model_name = "gemini:gemini-3.5-flash-lite"
    llm = get_llm(model_name)

    messages = [
        SystemMessage(
            content="You are a helpful AI assistant and creative writing expert."
        ),
        UserMessage(
            content=(
                "Help me brainstorm a unique business idea for a food "
                "delivery service that doesn't exist yet."
            )
        ),
    ]

    response = await llm.create(messages=messages)

    print("LLM Response:", response.get_text_content())


if __name__ == "__main__":
    asyncio.run(main())
