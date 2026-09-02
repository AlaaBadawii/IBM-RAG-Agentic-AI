# AI Agents From Scratch — Evidence (earlier milestone)

Three framework-free autonomous agents. **Earlier** milestone in
`/home/alaabadawii/LLMs/AI-Agents/`. Source: `../completed_projects/ai_agents_from_scratch.md`.

## Evidence state

VERIFIED (implemented locally, experimental, not deployed).

## What was actually built (evidence-backed)

1. **README Agent** (`Readme_Agent/`) — reads a Python project and writes its
   README (written by the agent itself). GAME framework (Goals, Actions, Memory,
   Environment); decorator-based `ActionRegistry` registering tools from type
   hints/docstrings; tag-based filtering; terminal-action pattern.
2. **Agent Assistant** (`Agent_Assistant/`) — general-purpose conversational
   agent exploring/reading files. OpenAI-style tool-calling protocol
   (`tool_calls` + `tool` role), multi-turn memory, parallel tool-call handling;
   `TOOLS` (LLM-facing schema) vs `TOOL_FUNCTIONS` (Python callables); has
   `test_memory.py` unit tests.
3. **Multi Agents** (`Multi_Agents/`) — lightweight multi-agent orchestrator;
   routes requests to a question-generator agent backed by registered tools.

## Concepts actually implemented (not just read)

- Agent loop (~50 lines: call LLM → parse → execute tools → repeat).
- Memory as a list of `{role, content}`; LLMs pass context each call.
- Tool calling as a structured protocol; LLM never runs code directly.
- Explicit termination via tool; registry/decorator tool registration; multi-agent
  routing.

## Supporting infrastructure

- Docker: `docker-compose.yml` + per-agent `Dockerfile`s (reproducible containers).
- LLM access: `litellm` + OpenRouter.
- Deliberately **no agent framework** (no LangChain/CrewAI).

## Technologies demonstrated

Pure Python, `litellm`, OpenRouter, Docker, JSON tool-calling protocol.

## Publicly safe claim

- "I built AI agents from scratch in Python — implementing the agent loop, tool
  calling, memory, a tool registry, and multi-agent orchestration without a
  framework."

## Avoid

- "I am an expert AI Agent engineer." (experimental, not production.)

## Relationship

- Earlier foundation in the chain: **AI Agents From Scratch → Evaluator Core →
  Quizey Phase 3.**

## Evidence source

`../completed_projects/ai_agents_from_scratch.md`,
`/home/alaabadawii/LLMs/AI-Agents/README.md` (+ `Readme_Agent/`, `Agent_Assistant/`,
`Multi_Agents/`, `docker-compose.yml`), git log.