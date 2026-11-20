import logging
from pathlib import Path

from fastmcp import FastMCP

# Suppress verbose FastMCP logging
logging.getLogger("fastmcp").setLevel(logging.WARNING)
mcp = FastMCP("lab-server")
BASE_DIR = Path(__file__).resolve().parent


def resolve_project_path(path: str) -> Path:
    """Resolve a path while keeping it inside the project directory."""
    file_path = (BASE_DIR / path).resolve()
    if not file_path.is_relative_to(BASE_DIR):
        raise ValueError("Path must remain inside the project directory")
    return file_path


@mcp.tool()
def echo(text: str) -> str:
    """Echo back the input text."""
    return f"Echo: {text}"


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    file_path = resolve_project_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return f"Successfully wrote to {path}"


@mcp.resource("file://resources/{filename}")
def read_resource_file(filename: str) -> str:
    """Read a file from the resources directory."""
    resources_dir = (BASE_DIR / "resources").resolve()
    file_path = (resources_dir / filename).resolve()
    if not file_path.is_relative_to(resources_dir):
        raise ValueError("Resource path must remain inside the resources directory")
    if not file_path.exists():
        return f"File not found: {filename}"
    return file_path.read_text(encoding="utf-8")
@mcp.prompt()
def review_file(filename: str) -> str:
    """Generate a prompt to review a file's contents."""
    return f"""Please review the file '{filename}' and provide:

A summary of its contents
Key points or sections
Any suggestions for improvement
Overall quality assessment

Use the appropriate tools to read the file if needed."""


if __name__ == "__main__":
    mcp.run()
