"""Prompts for the MCP server."""

from server import mcp


@mcp.prompt
def review_code(code: str) -> str:
    return f"Please review this code:\n\n{code}"
