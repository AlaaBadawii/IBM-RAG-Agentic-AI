"""Remote MCP connection"""

import asyncio

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from mcp.types import TextContent


async def main():
    http_transport = StreamableHttpTransport(url="https://mcp.context7.com/mcp")

    async with Client(http_transport) as client:
        tools = await client.list_tools()

        response = await client.call_tool(
            "resolve-library-id",
            {
                "libraryName": "fastmcp",
                "query": "I want to create a new MCP server using the fastmcp Python framework",
            },
        )

        docs = await client.call_tool(
            "query-docs",
            {
                "libraryId": "/llmstxt/gofastmcp_llms-full_txt",
                "query": "I want to fetch the code snippets and the documentation",
                "tokens": 5000,
            },
        )

    for tool in tools:
        print(f"{tool.name}: \n{tool.description} \n{tool.input_schema}")

    response_content = response.content[0]
    if isinstance(response_content, TextContent):
        print(response_content.text[:1000])
    else:
        print(response_content)

    docs_content = docs.content[0]
    if isinstance(docs_content, TextContent):
        print(docs_content.text[:500])
    else:
        print(docs_content)

if __name__ == "__main__":
    asyncio.run(main())
