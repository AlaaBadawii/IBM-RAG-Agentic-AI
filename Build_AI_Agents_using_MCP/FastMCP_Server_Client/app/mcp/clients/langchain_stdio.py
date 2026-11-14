from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import LLM_MODEL

server_params = StdioServerParameters(
    command="python",
    args=["-m", "app.mcp.server"]
)


async def main():
    async with stdio_client(server_params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()

        tools = await load_mcp_tools(session)

        agent = create_react_agent(model=LLM_MODEL, tools=tools) 

        agent_response = await agent.ainvoke(
            {
                "messages": "Use the add tool to add 2 and 1 and let me know if you used a tool."
            }
        )
        return agent_response["messages"][-1].content
    
