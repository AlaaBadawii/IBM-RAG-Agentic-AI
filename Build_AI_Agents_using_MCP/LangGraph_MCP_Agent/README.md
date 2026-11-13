# LangGraph MCP Agent

A LangGraph ReAct agent that connects to multiple MCP (Model Context Protocol) servers using LangChain adapters.

## Features

- ReAct agent powered by OpenAI (`gpt-5.4-mini`)
- MCP server clients via `langchain-mcp-adapters`
- Persistent conversation memory with `InMemorySaver`
- MCP servers:
  - **Context7** — library documentation (streamable HTTP)
  - **Met Museum** — museum collection (stdio via `npx`)
- Interactive CLI menu to query the agent

## Quick Start

1. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install langchain-core langchain-mcp-adapters langchain-openai langgraph
```

3. Set your OpenAI API key:

```bash
export OPENAI_API_KEY=sk-...
```

4. Run the agent:

```bash
python mian.py
```

## Requirements

- Python 3.10+
- OpenAI API key
- Node.js (for the `npx metmuseum-mcp` stdio server)
