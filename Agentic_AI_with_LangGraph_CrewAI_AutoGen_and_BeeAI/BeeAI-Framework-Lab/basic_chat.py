import asyncio
import logging

from beeai_framework.backend import (
    ChatModel,
    ChatModelParameters,
    SystemMessage,
    UserMessage,
)


# Init the chat model
async def basic_chat_example():
    llm = ChatModel.from_name(
        "watsonx:ibm/granite-4-h-small", ChatModelParameters(temperature=0.5)
    )

    # Create a conversation about something everyone finds interesting
    messages = [
        SystemMessage(
            content="You are a helpful AI assistant and creative writing expert."
        ),
        UserMessage(
            content="Help me brainstorm a unique job-hunting idea for a Backend Engineer with capabilities to build RAG and Agentic AI systems to help him getting his first job offer ASAP."
        ),
    ]

    response = await llm.create(messages=messages)

    print("User: Help me brainstorm a unique Job-Hunting idea.")
    print(f"Assistant: {response.get_text_content()}")

    return response


async def main() -> None:
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)
    await basic_chat_example()


if __name__ == "__main__":
    asyncio.run(main())
