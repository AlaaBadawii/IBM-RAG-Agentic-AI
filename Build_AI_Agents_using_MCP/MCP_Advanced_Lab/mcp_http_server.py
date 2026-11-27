import logging
import warnings
from pathlib import Path

from fastmcp import Context, FastMCP

# Suppress deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.getLogger("fastmcp").setLevel(logging.WARNING)

mcp = FastMCP("HTTP File Server")

BASE_DIR = Path(__file__).parent / "workspace"
BASE_DIR.mkdir(exist_ok=True)


def is_within_roots(path: Path) -> bool:
    """Check if path is within allowed roots directory."""
    try:
        path.resolve().relative_to(BASE_DIR.resolve())
        return True
    except ValueError:
        return False


@mcp.tool()
def read_file(filepath: str) -> str:
    """Read a file from the workspace directory."""
    path = BASE_DIR / filepath

    if not is_within_roots(path):
        return "Error: Access denied - path outside workspace roots"

    if not path.exists():
        return f"Error: File not found: {filepath}"

    try:
        content = path.read_text()
        return content
    except (OSError, UnicodeError) as e:
        return f"Error reading file: {e!s}"


@mcp.tool()
def write_file(filepath: str, content: str) -> str:
    """Write content to a file in the workspace directory."""
    path = BASE_DIR / filepath

    if not is_within_roots(path):
        return "Error: Access denied - path outside workspace roots"

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f"Successfully wrote {len(content)} characters to {filepath}"
    except (OSError, UnicodeError) as e:
        return f"Error writing file: {e!s}"


@mcp.tool()
def list_files(directory: str = ".") -> str:
    """List files in a directory within the workspace."""
    path = BASE_DIR / directory

    if not is_within_roots(path):
        return "Error: Access denied - path outside workspace roots"

    if not path.exists():
        return f"Error: Directory not found: {directory}"

    if not path.is_dir():
        return f"Error: Not a directory: {directory}"

    try:
        files = []
        for item in sorted(path.iterdir()):
            relative_path = item.relative_to(BASE_DIR)
            file_type = "DIR" if item.is_dir() else "FILE"
            size = item.stat().st_size if item.is_file() else 0
            files.append(f"{file_type}: {relative_path} ({size} bytes)")

        return "\n".join(files) if files else "Directory is empty"
    except (OSError, UnicodeError) as e:
        return f"Error listing directory: {e!s}"


@mcp.tool()
async def analyze_code(
    code: str, ctx: Context, focus: str = "quality"
) -> str:
    """Analyze code for quality, security, or performance."""

    analysis_result = await ctx.sample(
        f"Analyzing code for {focus}:\n{code}\nProvide a detailed analysis and suggestions.",
        max_tokens=500,
    )

    text = getattr(analysis_result, "text", None)
    if isinstance(text, str):
        return text

    return "Error: The analysis response did not contain text content."

@mcp.resource("file://workspace/{filename}")
def get_workspace_file(filename: str) -> str:
    """Get the content of a file in the workspace."""
    path = BASE_DIR / filename

    if not is_within_roots(path):
        return "Error: Access denied - path outside workspace roots"

    if not path.exists():
        return f"Error: File not found: {filename}"

    try:
        content = path.read_text()
        return content
    except (OSError, UnicodeError) as e:
        return f"Error reading file: {e!s}"

@mcp.prompt()
def review_code(filename: str) -> str:
    """Retrieve a prompt template by name."""
    return f""" Generate a prompt to review code in the file '{filename}' and provide:
1. A summary of the code's functionality.
2. Potential issues or bugs.
3. Suggestions for improvements.
4. Any security vulnerabilities or performance concerns.
5. Code Quality assessment and best practices recommendations.

Focus on providing actionable feedback and clear explanations.
"""

@mcp.prompt()
def analyze_secutity(filename: str) -> str:
    """Retrieve a prompt template for security analysis."""
    return f""" Generate a prompt to analyze the security of the code in the file '{filename}' and provide:
1. Input validation and sanitization checks.
2. Authentication and authorization considerations.
3. Potential vulnerabilities (e.g., SQL injection, XSS, CSRF).
4. Data exposure and privacy concerns.
5. Error handling and logging practices.

Provide specific line numbers and remediation suggestions
"""

if __name__ == "__main__":
    print("Starting FastMCP HTTP File Server on http://localhost:8000")
    print(f"Workspace directory: {BASE_DIR.resolve()}")

    mcp.run(transport="http", host="127.0.0.1", port=8000)

