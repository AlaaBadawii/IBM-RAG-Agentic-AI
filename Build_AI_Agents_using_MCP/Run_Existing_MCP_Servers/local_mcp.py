"""Local MCP connection"""
import asyncio

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from mcp.types import TextContent


async def main():
    stdio_transport = StdioTransport(
        command="npx",
        args=["-y", "@upstash/context7-mcp"],
    )

    async with Client(transport=stdio_transport) as client:
        print("Getting tools...")
        tools = await client.list_tools()
        print("Tools len:", len(tools))

        print("Getting FastMCP info...")
        fastmcp_info = await client.call_tool(
            "resolve-library-id",
            {
                "libraryName": "fastmcp",
                "query": "I want to create a new MCP server using the FastMCP Python framework.",
            },
        )

        content = fastmcp_info.content[0]

        if isinstance(content, TextContent):
            print("FastMCP info:", content.text)
        else:
            print("FastMCP info:", content)

        docs = await client.call_tool(
            "query-docs",
            {
                "libraryId": "/llmstxt/gofastmcp_llms-full_txt",
                "query": "I want to fetch the code snippets and the documentation",
                "tokens": 5000,
            },
        )

        content = docs.content[0]
        if isinstance(content, TextContent):
            print(content.text[:1000])
        else:
            print(content)


if __name__ == "__main__":
    asyncio.run(main())
