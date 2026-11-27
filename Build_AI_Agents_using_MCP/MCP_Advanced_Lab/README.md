# MCP Advanced Lab

A FastMCP **HTTP file server** with two Gradio front ends: a protocol-focused
client and an AI host that exposes MCP capabilities to an OpenAI model through
function calling.

**Status: implemented educational lab; the sampling tool is not supported by the
included clients.**

Course 9: **Build AI Agents using MCP** (IBM RAG and Agentic AI Professional
Certificate). [Course overview](../README.md)

## Overview and objectives

- Serve MCP over **Streamable HTTP** instead of STDIO.
- Expose file tools confined to a `workspace/` directory.
- Expose a resource template and prompt templates over HTTP.
- Build a Gradio client that lists/calls tools, lists/reads resources, and
  lists/renders prompts.
- Build an AI host that adapts MCP tools, resources, and prompts into OpenAI
  function-calling tools.
- Demonstrate the server side of MCP **sampling** with `ctx.sample(...)`.

## Architecture

```text
mcp_http_server.py          FastMCP("HTTP File Server")
  http://127.0.0.1:8000/mcp
        ▲                         ▲
        │ Streamable HTTP         │ Streamable HTTP
        │                         │
mcp_http_client_app.py      mcp_http_host_app.py
  Gradio protocol client      Gradio AI host + OpenAI
  port 7861                   port 7862
```

Both front ends extend `MCPHTTPClient` in `mcp_http_client_base.py`, which wraps
a `streamablehttp_client` connection and a `ClientSession`. The base client
appends `/mcp` to the server URL.

## Server capabilities

`mcp_http_server.py` creates the `workspace/` directory next to the script if it
does not exist and enforces containment with `is_within_roots()`.

| Type | Name | Purpose |
| --- | --- | --- |
| Tool | `read_file(filepath)` | Read a file inside `workspace/` |
| Tool | `write_file(filepath, content)` | Write a file inside `workspace/` |
| Tool | `list_files(directory=".")` | List a directory inside `workspace/` |
| Tool | `analyze_code(code, focus="quality", ctx)` | Request an LLM analysis through MCP sampling |
| Resource template | `file://workspace/{filename}` | Read a workspace file as a resource |
| Prompt | `review_code(filename)` | Code-review prompt |
| Prompt | `analyze_secutity(filename)` | Security-analysis prompt (spelling preserved from source) |

Paths outside `workspace/` are rejected with
`Error: Access denied - path outside workspace roots`. This was verified with a
`../../` traversal attempt.

`analyze_code` calls `ctx.sample(...)`. A client that does not implement a
sampling callback receives `Error calling tool 'analyze_code': Client does not
support sampling`. The included low-level `ClientSession` setup does not register
a sampling handler, so this tool is a server-side demonstration rather than a
working end-to-end path.

## Concepts demonstrated

- FastMCP HTTP transport and the `/mcp` Streamable HTTP endpoint.
- Resource templates and prompts over HTTP.
- Workspace containment for file operations.
- MCP sampling request (`Context.sample`).
- Mapping MCP tools to OpenAI function schemas, including synthetic tools for
  resources and prompts.
- Building Gradio control panels and chat interfaces over an async MCP client.

## Technologies and dependencies

- Python 3.10+
- `fastmcp`, `mcp`
- `gradio`
- `openai`
- `pydantic`

There is **no `requirements.txt`** in this directory. Install the packages
directly:

```bash
python -m pip install fastmcp mcp gradio openai pydantic
```

The Gradio AI host uses the OpenAI Python SDK and reads `OPENAI_API_KEY` from the
environment. The protocol client does not need an API key.

## Project structure

```text
MCP_Advanced_Lab/
├── README.md
├── mcp_http_server.py        # FastMCP HTTP file server
├── mcp_http_client_base.py   # Async HTTP MCP client base class
├── mcp_http_client_app.py    # Gradio protocol client (port 7861)
├── mcp_http_host_app.py      # Gradio AI host with OpenAI (port 7862)
├── .gitignore
└── workspace/                # Server file root (created automatically)
```

## Prerequisites

- Python 3.10+.
- An OpenAI API key for `mcp_http_host_app.py`.
- Network access only if your OpenAI endpoint requires it.
- No Node.js dependency.

## Installation

```bash
cd MCP_Advanced_Lab

python -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows

python -m pip install fastmcp mcp gradio openai pydantic
```

The modules use **flat imports** (`from mcp_http_client_base import ...`), so run
them from inside `MCP_Advanced_Lab` (or add the directory to `PYTHONPATH`).

## Run

### 1. Start the server

```bash
python mcp_http_server.py
```

It prints:

```text
Starting FastMCP HTTP File Server on http://localhost:8000
Workspace directory: /.../MCP_Advanced_Lab/workspace
```

and serves at `http://127.0.0.1:8000/mcp`. Keep it running.

### 2. Protocol client (optional)

In a second terminal:

```bash
python mcp_http_client_app.py http://127.0.0.1:8000 ./workspace
```

Opens `http://127.0.0.1:7861` with tabs for tools, resources, and prompts.

### 3. AI host (optional)

In another terminal, with `OPENAI_API_KEY` set:

```bash
export OPENAI_API_KEY=sk-...
python mcp_http_host_app.py http://127.0.0.1:8000 ./workspace
```

Opens `http://127.0.0.1:7862`. The host uses the hard-coded model
`gpt-6-luna`; if your account does not expose that model, update
`self.model` in `mcp_http_host_app.py`.

Both front ends require the server URL as the first argument and a roots
directory as the second. The `roots_dir` value is stored and displayed, but the
server enforces its own `workspace/` root; the argument does not change the
server's containment boundary.

## Expected behavior

- `list_files` on an empty workspace returns `Directory is empty`.
- `read_file` on a missing file returns `Error: File not found: <name>`.
- `read_file` with a path outside `workspace/` returns an access-denied error.
- The resource `file://workspace/<name>` returns the file text.
- The prompts return review/security instructions.
- The AI host discovers tools, resources, and prompts and can call them during a
  chat.

## Implementation notes

- The server uses `BASE_DIR = Path(__file__).parent / "workspace"`, so the file
  root is independent of the current working directory.
- The AI host adds synthetic tools `mcp_list_resources`, `mcp_read_resource`,
  `mcp_list_prompts`, and `mcp_get_prompt` so the model can reach resources and
  prompts that are not ordinary tools.
- `gui_call_tool` in the protocol client returns after the first content item;
  multi-item tool results may be truncated in the GUI.
- The security prompt name is `analyze_secutity` in the source and must be used
  as written.

## Limitations

- `analyze_code` needs a client that supports MCP sampling; the bundled clients
  do not, and the call fails with `Client does not support sampling`.
- The AI host model ID (`gpt-6-luna`) is hard-coded and may not exist for your
  account.
- No authentication, TLS, rate limiting, or multi-user isolation.
- No automated tests.
- No dependency lockfile.
