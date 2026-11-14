from typing import cast

from fastmcp import Client


async def test_client_http(client: Client, a: int, b: int) -> int:
    async with client:
        response = await client.call_tool("add", {"a": a, "b": b})
        return cast(int, response.data)


if __name__ == "__main__":
    import asyncio

    from app.mcp.clients.in_memory_client import http_client

    result = asyncio.run(test_client_http(http_client, 5, 3))
    print(f"Result of add tool: {result}")

