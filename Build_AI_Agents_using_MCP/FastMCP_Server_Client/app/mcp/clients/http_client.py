from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from app.config import PORT

# MCP client that uses HTTP transport
transport_http = StreamableHttpTransport(
    url=f"http://127.0.0.1:{PORT}/mcp"
)
client = Client(transport=transport_http)

async def call_add_tool(a: int, b: int):
    async with client:
        return await client.call_tool("add", {"a": a, "b": b})


async def call_subtract_tool(a: int, b: int):
    async with client:
        return await client.call_tool("subtract", {"a": a, "b": b})


async def call_resource(name: str):
    async with client:
        return await client.read_resource(f"file:///endpoint{name}")


async def call_resource2(name: str):
    async with client:
        return await client.read_resource(f"file:///endpoint2/{name}")


async def call_prompt(code: str):
    async with client:
        return await client.get_prompt("review_code", {"code": code})
    