"""Tools for the MCP server."""
from app.mcp.server import mcp


@mcp.tool
def add(a: int, b: int) -> int:
    """
    Add two integers

    Args:
        a (int): The first integer.
        b (int): the second integer.

    Returns:
        int: The sum of a + b

    Example:
        >>> add(3, 5)
        8
    """
    return a + b

@mcp.tool
def subtract(a: int, b: int) -> int:
    """
    Subtract two integers

    Args:
        a (int): first number
        b (int): second number

    Return:
        int: the subtract of a - b

    Example:
        >>> subtract(5, 3)
        2
    """
    return a - b
