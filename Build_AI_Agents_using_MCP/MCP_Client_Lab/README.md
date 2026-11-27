# MCP Client Lab

An interactive Model Context Protocol (MCP) client paired with a FastMCP STDIO
server. It is a hands-on lab for discovering and invoking tools, resource
templates, and prompts from a terminal.

**Status: implemented and locally runnable with the pinned dependencies.**

Course 9: **Build AI Agents using MCP** (IBM RAG and Agentic AI Professional
Certificate). [Course overview](../README.md)

## Overview and objectives

- Build a minimal FastMCP server that exposes tools, a resource template, and a
  prompt.
- Connect to it from a custom client over **STDIO**.
- List and call tools, list and read resources, and list and render prompts.
- Keep filesystem access bounded to the project and resources directories.

The client launches the server itself as a subprocess, so no separate server
terminal is needed.

## Server capabilities

The server is named `lab-server` (`mcp_server.py`) and provides:

| Type | Name | Purpose |
| --- | --- | --- |
| Tool | `echo` | Returns text prefixed with `Echo:` |
| Tool | `write_file` | Creates or updates a text file inside the project |
| Resource template | `file://resources/{filename}` | Reads a text file from `resources/` |
| Prompt | `review_file` | Generates a file-review prompt |

`write_file` resolves the path against the project directory and rejects paths
that escape it. The resource reader additionally restricts access to the
`resources/` subdirectory. Both checks use `Path.resolve()` and
`Path.is_relative_to()`.

The server runs with `mcp.run()`, which uses the STDIO transport by default.

## Concepts demonstrated

- FastMCP `@mcp.tool`, `@mcp.resource`, and `@mcp.prompt` registration.
- MCP `ClientSession` over a `stdio_client` transport.
- `list_tools` / `call_tool`, `list_resource_templates` / `read_resource`, and
  `list_prompts` / `get_prompt`.
- Passing a Python executable (`sys.executable`) and script path to
  `StdioServerParameters`.
- Basic path-traversal protection in server tools.

## Technologies and dependencies

- Python 3.12 (as documented for this lab)
- Pinned packages in `requirements.txt`:
  - `fastmcp==2.12.5`
  - `mcp==1.16.0`
  - `pydantic==2.13.5`

## Project structure

```text
MCP_Client_Lab/
├── README.md
├── mcp_client.py        # Interactive STDIO client
├── mcp_server.py        # FastMCP server (tools, resource, prompt)
├── requirements.txt     # Pinned dependencies
├── project_info.txt     # Lab metadata
├── .gitignore
└── resources/           # Files served by the resource template (starts empty)
```

## Prerequisites

- Python 3.12 (the README and pins target this version).
- A terminal environment; no API key or external service is required.

## Installation

Run these commands from `MCP_Client_Lab`:

```bash
python3 -m venv mcp_client_env
source mcp_client_env/bin/activate      # Linux/macOS
# mcp_client_env\Scripts\activate       # Windows

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`mcp_client_env/` is git-ignored.

## Run the client

```bash
source mcp_client_env/bin/activate
python mcp_client.py mcp_server.py
```

The client spawns the server over STDIO. If the argument is omitted it prints:

```text
Usage: python mcp_client.py <server_script>
```

## Interactive commands

| Command | Action |
| --- | --- |
| `tools` | List available MCP tools |
| `call` | Call a tool with a JSON argument object |
| `resources` | List available resource templates |
| `read` | Read a resource by URI |
| `prompts` | List available prompts |
| `prompt` | Run a prompt with JSON arguments |
| `quit` | Close the client and server |

### Echo example

```text
> tools
> call
  Tool name: echo
  Arguments (as JSON, for example, {"text": "hello"}):
  {"text":"hello"}
```

Result:

```text
  Result: Echo: hello
```

### Write-file example

```text
> call
  Tool name: write_file
  Arguments (as JSON, for example, {"text": "hello"}):
  {"path":"resources/example.txt","content":"Hello from MCP"}
```

### Resource example

```text
> resources
> read
  URI: file://resources/example.txt
```

`resources/` starts empty. Create `example.txt` with `write_file` first, or use
the name of an existing file in `resources/`.

### Prompt example

```text
> prompt
  Prompt name: review_file
  Arguments (as JSON):
  {"filename":"README.md"}
```

## Expected behavior

- `tools` lists `echo` and `write_file`.
- `resources` lists the `file://resources/{filename}` template (the client lists
  resource *templates*, not concrete resource instances).
- `read` on a missing file returns `File not found: <name>`.
- `write_file` reports `Successfully wrote to <path>`.
- `prompt` prints the rendered `review_file` message.

## Implementation notes

- `write_file` paths are relative to the project directory, so files may be
  created outside `resources/` as long as they stay inside the project. Only the
  resource reader is restricted to `resources/`.
- The resource reader returns an error string for missing files rather than
  raising.
- Tool/prompt arguments are parsed with `json.loads`; invalid JSON is reported
  as `Error: Invalid JSON format`.
- `project_info.txt` identifies the lab as version 1.0.0 by Skills Network.

## Limitations

- STDIO only; there is no HTTP transport in this lab.
- No authentication, concurrency handling, or rate limiting.
- No automated tests.
- The client is a learning tool and does not validate schemas beyond the MCP
  layer.
