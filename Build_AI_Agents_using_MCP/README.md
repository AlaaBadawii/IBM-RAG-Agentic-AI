# Build AI Agents Using MCP

Practical projects completed while working through the IBM course **Build AI
Agents using MCP**, part of the **IBM RAG and Agentic AI Professional
Certificate** on Coursera.

The repository is a learning portfolio: it starts by consuming existing MCP
servers, then builds servers and clients with FastMCP, integrates MCP tools into
LangChain/LangGraph agents, and finishes with advanced transport and security
patterns.

## Overview

The **Model Context Protocol (MCP)** is an open protocol that standardizes how
AI applications expose and consume tools, resources, and prompt templates. An
MCP **server** publishes capabilities; an MCP **client** (often an LLM host)
discovers and invokes them over a transport such as STDIO or Streamable HTTP.

This repository demonstrates that client/server model end to end:

- Connecting to third-party MCP servers.
- Building FastMCP servers with tools, resources, and prompts.
- Writing interactive clients and transport-specific clients.
- Wrapping MCP tools as LangChain tools for LangGraph ReAct agents.
- Using Streamable HTTP, resource templates, and sampling.
- Enforcing permissions, risk levels, approval, and audit logging.

The projects are educational. Several retain limitations that are documented in
their individual READMEs rather than hidden.

## Course Information

- **Course:** [Build AI Agents using MCP](https://www.coursera.org/learn/build-ai-agents-using-mcp/home/welcome)
- **Program:** [IBM RAG and Agentic AI Professional Certificate](https://www.coursera.org/professional-certificates/ibm-rag-and-agentic-ai)
- **Provider:** IBM Skills Network, offered on Coursera
- **Author of this repository:** personal learning implementations, not official
  IBM material

## Projects

The projects are listed in the order they build on one another.

### 1. [Run Existing MCP Servers](Run_Existing_MCP_Servers/README.md)

Connects to the hosted and local variants of the **Context7** MCP server using
the FastMCP `Client`. One script uses a `StdioTransport` that launches
`@upstash/context7-mcp` through `npx`; the other uses a
`StreamableHttpTransport` pointed at `https://mcp.context7.com/mcp`. Both list
the server's tools and call `resolve-library-id` and `query-docs`. This is the
entry point for consuming an existing MCP server without writing one.

### 2. [MCP Client Lab](MCP_Client_Lab/README.md)

A minimal FastMCP **STDIO server** (`lab-server`) plus an interactive terminal
client. The server exposes `echo` and `write_file` tools, a
`file://resources/{filename}` resource template, and a `review_file` prompt. The
client spawns the server as a subprocess and supports listing/calling tools,
listing/reading resources, and listing/running prompts. File access is contained
to the project directory, and resources are contained to `resources/`.

### 3. [FastMCP Server & Client](FastMCP_Server_Client/README.md)

A calculator MCP server with intended `add`/`subtract` tools, file resources, and
a `review_code` prompt, together with several client examples: in-memory,
Streamable HTTP, STDIO, and a LangChain multi-server agent. The README documents
the current module wiring precisely, including the fact that the server entry
point does not import the tool-registration modules and that the resource and
prompt modules use an import that does not resolve.

### 4. [LangGraph MCP Agent](LangGraph_MCP_Agent/README.md)

A LangGraph ReAct agent built with `langchain-mcp-adapters` that aggregates tools
from two MCP servers: **Context7** over Streamable HTTP and the **Met Museum**
server over STDIO via `npx`. It uses an OpenAI chat model, keeps conversation
memory with `InMemorySaver`, and provides an interactive CLI. The entry point
file is named `mian.py`.

### 5. [MCP Advanced Lab](MCP_Advanced_Lab/README.md)

A FastMCP **HTTP file server** and two Gradio front ends. The server exposes
workspace-confined file tools (`read_file`, `write_file`, `list_files`), a
`file://workspace/{filename}` resource, two prompts, and a sampling-based
`analyze_code` tool. One client is a protocol-focused GUI; the other is an AI
host that adapts MCP tools, resources, and prompts to OpenAI function calling.
Path containment is enforced with `Path.resolve()` and `is_within_roots`.

### 6. [MCP Security Lab](MCP_Security_Lab/README.md)

A permission-aware MCP server with low/medium/high/critical risk annotations,
per-tool and per-argument permission policies, and an audit log. It includes a
Gradio permission-management client and an AI host with risk assessment and an
approval flow. `execute_command` is simulated, elicitation is conceptual, and the
README records the path-containment and approval-handling caveats found in the
code.

## Technologies and Concepts

- **MCP / FastMCP:** `FastMCP` servers, `Client`, tool/resource/prompt
  registration, resource templates, prompts, sampling, STDIO and Streamable HTTP
  transports.
- **MCP Python SDK:** `ClientSession`, `StdioServerParameters`, `stdio_client`,
  `streamablehttp_client`, `TextContent`, `AnyUrl`.
- **LangChain / LangGraph:** `langchain-mcp-adapters`
  (`MultiServerMCPClient`, `load_mcp_tools`), `create_react_agent`,
  `InMemorySaver`, OpenAI chat models.
- **LLM access:** OpenAI Python SDK (`openai`) and `langchain-openai`; API keys
  are read from environment variables.
- **User interfaces:** Gradio chat and control panels.
- **Supporting tools:** Pydantic, `python-dotenv`, Node.js/`npx` (for Node-based
  MCP servers such as Context7 and Met Museum), and `uvicorn` for HTTP serving.
- **Security concepts:** allow/ask/deny policies, risk levels, audit logging,
  approval prompts, elicitation (conceptual), workspace/roots containment.

## Repository Structure

```text
Build_AI_Agents_using_MCP/
├── README.md
├── Run_Existing_MCP_Servers/
│   ├── README.md
│   ├── local_mcp.py
│   └── remote_mcp.py
├── MCP_Client_Lab/
│   ├── README.md
│   ├── mcp_client.py
│   ├── mcp_server.py
│   ├── project_info.txt
│   ├── requirements.txt
│   ├── .gitignore
│   └── resources/
├── FastMCP_Server_Client/
│   ├── README.md
│   ├── index.py
│   ├── requirements.txt
│   ├── requiremnets.txt
│   ├── .env.example
│   ├── .gitignore
│   ├── app/
│   │   ├── config.py
│   │   ├── utils.py
│   │   └── mcp/
│   │       ├── server.py
│   │       ├── tools.py
│   │       ├── resources.py
│   │       ├── prompts.py
│   │       └── clients/
│   │           ├── in_memory_client.py
│   │           ├── http_client.py
│   │           ├── langchain_http.py
│   │           ├── langchain_stdio.py
│   │           └── langchain_multi_server.py
│   ├── path/
│   └── tests/
├── LangGraph_MCP_Agent/
│   ├── README.md
│   ├── mian.py
│   ├── .env.example
│   └── .gitignore
├── MCP_Advanced_Lab/
│   ├── README.md
│   ├── mcp_http_server.py
│   ├── mcp_http_client_base.py
│   ├── mcp_http_client_app.py
│   ├── mcp_http_host_app.py
│   ├── .gitignore
│   └── workspace/
├── MCP_Security_Lab/
│   ├── README.md
│   ├── mcp_permission_server.py
│   ├── mcp_permission_client_base.py
│   ├── mcp_permission_client_app.py
│   ├── mcp_permission_host_app.py
│   ├── .gitignore
│   └── data/
│       ├── permissions.json
│       └── audit.log
```

Generated virtual environments, `__pycache__/`, and local `.env` files should not
be committed. Each project README lists the ignore rules it relies on.

## Getting Started

There is **no single installation procedure** for the whole repository: the
projects were built at different times with different dependency sets, and four
of the six do not include a `requirements.txt`. Create a separate virtual
environment per project.

Common prerequisites:

- **Python 3.10+** for most projects; `MCP_Client_Lab` documents Python 3.12 and
  pins its dependencies.
- **Node.js / `npx`** for the projects that launch Node-based MCP servers
  (`Run_Existing_MCP_Servers/local_mcp.py`, `LangGraph_MCP_Agent`).
- **Network access** for Context7, the Met Museum server, and OpenAI-backed
  clients.
- **`OPENAI_API_KEY`** for the LangChain/LangGraph and OpenAI-hosted clients.
  The Gradio protocol clients that do not call an LLM need no key.

Start with [Run Existing MCP Servers](Run_Existing_MCP_Servers/README.md), then
[MCP Client Lab](MCP_Client_Lab/README.md). Each project README contains its own
setup, environment variables, and exact run commands.

## Learning Outcomes

By working through these projects, the implementations demonstrate the ability
to:

- Consume existing MCP servers over both STDIO and Streamable HTTP.
- Define MCP servers with tools, resources/resource templates, and prompts.
- Build interactive MCP clients that discover and invoke capabilities.
- Bridge MCP tools into LangChain/LangGraph ReAct agents and combine multiple
  servers in one agent.
- Serve MCP over HTTP and expose the same capabilities through Gradio and OpenAI
  function calling.
- Apply workspace containment, permission policies, risk levels, approval, and
  audit logging to tool execution.
- Recognize where an educational MCP implementation is incomplete or unsafe and
  document it accurately.

## Acknowledgments

- Course content and lab scaffolding: **IBM Skills Network** and **Coursera**.
- MCP specification and SDKs: the Model Context Protocol project.
- FastMCP, LangChain, LangGraph, and Gradio maintainers.
- Context7 and the Met Museum MCP server used in the agent examples.

This repository contains personal educational implementations. It is **not** an
official IBM repository, and the code is provided as-is for learning.
