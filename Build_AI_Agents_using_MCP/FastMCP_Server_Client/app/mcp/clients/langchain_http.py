import asyncio

from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.config import LLM_MODEL, PORT


async def fun():
    async with (
        streamable_http_client(f"http://127.0.0.1:{PORT}/mcp") as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()

        # Load LangChain Tools from live MCP
        tools = await load_mcp_tools(session)

        agent = create_react_agent(model=LLM_MODEL, tools=tools)

        agent_response = await agent.ainvoke(
            {
                "messages": "Use the add tool to add 2 and 1 and let me know if you used a tool."
            }
        )

        return agent_response["messages"][-1].content

asyncio.run(fun())

