# LangGraph MCP Agent

A LangGraph ReAct agent that connects to multiple MCP servers through
`langchain-mcp-adapters`, with conversation memory and an interactive CLI.

**Status: implemented educational agent; depends on external MCP servers and an
OpenAI-compatible model.**

Course 9: **Build AI Agents using MCP** (IBM RAG and Agentic AI Professional
Certificate). [Course overview](../README.md)

## Overview

The agent combines two MCP servers into one tool set:

| MCP server | Transport | How it is started |
| --- | --- | --- |
| Context7 | Streamable HTTP | Connects to `https://mcp.context7.com/mcp` |
| Met Museum | STDIO | Runs `npx -y metmuseum-mcp` |

`MultiServerMCPClient` discovers the tools, `create_react_agent` builds a ReAct
agent over them, and `InMemorySaver` keeps the conversation thread in memory.
The model is a `ChatOpenAI` instance configured as `gpt-5.4-mini`.

The CLI introduces the agent, then lets you ask questions or quit. The system
message tells the model it can use Context7 for library documentation and the
Met Museum server for collection exploration.

## Concepts demonstrated

- Aggregating tools from multiple MCP servers with different transports.
- Loading MCP tools as LangChain tools (`client.get_tools()`).
- Building a LangGraph ReAct agent with `create_react_agent`.
- Adding short-term conversation memory with `InMemorySaver` and a
  `thread_id`.
- Reading provider configuration from `.env` with `python-dotenv`.

## Technologies and dependencies

- Python 3.10+
- `langchain-core`, `langchain-openai`, `langchain-mcp-adapters`, `langgraph`
- `python-dotenv`
- Node.js with `npx` (for the Met Museum STDIO server)
- Network access to Context7 and the npm registry

There is **no `requirements.txt`** in this directory. Install the packages
directly:

```bash
python -m pip install langchain-core langchain-mcp-adapters langchain-openai langgraph python-dotenv
```

## Project structure

```text
LangGraph_MCP_Agent/
├── README.md
├── mian.py          # Agent entry point (filename is intentionally spelled this way)
├── .env.example     # OPENAI_API_KEY placeholder
└── .gitignore
```

## Prerequisites

- Python 3.10+.
- An OpenAI API key with access to the configured model.
- Node.js and `npx` available on `PATH`.
- Outbound network access.

## Setup

```bash
cd LangGraph_MCP_Agent

python -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows

python -m pip install langchain-core langchain-mcp-adapters langchain-openai langgraph python-dotenv

cp .env.example .env
# edit .env and set OPENAI_API_KEY
```

`.env.example` contains:

```text
OPENAI_API_KEY=sk-...
```

The script calls `load_dotenv()` and raises `ValueError` at startup if
`OPENAI_API_KEY` is missing. `.env` is git-ignored.

## Run

```bash
python mian.py
```

The filename is `mian.py` (not `main.py`), so use the exact name.

On startup the agent prints a brief introduction, then shows:

```text
Menu:
1. Ask agent a question
2. Quit
```

Enter `1`, type a question, and the agent answers using the available tools.
`Ctrl+C` exits with a message.

## Execution flow

1. Load environment variables and validate `OPENAI_API_KEY`.
2. Create `MultiServerMCPClient` with the Context7 and Met Museum entries.
3. Create `ChatOpenAI(model="gpt-5.4-mini")`.
4. Fetch the combined tool list with `await client.get_tools()`.
5. Create an `InMemorySaver` checkpointer and a `thread_id` of
   `"conversation_id"`.
6. Build the ReAct agent with `create_react_agent`.
7. Send an initial system + user message, print the introduction, and enter the
   question loop.

## Configuration details

- The model ID is hard-coded as `gpt-5.4-mini` in `mian.py`. If your account
  does not expose that model, change the ID to one you can use.
- The Context7 URL and the Met Museum command/arguments are hard-coded.
- Memory is **in-process only**: `InMemorySaver` is not a database, so the
  conversation does not survive a restart.
- There is no model-selection, temperature, or server-URL environment variable.

## Expected output

A short agent introduction followed by the menu. Questions about a library or
the museum should trigger the corresponding MCP tools. Because the answers come
from a live model and live servers, exact wording varies.

## Limitations

- Requires network access, a valid OpenAI key, and a working `npx`/Node.js
  installation.
- The Met Museum server is fetched at runtime by `npx`; an npm outage or package
  change can break startup.
- The Context7 endpoint is a hosted service and may rate-limit or change.
- No error handling around individual MCP servers; a failing server can abort
  startup.
- No automated tests.
- Conversation memory is not persistent across runs.
