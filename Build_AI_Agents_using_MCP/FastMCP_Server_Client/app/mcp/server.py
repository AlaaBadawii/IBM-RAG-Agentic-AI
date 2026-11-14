"""Simple Calculator MCPServer"""
from fastmcp import FastMCP

# Init the MCP Server
mcp = FastMCP(
    name="CalculatorMCPServer",
    instructions="""
This server provides data anlysis tools.
Call get_average() to analyze numerical data.
""",
)

if __name__ == "__main__":
    mcp.run(transport="http", 
            host="127.0.0.1",
            port=8000
    )
