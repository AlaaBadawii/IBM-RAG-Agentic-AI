# Run Existing MCP Servers

Two small scripts that connect to the existing **Context7** MCP server using the
FastMCP `Client`: one through a local STDIO server launched with `npx`, and one
through the hosted Streamable HTTP endpoint.

**Status: implemented connection exercises; requires network access (and Node.js
for the local variant).**

Course 9: **Build AI Agents using MCP** (IBM RAG and Agentic AI Professional
Certificate). [Course overview](../README.md)

## Overview and objectives

- Consume a third-party MCP server without writing one.
- Compare two transports: **STDIO** and **Streamable HTTP**.
- Discover a server's tools with `client.list_tools()`.
- Call the Context7 tools `resolve-library-id` and `query-docs`.
- Read MCP `TextContent` results.

Both scripts use the same Context7 queries, so you can compare the local and
remote connection paths directly.

## Scripts

| Script | Transport | Endpoint |
| --- | --- | --- |
| `local_mcp.py` | `StdioTransport` | Runs `npx -y @upstash/context7-mcp` |
| `remote_mcp.py` | `StreamableHttpTransport` | `https://mcp.context7.com/mcp` |

### `local_mcp.py`

Creates a `StdioTransport` that launches the Context7 npm package, lists tools,
then:

1. Calls `resolve-library-id` for `fastmcp`.
2. Calls `query-docs` with library ID `/llmstxt/gofastmcp_llms-full_txt` and a
   5000-token request.
3. Prints the resolved library information and the first 1000 characters of the
   documentation response.

### `remote_mcp.py`

Connects to the hosted Context7 endpoint, lists tools, performs the same two
calls, and then prints each tool's name, description, and input schema followed
by truncated response text (1000 and 500 characters).

## Concepts demonstrated

- FastMCP `Client` as a consumer of MCP servers.
- STDIO transport via `StdioTransport`.
- Streamable HTTP transport via `StreamableHttpTransport`.
- Tool discovery and tool invocation.
- Handling `TextContent` versus other content types.

## Technologies and dependencies

- Python 3.10+
- `fastmcp`
- `mcp`
- Node.js and `npx` (local script only)
- Network access to the npm registry and Context7

There is **no `requirements.txt`**. Install the Python packages directly:

```bash
python -m pip install fastmcp mcp
```

No API key is used by these scripts.

## Project structure

```text
Run_Existing_MCP_Servers/
├── README.md
├── local_mcp.py     # STDIO connection to @upstash/context7-mcp
└── remote_mcp.py    # Streamable HTTP connection to mcp.context7.com
```

## Prerequisites

- Python 3.10+.
- For `local_mcp.py`: Node.js with `npx` on `PATH`.
- Outbound network access. The first local run also downloads the npm package.

## Run

```bash
cd Run_Existing_MCP_Servers
python -m pip install fastmcp mcp

python local_mcp.py     # requires Node.js / npx
python remote_mcp.py    # requires network access
```

## Expected output

Both scripts print the Context7 tool list and then text from the resolved
library and documentation queries. The local script prints messages such as
`Getting tools...` and `Tools len: N`; the remote script prints each tool's name,
description, and input schema.

Exact text depends on the live Context7 service and the queried documentation, so
no fixed output is reproduced here.

## Configuration details

- The library name (`fastmcp`), queries, library ID
  (`/llmstxt/gofastmcp_llms-full_txt`), and token count (`5000`) are hard-coded.
- The local package name (`@upstash/context7-mcp`) and the remote URL
  (`https://mcp.context7.com/mcp`) are hard-coded.
- No environment variables are read.

## Limitations

- Requires network access; the local variant also requires Node.js/`npx`.
- No error handling or retries; a network or package failure aborts the script.
- Context7 is an external hosted service and may rate-limit or change its tools.
- Output is intentionally truncated (1000/500 characters) for display.
- No automated tests.
