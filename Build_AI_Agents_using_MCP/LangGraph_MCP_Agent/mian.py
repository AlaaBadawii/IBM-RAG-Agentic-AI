import asyncio
import os

from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent


async def main():
    """
    Set up and run a LangGraph ReAct agent
    connected to multiple MCP servers.

    Available MCP servers:
        - Context7: Library documentation
        - Met Museum: Museum collections

    Features:
        - GPT-5.4-mini powered agent
        - Persistent conversation memory
        - STDIO and HTTP MCP transports
    """

    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set. Copy .env.example to .env and add your key.")

    try:
        # Configure MCP servers
        client = MultiServerMCPClient(
            {
                "context7": {
                    "url": "https://mcp.context7.com/mcp",
                    "transport": "streamable_http",
                },
                "met-museum": {
                    "command": "npx",
                    "args": ["-y", "metmuseum-mcp"],
                    "transport": "stdio",
                },
            }
        )

        # Initialize the language model
        openai_model = ChatOpenAI(model="gpt-5.4-mini", temperature=0)

        # Retrieve tools from all configured MCP servers
        tools = await client.get_tools()

        # Initialize conversation memory
        checkpointer = InMemorySaver()

        config: RunnableConfig = {
            "configurable": {"thread_id": "conversation_id"}
        }

        # Create the ReAct agent
        agent = create_react_agent(
            model=openai_model, tools=tools, checkpointer=checkpointer
        )

        # Initial system instructions
        system_message = {
            "role": "system",
            "content": (
                "You are a smart and useful assistant with access to "
                "multiple MCP servers. You can access code library "
                "documentation through Context7 and explore the "
                "Metropolitan Museum of Art collection through "
                "the Met Museum MCP server. "
                "Use your tools whenever they are relevant."
            ),
        }

        # Initialize the conversation
        messages = {
            "messages": [
                system_message,
                {
                    "role": "user",
                    "content": (
                        "Give a brief introduction of what you do "
                        "and the tools you can access."
                    ),
                },
            ]
        }

        response = await agent.ainvoke(messages, config=config)

        print("\nAgent:")
        print(response["messages"][-1].content)

        while True:
            choice = input(
                """
Menu:
1. Ask agent a question
2. Quit

Enter your choice (1 or 2): """
            ).strip()

            if choice == "1":
                query = input("\nYour question: ").strip()

                if not query:
                    print("Please enter a valid question.")
                    continue

                response = await agent.ainvoke(
                    {"messages": [{"role": "user", "content": query}]}, config=config
                )

                print("\nAgent:")
                print(response["messages"][-1].content)

            elif choice == "2":
                print("\nGoodbye!")
                break

            else:
                print("\nInvalid choice. Please select 1 or 2.")

    except KeyboardInterrupt:
        print("\nApplication interrupted. Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())
