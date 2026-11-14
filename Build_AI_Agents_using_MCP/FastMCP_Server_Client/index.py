import asyncio
from fastmcp import Client

async def main():
    async with Client("http://127.0.0.1:8000/mcp") as client:

        # Check connection
        print(await client.ping())

        # Discover available tools
        tools = await client.list_tools()

        for tool in tools:
            print(tool.name, tool.inputSchema)

asyncio.run(main())
