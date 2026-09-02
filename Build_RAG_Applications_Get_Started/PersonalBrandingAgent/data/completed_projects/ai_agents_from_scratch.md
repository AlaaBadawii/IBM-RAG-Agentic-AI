# AI Agents From Scratch — three framework-free agents

> **Relationship note (from the cross-source audit):** this project is the
> **earlier** milestone in the `/home/alaabadawii/LLMs/AI-Agents/` folder (the
> 3 framework-free agents). **Evaluator Core** (`../in_progress_projects/evaluator_core.md`)
> is a **later, separate** build in the same folder (two-stage Judge+Critic
> grading engine), not part of these three agents. Do not merge them. The chain
> continues: Evaluator Core → Quizey Phase 3 (AI grading / open-ended review).

## Status
COMPLETED (implemented and run locally; experimental, not deployed).
Source: `/home/alaabadawii/LLMs/AI-Agents/` (git repo, 10 commits).

## What this is
Three autonomous AI agents built deliberately WITHOUT frameworks (no LangChain,
no CrewAI) to learn the underlying mechanics. Author's stated goal in README:
"understand how agents actually work before reaching for abstractions."

## Agents actually implemented

### 1. README Agent (`Readme_Agent/`)
- Reads an entire Python project and writes its own README.md (the folder's
  README was written by the agent itself).
- GAME framework: Goals, Actions, Memory, Environment.
- Decorator-based `ActionRegistry` that auto-registers tools from type hints and
  docstrings; tag-based tool filtering; a "terminate" terminal-action pattern.
- Files: `action.py`, `action_registry.py`, `decorators.py`, `agent.py`,
  `environment.py`, `memory.py`, `llm.py`, `tools.py`, `main.py`.

### 2. Agent Assistant (`Agent_Assistant/`)
- General-purpose conversational agent that explores/reads files.
- OpenAI-style tool calling protocol (`tool_calls` + `tool` role messages),
  multi-turn memory, parallel tool-call handling.
- Clean separation of `TOOLS` (LLM-facing schema) vs `TOOL_FUNCTIONS`
  (Python callables).
- Files: `agent.py`, `memory.py`, `tool_registry.py`, `tools/`, `Prompts.py`,
  plus `test_memory.py` (unit tests).

### 3. Multi Agents (`Multi_Agents/`)
- Lightweight multi-agent orchestrator: top-level orchestrator routes requests
  to a question-generator agent backed by registered tools.
- Agent registration/routing, tool-backed question generation + validation,
  terminal workflow via OpenRouter.
- Files: `agents/`, `registery/`, `tools/`, `llm.py`, `main.py`.

## Supporting infrastructure
- Docker support: `docker-compose.yml` + per-agent `Dockerfile`s (reproducible
  containers; git log "Add Docker support...").
- Shared pattern: `litellm` + OpenRouter for LLM access.

## Technologies / frameworks
Pure Python, `litellm`, OpenRouter API, Docker, JSON tool-calling protocol.
Deliberately no agent framework.

## Concepts actually implemented (not just read)
- The agent loop (call LLM -> parse -> execute tools -> repeat), ~50 lines.
- Memory as conversation-history list of `{role, content}` dicts.
- Tool calling as a structured protocol; the LLM never runs code directly.
- Explicit termination via a terminate tool.
- Registry/decorator-based tool registration with schema generation.
- Multi-agent routing/orchestration.

## Lessons supported (from the author's own README)
- "The agent loop is just: call LLM → parse → if tool call, execute → repeat."
- "Memory is just a list"; LLMs have no memory — you pass it every time.
- "Termination is explicit" — the agent stops only because you give it a tool.
- Frameworks "become tools you choose, not black boxes you depend on."

## Evidence / provenance
`/home/alaabadawii/LLMs/AI-Agents/README.md` (architecture + "What I Learned")
`/home/alaabadawii/LLMs/AI-Agents/Readme_Agent/`
`/home/alaabadawii/LLMs/AI-Agents/Agent_Assistant/`
`/home/alaabadawii/LLMs/AI-Agents/Multi_Agents/`
`/home/alaabadawii/LLMs/AI-Agents/docker-compose.yml`
`git log`: "Initial commit - AI Agents project", "ADD: README-Agent && Assistant-Agent", "Add Docker support..."

## Accurate skill assessment
Demonstrates understanding of agent internals at a working, course-project
level. These are local, experimental agents — not production systems. The
README itself says frameworks were avoided as a learning choice, not because
frameworks were mastered.