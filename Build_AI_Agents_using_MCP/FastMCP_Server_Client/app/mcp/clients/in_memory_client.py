"""MCP Client for interacting with the MCP server."""
from fastmcp import Client

from app.mcp.server import mcp

# Create client
client = Client(mcp)


# create a function that handles add tool calling
async def call_add_tool(a: int, b: int):
    async with client:  # type: ignore[reportGeneralTypeIssues]
        response = await client.call_tool("add", {"a": a, "b": b})
        return response


# create a function that handles subtract tool calling
async def call_subtract_tool(a: int, b: int):
    async with client:
        response = await client.call_tool("subtract", {"a": a, "b": b})

        return response

async def call_resource(name):
    async with client:
        result = await client.read_resource(f"file:///endpoint/{name}")
        return result

async def call_resource2(name):
    async with client:
        result = await client.read_resource(f"file://endpoint2/{name}")
        return result

async def call_prompt(code):
    async with client:
        result = await client.get_prompt("review_code", {"code": code})
        return result


