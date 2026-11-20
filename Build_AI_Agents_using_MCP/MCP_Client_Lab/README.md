# MCP Client Lab

An interactive Model Context Protocol (MCP) client and FastMCP STDIO server for
learning MCP tools, resource templates, and prompts.

## Project files

- `mcp_client.py` - connects to an MCP server and provides an interactive terminal.
- `mcp_server.py` - exposes MCP tools, a resource template, and a prompt.
- `resources/` - directory used by the file resource and writable files.
- `requirements.txt` - Python dependencies used by the lab.
- `project_info.txt` - project metadata.

## Server capabilities

The server is named `lab-server` and provides:

| Type | Name | Purpose |
| --- | --- | --- |
| Tool | `echo` | Returns text prefixed with `Echo:` |
| Tool | `write_file` | Creates or updates a text file |
| Resource | `file://resources/{filename}` | Reads a text file from `resources/` |
| Prompt | `review_file` | Generates a prompt for reviewing a file |

File paths are restricted to the project directory, and resource paths are
restricted to the `resources/` directory.

## Requirements

- Python 3.12 or newer
- The pinned packages in `requirements.txt`:
  - `fastmcp==2.12.5`
  - `mcp==1.16.0`
  - `pydantic==2.13.5`

## Setup

Run these commands from `MCP_Client_Lab`:

```bash
python3 -m venv mcp_client_env
source mcp_client_env/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Start the client

```bash
source mcp_client_env/bin/activate
python mcp_client.py mcp_server.py
```

The server is launched automatically by the client over STDIO. The server does
not need to be started in a separate terminal.

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

The result is:

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

Create `resources/example.txt` first by using `write_file`, or replace the URI
with the name of an existing file in `resources/`.

### Prompt example

```text
> prompt
  Prompt name: review_file
  Arguments (as JSON):
  {"filename":"README.md"}
```

