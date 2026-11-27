import asyncio
import logging
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from pydantic import AnyUrl

logging.getLogger("fastmcp").setLevel(logging.WARNING)


class MCPHTTPClient:
    """Base MCP HTTP client with pure protocol logic - no GUI dependencies."""

    def __init__(self, server_url: str, roots_dir: str):
        self.server_url = server_url
        self.roots_dir = roots_dir
        self.session = None
        self.exit_stack = AsyncExitStack()
        self._connected = False

    async def connect(self):
        """Connect to HTTP MCP server via Streamble HTTP. Safe to call multiple times."""
        if self._connected:
            return

        # FastMCP Uses /mcp endpoint for streamable HTTP
        mcp_url = f"{self.server_url}/mcp"
        read, write, _ = await self.exit_stack.enter_async_context(
            streamablehttp_client(mcp_url)
        )

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )

        await self.session.initialize()

        self._connected = True

    async def list_tools(self):
        """List all availible tools from HTTP server"""
        if self.session is None:
            await self.connect()

        assert self.session is not None

        result = await self.session.list_tools()
        return result.tools

    async def call_tool(self, tool_name, args):
        """execute tool on the HTTP server"""
        if not self.session:
            await self.connect()
        assert self.session is not None
        result = await self.session.call_tool(tool_name, args)

        return result

    async def list_resources(self):
        """List rescouces on the HTTP server"""
        if not self.session:
            await self.connect()
        assert self.session is not None

        result = await self.session.list_resource_templates()

        return result.resourceTemplates

    async def read_resource(self, uri: str):
        """Read recource on the HTTP server"""
        if not self.session:
            await self.connect()
        assert self.session is not None

        result = await self.session.read_resource(AnyUrl(uri))
        return result

    async def list_prompts(self):
        """List available prompts on the server"""
        if not self.session:
            await self.connect()
        assert self.session is not None

        result = await self.session.list_prompts()
        return result.prompts

    async def get_prompt(self, prompt_name: str, args):
        """Get prompt tenplate from the server"""
        if not self.session:
            await self.connect()
        assert self.session is not None

        result = await self.session.get_prompt(prompt_name, args)
        return result

    async def cleanup(self):
        """Clean up recources and close HTTP connection"""
        await self.exit_stack.aclose()

    
