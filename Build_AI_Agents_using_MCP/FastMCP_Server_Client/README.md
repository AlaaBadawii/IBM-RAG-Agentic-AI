# FastMCP Server & Client

A minimal Model Context Protocol (MCP) project built with [FastMCP](https://gofastmcp.com/). It exposes a simple calculator MCP server (add/subtract tools, document resources, and a code-review prompt) alongside several client examples: in-memory, HTTP (Streamable HTTP), STDIO, and LangChain multi-server integration.

## Purpose

Demonstrate how to:

- Build and run an MCP server with FastMCP.
- Call MCP tools, read resources, and fetch prompts from different client transports.
- Integrate MCP servers with LangChain/LangGraph agents using stdio and Streamable HTTP.
- Aggregate tools from multiple MCP servers (stdio + HTTP) with `MultiServerMCPClient`.

## Project structure

```
FastMCP_Server_Client/
├── index.py                 # Simple HTTP client entry point
├── README.md                # This file
├── requirements.txt         # Python dependencies
├── .env.example             # Example environment variables
├── .env                     # Local environment variables (create from .env.example)
├── .gitignore               # Git ignore rules
├── app/
│   ├── __init__.py
│   ├── config.py            # PORT and LLM_MODEL settings
│   └── utils.py             # Helpers (make_dir, print_stream_info)
│   └── mcp/
│       ├── __init__.py
│       ├── server.py        # FastMCP Calculator MCP server (HTTP transport)
│       ├── tools.py         # add / subtract tools
│       ├── resources.py     # file:/// resources
│       ├── prompts.py       # review_code prompt
│       └── clients/
│           ├── __init__.py
│           ├── in_memory_client.py   # In-memory FastMCP client
│           ├── http_client.py        # Streamable HTTP client
│           ├── langchain_http.py     # LangChain agent over HTTP
│           ├── langchain_stdio.py    # LangChain agent over STDIO
│           └── langchain_multi_server.py  # LangChain agent over stdio + HTTP
├── path/                    # Documents served by the MCP server
│   ├── README.txt
│   └── examples.txt
└── tests/
    ├── __init__.py
    ├── test_client_http.py  # HTTP client test helper
    └── test_port.py         # Port availability check
```

## Prerequisites

- Python 3.10+
- A virtual environment (recommended)

## Setup

1. Clone or open this folder.

2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure environment variables:

```bash
cp .env.example .env
# Edit .env as needed (OPENAI_API_KEY, etc.)
```

The project uses `OPENAI_API_KEY` for LangChain/LangGraph agent runs that call `openai:gpt-5-nano`. Set it in `.env` before running those clients.

## Dependencies

See `requirements.txt`. Core packages:

- `fastmcp` — MCP server/framework
- `mcp` — MCP Python SDK
- `langchain-mcp-adapters` — LangChain MCP tool adapters
- `langgraph`, `langgraph-prebuilt` — LangGraph agents
- `langchain-openai`, `openai` — LLM model access
- `httpx`, `uvicorn` — HTTP transport/server
- `python-dotenv` — environment variable loading

## Run the MCP server

Start the HTTP (Streamable HTTP) server on `http://127.0.0.1:8000/mcp`:

```bash
python -m app.mcp.server
```

The server exposes:
- Tools: `add`, `subtract`
- Resources: `file:///endpoint{name}`, `file:///endpoint2/{name}`
- Prompt: `review_code`

Keep the server running in one terminal while running clients in another.

## Run the clients

### 1. In-memory client

Connects directly to the in-process `mcp` object (no network):

```bash
python -m app.mcp.clients.in_memory_client
```

It provides `call_add_tool`, `call_subtract_tool`, `call_resource`, `call_resource2`, and `call_prompt`.

### 2. HTTP client (Streamable HTTP)

Connects to the running server at `http://127.0.0.1:8000/mcp`:

```bash
python -m app.mcp.clients.http_client
```

Requires the server to be running first.

### 3. STDIO client (LangChain)

Spawns the server as a subprocess over stdio and runs a LangGraph agent:

```bash
python -m app.mcp.clients.langchain_stdio
```

Requires `OPENAI_API_KEY` in `.env`.

### 4. LangChain multi-server integration

Aggregates tools from both a stdio server and an HTTP server, then runs a LangGraph agent:

```bash
python -m app.mcp.clients.langchain_multi_server
```

Requires the HTTP server running (for the `http-client`) and `OPENAI_API_KEY` in `.env`.

### 5. Simple HTTP client (index.py)

Lists tools from the running HTTP server:

```bash
python index.py
```

Requires the server to be running first.

## Notes

- `requiremnets.txt` is an empty, misspelled file left in the repo; use `requirements.txt` for installation.
- `app/mcp/resources.py` and `app/mcp/prompts.py` import `mcp` via `from server import mcp`, which only resolves when those modules are imported from the project root with `server` on `sys.path`. They are not imported by `app.mcp.server`.

## License

This project is provided as-is for learning and demonstration purposes.
