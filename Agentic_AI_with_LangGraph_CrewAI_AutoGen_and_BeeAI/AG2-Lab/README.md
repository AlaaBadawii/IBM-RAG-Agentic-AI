# AG2 Lab — AutoGen-Style Conversational Agents

Hands-on examples for building **agentic AI systems** with [AG2](https://github.com/ag2ai/ag2), the maintained AutoGen lineage that exposes the `autogen` import API (`ConversableAgent`, `GroupChat`, `GroupChatManager`, and code executors).

**Status: Implemented educational scripts; provider/API compatibility is not validated by this documentation update.** [Course 8](../README.md) · [Certificate](../../README.md)

This is the AG2 companion to the LangGraph, CrewAI, and BeeAI labs in **Course 8 — Agentic AI with LangGraph, CrewAI, AutoGen and BeeAI**. The official course title uses AutoGen; these scripts use the AG2/`autogen` conversational API, not Microsoft's `autogen_agentchat`/`autogen_core` API.

The lab contains independent, runnable Python scripts that each demonstrate a single, focused agent capability with AutoGen: coding assistants with local code execution, tool calling, structured output, human-in-the-loop approval, conversational tutoring, specialized-agent teams, and multi-agent group chat.

## Table of Contents

- [Overview](#overview)
- [Learning Objectives](#learning-objectives)
- [Technologies](#technologies)
- [Repository Structure](#repository-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Examples](#running-the-examples)
- [Agent Patterns Implemented](#agent-patterns-implemented)
- [Current Status & Known Limitations](#current-status--known-limitations)
- [License](#license)

## Overview

The source contains independent agent examples. The coding assistant is an agent pair; the healthcare example uses `GroupChat` and `GroupChatManager`:

- **Coding assistant** (`built_in_agents.py`) — an assistant agent with a Python coding expert system message pairs with a user proxy agent that writes and executes code locally (matplotlib sine wave) via `LocalCommandLineCodeExecutor`.
- **Healthcare consultation** (`AutoMed_Healthcare_bot/automed.py`) — a patient → diagnosis → pharmacy → consultation group chat for symptom triage.

Supporting single-agent examples cover tool use, structured output, human-in-the-loop control, and conversational patterns.

## Learning Objectives

- Build LLM-powered agents with `ConversableAgent` (system messages, human input modes, termination conditions).
- Add tools with `register_function` and execute generated code locally via `LocalCommandLineCodeExecutor`.
- Enforce structured output with Pydantic schemas (`response_format`).
- Add human-in-the-loop approval flows via `human_input_mode`.
- Coordinate multi-agent teams with `GroupChat` and `GroupChatManager` (speaker selection, termination).

## Technologies

- [Python](https://www.python.org/) 3.12+
- AG2's `autogen` import API — agents, group chat, tool registration, code execution
- LLM provider: IBM watsonx.ai via the shared AutoGen LLM configuration (`llm_config`)
- Tools demonstrated: `LocalCommandLineCodeExecutor` (matplotlib sine wave), `register_function` (primality check)
- `python-dotenv` for environment configuration, `pydantic` for structured output

The committed manifest pins `autogen==0.14.1` and `pyautogen==0.10.0`. It also
lists `autogen-agentchat==0.7.5` and `autogen-core==0.7.5`; none of these scripts
imports `autogen_agentchat` or `autogen_core`. The mixed manifest is retained,
but these are distinct package/API names, not interchangeable framework versions.

## Repository Structure

```
AG2-Lab/
├── built_in_agents.py                      # Coding assistant + user proxy + local code execution (sine wave)
├── tool_calling.py                         # register_function tool + math agent pair
├── structure_output.py                     # Structured output via Pydantic schema
├── human_in_the_loop.py                    # Bug triage with ALWAYS-on-human input
├── student_tutor_conversable_agent.py    # Conversational tutoring (student <-> tutor)
├── technical_expert_agent.py              # Specialized expert team (tech / creative / business)
├── mutli_agent.py                         # Lesson planning group chat (planner, reviewer, teacher)
├── llm_config.py                           # Shared AutoGen LLM configuration (watsonx.ai)
├── AutoMed_Healthcare_bot/
│   ├── automed.py                         # Healthcare consultation group chat
│   └── llm_config.py                      # Healthcare variant (temperature 0.0)
├── coding/
│   └── sine_wave.png                      # Generated sine-wave plot
├── .env.example
├── requirements.txt
└── .gitignore
```

## Installation

From the repository root:

```bash
cd Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/AG2-Lab

python -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows

python -m pip install -r requirements.txt
cp .env.example .env
```

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

| Variable | Purpose |
|---|---|
| `WATSONX_API_KEY` | IBM watsonx.ai API key |
| `WATSONX_PROJECT_ID` | watsonx project ID |
| `WATSONX_URL` | watsonx endpoint URL |
| `WATSONX_MODEL_ID` | watsonx model id (e.g. `ibm/granite-4-h-small`) |

These four variables are read directly by `llm_config.py` at import time.
`WATSONX_PROJECT_NAME` is in the example file but is not consumed. The config
uses `WATSONX_URL + "/ml/v1"` as an OpenAI-compatible base URL and sends
`project_id` through `extra_body`; compatibility of that path and credential
format with the selected watsonx endpoint is not established by a static review.

## Running the Examples

All commands are run from the lab root with the virtual environment activated.

```bash
python built_in_agents.py
python tool_calling.py
python structure_output.py
python human_in_the_loop.py
python student_tutor_conversable_agent.py
python technical_expert_agent.py
python mutli_agent.py
python AutoMed_Healthcare_bot/automed.py
```

Notes:

- `built_in_agents.py` starts a coding assistant that writes and executes a matplotlib sine-wave script via the local code executor; the plot is saved to `coding/sine_wave.png`.
- `tool_calling.py` registers a primality-check function and routes tool calls between the asker and checker agents.
- `structure_output.py` uses a Pydantic `TicketSummary` schema as the structured output for the support agent.
- `human_in_the_loop.py` pauses for human input on every interaction (`human_input_mode="ALWAYS"`).
- `AutoMed_Healthcare_bot/automed.py` prompts for patient symptoms via stdin before starting the group chat.

## Agent Patterns Implemented

- **Coding assistant** (`built_in_agents.py`): an `AssistantAgent` with a Python coding expert system message pairs with a `UserProxyAgent` (`human_input_mode="NEVER"`) that executes generated code via `LocalCommandLineCodeExecutor`.
- **Tool calling** (`tool_calling.py`): a Python function (`is_prime`) is registered with `register_function` and invoked by a math agent through a checker agent.
- **Structured output** (`structure_output.py`): `llm_config["response_format"]` is set to a Pydantic `TicketSummary` schema for the support agent.
- **Human-in-the-loop** (`human_in_the_loop.py`): a `ConversableAgent` uses `human_input_mode="ALWAYS"` for interactive approval during bug triage.
- **Conversational agents** (`student_tutor_conversable_agent.py`, `technical_expert_agent.py`): plain `ConversableAgent` chat chains for tutoring and specialized expertise.
- **Group chat** (`mutli_agent.py`, `AutoMed_Healthcare_bot/automed.py`): multi-agent orchestration with `GroupChat` + `GroupChatManager` — lesson planning team and healthcare consultation team.

## Current Status & Known Limitations

- Requires Python 3.12 and valid IBM watsonx.ai credentials (see [Configuration](#configuration)).
- Examples that call LLMs require working credentials and incur usage costs.
- The coding-assistant example executes generated code locally with a 30s timeout in `coding/`.
- The healthcare group chat uses round-robin selection and `max_round=5`. `CONSULTATION_COMPLETE` is requested in a prompt, but no explicit termination predicate consumes that marker.
- No automated test suite or recorded result from this documentation update is included. Some scripts construct agents and start chats at import time.

## License

No license file is tracked in this lab.
