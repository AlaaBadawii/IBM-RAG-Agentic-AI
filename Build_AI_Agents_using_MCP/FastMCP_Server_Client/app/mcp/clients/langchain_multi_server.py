import asyncio

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from app.config import LLM_MODEL, PORT

client = MultiServerMCPClient(
    {
        "stdio-client": {
            "command": "python",
            "args": ["-m", "app.mcp.server"],
            "transport": "stdio",
        },
        "http-client": {
            "url": f"http://127.0.0.1:{PORT}/mcp",
            "transport": "streamable_http",
        },
    }
)


tools = asyncio.run(client.get_tools())
[
    tool.name for tool in tools
]  # List the names of the tools available from the MCP server


agent = create_react_agent(model=LLM_MODEL, tools=tools)




if __name__ == "__main__":
    # Print the agent's response
    agent_response = asyncio.run(
        agent.ainvoke(
            {
                "messages": "Use the add tool to add 2 and 1 and let me know if you used a tool."
            }
        )
    )

    for i in agent_response['messages']:
        if isinstance(i, HumanMessage):
            message_type = "HUMAN"
        elif isinstance(i, AIMessage):
            message_type = "AI"
        elif isinstance(i, ToolMessage):
            message_type = "TOOL"
        else:
            message_type = "OTHER"

        if i.content == '':
            i.content = "tool call"
        
        print(f"[{message_type}] {i.content}")
