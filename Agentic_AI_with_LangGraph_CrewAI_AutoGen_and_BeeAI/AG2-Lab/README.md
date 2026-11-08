# AutoGen Lab

Hands-on examples for building **agentic AI systems** with [Microsoft AutoGen](https://github.com/microsoft/autogen) (AutoGen 2 / `autogen-agentchat`), an open-source framework for orchestrating multi-agent conversations.

This lab is part of the **IBM RAG & Agentic AI** engineering portfolio — the AutoGen companion to the LangGraph, CrewAI, and BeeAI labs from Course 8 of the IBM RAG and Agentic AI Professional Certificate.

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

The lab contains independent, runnable Python scripts that each demonstrate a single, focused agent capability with AutoGen. The most advanced examples are multi-agent systems built with `GroupChat` and `GroupChatManager`:

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
- [Microsoft AutoGen](https://github.com/microsoft/autogen) (`autogen`, `autogen-agentchat`, `autogen-core`, `pyautogen`) — agents, group chat, tool registration, code execution
- LLM provider: IBM watsonx.ai via the shared AutoGen LLM configuration (`llm_config`)
- Tools demonstrated: `LocalCommandLineCodeExecutor` (matplotlib sine wave), `register_function` (primality check)
- `python-dotenv` for environment configuration, `pydantic` for structured output

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

```bash
git clone <repository-url>
cd AG2-Lab

python -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
cp .env.example .env
```

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

| Variable | Purpose |
|---|---|
| `WATSONX_API_KEY` | IBM watsonx.ai API key |
| `WATSONX_PROJECT_ID` | watsonx project ID |
| `WATSONX_PROJECT_NAME` | watsonx project name |
| `WATSONX_URL` | watsonx endpoint URL |
| `WATSONX_MODEL_ID` | watsonx model id (e.g. `ibm/granite-4-h-small`) |

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
- The healthcare consultation group chat ends when the consultation agent signals completion via the `CONSULTATION_COMPLETE` marker.
- No automated test suite is included; verification is currently done by running the examples.

## License

This project does not currently declare a license. A license will be added upon your approval.
