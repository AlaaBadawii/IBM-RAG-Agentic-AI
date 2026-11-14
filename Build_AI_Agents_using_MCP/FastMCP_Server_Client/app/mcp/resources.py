"""Resources for the MCP server."""
from server import mcp

from app.utils import make_dir


@mcp.resource("file:///endpoint{name}")
def return_template_document(name: str) -> str:
    """Read a document by name"""
    return f"Document contents of {name}"

# Create the path directory if it doesn't exist
make_dir()

@mcp.resource("file:///endpoint2/{name}")
def read_document(name: str) -> str:
    """Read document by name from the path directory"""
    try:
        with open(f"path/{name}") as f:
            return f.read()
    except FileNotFoundError:
        return f"Document '{name}' not found in path directory"
    except (OSError, UnicodeError) as e:
        return f"Error reading document: {e!s}"
