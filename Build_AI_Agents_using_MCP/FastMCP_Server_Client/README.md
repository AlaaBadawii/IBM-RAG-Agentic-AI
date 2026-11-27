# FastMCP Server & Client

A FastMCP calculator project that pairs a small MCP server with several client
examples: in-memory, Streamable HTTP, STDIO, and LangChain multi-server
integration.

**Status: educational lab; client/server wiring is incomplete in places and is
documented below.**

Course 9: **Build AI Agents using MCP** (IBM RAG and Agentic AI Professional
Certificate). [Course overview](../README.md)

## Overview

The project was built to practise:

- Defining an MCP server with FastMCP.
- Registering tools, file resources, and a prompt.
- Calling MCP capabilities from different transports.
- Loading MCP tools into LangGraph ReAct agents with `langchain-mcp-adapters`.
- Aggregating tools from a STDIO server and an HTTP server in one agent.

The intended server is a calculator named `CalculatorMCPServer`, serving
`add`/`subtract`, two file-resource templates, and a `review_code` prompt.

## Important: current wiring status

The modules are present, but `app/mcp/server.py` does **not** import the modules
that register capabilities. As committed:

- `python -m app.mcp.server` starts an HTTP server on `127.0.0.1:8000` with
  **no tools, resources, or prompts registered**.
- `app/mcp/tools.py` registers `add` and `subtract` when imported. Verified by
  importing it before creating an in-memory client.
- `app/mcp/resources.py` and `app/mcp/prompts.py` use `from server import mcp`.
  That import fails with `ModuleNotFoundError: No module named 'server'` unless a
  top-level `server` module is placed on `sys.path`; it does not resolve from the
  `app` package. Consequently those two modules cannot register their
  capabilities in the current layout.

To register the tools in a session, import `app.mcp.tools` explicitly, for
example:

```python
import app.mcp.tools  # registers add/subtract on app.mcp.server.mcp
from app.mcp.server import mcp
```

No code changes are made by this documentation. Fixing the registration imports
is a code task.

## Project structure

```text
FastMCP_Server_Client/
├── index.py                     # Lists tools from a running HTTP server
├── requirements.txt             # Python dependencies
├── requiremnets.txt             # Empty, misspelled file; not used
├── .env.example                 # OPENAI_API_KEY placeholder
├── .gitignore
├── app/
│   ├── config.py                # PORT=8000, LLM_MODEL="openai:gpt-5-nano"
│   ├── utils.py                 # make_dir(), print_stream_info()
│   └── mcp/
│       ├── server.py            # FastMCP instance + HTTP entry point
│       ├── tools.py             # add / subtract tools
│       ├── resources.py         # Intended file resources (broken import)
│       ├── prompts.py           # Intended review_code prompt (broken import)
│       └── clients/
│           ├── in_memory_client.py    # In-process client functions
│           ├── http_client.py         # Streamable HTTP client functions
│           ├── langchain_http.py      # LangGraph agent over HTTP
│           ├── langchain_stdio.py     # LangGraph agent over STDIO
│           └── langchain_multi_server.py  # Agent over stdio + HTTP
├── path/                        # Documents used by the file resource
│   ├── README.txt
│   └── examples.txt             # Empty
└── tests/
    ├── test_client_http.py      # Broken import; not a runnable test
    └── test_port.py             # Prints port availability (inverted messages)
```

## Technologies

- Python 3.10+
- `fastmcp` (server, `Client`, transports)
- `mcp` Python SDK (`ClientSession`, `StdioServerParameters`, stdio/HTTP clients)
- `langchain`, `langchain-core`, `langchain-mcp-adapters`
- `langgraph`, `langgraph-prebuilt`
- `langchain-openai`, `openai`
- `httpx`, `uvicorn`, `python-dotenv`, `pydantic`, `anyio`

Exact pins are in `requirements.txt` (for example `fastmcp==2.12.2`,
`mcp==1.30.0`, `langgraph==0.6.7`). Use `requirements.txt`; `requiremnets.txt`
is empty.

## Setup

```bash
cd FastMCP_Server_Client

python -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows

python -m pip install -r requirements.txt
cp .env.example .env
# edit .env and set OPENAI_API_KEY for the LangChain clients
```

`OPENAI_API_KEY` is required by the LangChain/LangGraph clients. The model is
hard-coded as `openai:gpt-5-nano` in `app/config.py`, so that model must be
available to your key.

## Run the server

From the project root:

```bash
python -m app.mcp.server
```

This serves Streamable HTTP at `http://127.0.0.1:8000/mcp`. Remember that, as
committed, the server has no registered capabilities until the registration
modules are imported (see the wiring note above). Keep it running in one terminal
for the HTTP-based clients.

## Clients

### `index.py` — tool discovery

```bash
python index.py
```

Connects to `http://127.0.0.1:8000/mcp`, pings the server, and prints each tool's
name and input schema. Requires the server to be running. With the current
registration gap it prints no tools.

### In-memory client (`in_memory_client.py`)

A module of async helper functions (`call_add_tool`, `call_subtract_tool`,
`call_resource`, `call_resource2`, `call_prompt`) that use `Client(mcp)`. It has
**no `__main__` block**, so running it as a module does nothing. Import the
functions from your own script. The tools are only available if
`app.mcp.tools` has been imported first.

### Streamable HTTP client (`http_client.py`)

A module of async helper functions using `StreamableHttpTransport` against
`http://127.0.0.1:8000/mcp`. It also has **no `__main__` block**. Requires the
server to be running; import and call the helpers from your own script.

### LangChain over HTTP (`langchain_http.py`)

```bash
python -m app.mcp.clients.langchain_http
```

The module runs `asyncio.run(fun())` at import time. It opens a Streamable HTTP
session, loads MCP tools with `load_mcp_tools`, creates a ReAct agent, and asks
the model to use the `add` tool. Requires the HTTP server and
`OPENAI_API_KEY`.

### LangChain over STDIO (`langchain_stdio.py`)

The module defines `main()` but has **no `__main__` block and no
`asyncio.run(...)`**, so running it directly does nothing. It is intended to
spawn `python -m app.mcp.server` over STDIO, load tools, and run a ReAct agent.
Call `asyncio.run(main())` yourself after importing it, with
`OPENAI_API_KEY` set.

### LangChain multi-server (`langchain_multi_server.py`)

```bash
python -m app.mcp.clients.langchain_multi_server
```

Builds a `MultiServerMCPClient` with a `stdio-client` (spawns
`python -m app.mcp.server`) and an `http-client` (`http://127.0.0.1:8000/mcp`).
Note that `asyncio.run(client.get_tools())` executes at module import, so the
HTTP server must already be running before the module is imported. Requires
`OPENAI_API_KEY`. The `__main__` block prints the human/AI/tool message
sequence.

## Expected behavior

- With the server started and tools registered, `add` and `subtract` return
  integer results and the LangChain clients ask the model to use `add`.
- Without the registration imports, tool discovery returns an empty list and
  tool calls fail with an unknown-tool error. This is the current state of the
  committed entry point.
- The resource/prompt clients refer to URI forms that do not all match the
  decorators: `resources.py` declares `file:///endpoint{name}` and
  `file:///endpoint2/{name}`, while the clients request `file:///endpoint{name}`,
  `file:///endpoint/{name}`, and `file://endpoint2/{name}`. These are
  inconsistent and are not a verified end-to-end resource path.

## Limitations and notes

- **Registration gap:** the server entry point does not import `tools.py`,
  `resources.py`, or `prompts.py`.
- **Broken imports:** `resources.py` and `prompts.py` import `mcp` from a
  non-existent top-level `server` module.
- **Library-only clients:** `in_memory_client.py`, `http_client.py`, and
  `langchain_stdio.py` have no runnable entry point.
- **Broken test helper:** `tests/test_client_http.py` imports `http_client` from
  `app.mcp.clients.in_memory_client`, which does not define it.
- **Port check message:** `tests/test_port.py` prints "not available" when the
  bind succeeds and "available" on `OSError`, i.e. the messages are inverted.
- **No automated test suite** is runnable as-is; the files in `tests/` are
  helpers rather than a configured pytest suite.
- The server instructions mention `get_average()`, but no such tool exists.
- Never commit `.env` or real keys. This directory's `.gitignore` is empty, so
  add `.env` to your ignore rules when using the project standalone.
