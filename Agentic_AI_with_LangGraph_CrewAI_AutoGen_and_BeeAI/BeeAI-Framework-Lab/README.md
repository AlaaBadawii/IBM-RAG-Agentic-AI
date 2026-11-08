# BeeAI Framework Lab

Hands-on examples for building **agentic AI systems** with the [BeeAI Framework](https://github.com/BeeAI-devs/BeeAI), an open-source framework from IBM for developing, observing, and evaluating AI agents.

This repository is a laboratory of working patterns for LLM-powered agents: tool use, reasoning, orchestration, human-in-the-loop approval, structured output, prompt templates, and multi-agent coordination.

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

The lab contains independent, runnable Python scripts that each demonstrate a single, focused agent capability with the BeeAI Framework. The most advanced example is a multi-agent travel planning system in which a coordinator hands off to specialized expert agents (destination research, weather, language & culture).

## Learning Objectives

- Build LLM-powered agents with the BeeAI `RequirementAgent`.
- Control agent behavior with conditional and ask-permission requirements.
- Add tools (reasoning, retrieval, weather, custom) and trace execution with middleware.
- Coordinate multiple agents via handoff tools.
- Produce structured outputs and reusable prompt templates.
- Compose multi-agent workflows.

## Technologies

- [Python](https://www.python.org/) 3.12+
- [BeeAI Framework](https://github.com/BeeAI-devs/BeeAI) (`beeai-framework`) — agents, tools, memory, middleware, emitters
- LLM providers via BeeAI:
  - IBM watsonx.ai (`watsonx:ibm/granite-4-h-small`)
  - Google Gemini (`gemini:gemini-3.5-flash-lite`)
- Tools demonstrated: `ThinkTool`, `WikipediaTool`, `OpenMeteoTool`, custom calculator tool, handoff tools
- `python-dotenv` for environment configuration

## Repository Structure

```
BeeAI-Framework-Lab/
├── basic_chat.py                  # Basic LLM chat completion
├── llm.py                          # LLM client factory + chat completion example
├── minimal_agent.py               # Minimal RequirementAgent
├── structure_output.py            # Structured output with Pydantic schema
├── dynamic_prompt_template.py     # Simple prompt template rendering
├── simple_calculator_tool.py      # Custom tool + agent integration
├── controlled_execution_agent.py # Conditional requirements (tool orchestration)
├── human_in_the_loop.py           # AskPermissionRequirement (HITL approval)
├── react_pattern_agent.py         # Reasoning + research agent
├── reasoning_enhanced_agent.py   # Systematic reasoning agent
├── test_wiki.py                    # Wikipedia tool smoke test
├── test_wiki_agent.py             # Wikipedia agent with research integrity rules
├── multi_agent/
│   ├── agents.py                  # Travel coordinator multi-agent system
│   └── multi_agent_travel_planner.py
├── text.py                        # Experimental script (OpenRouter) - not part of core lab
├── .env.example
├── requirements.txt
└── .gitignore
```

## Installation

```bash
git clone <repository-url>
cd BeeAI-Framework-Lab

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
| `GEMINI_API_KEY` | Google Gemini API key |
| `GEMINI_CHAT_MODEL` | Gemini chat model id |

## Running the Examples

All commands are run from the project root with the virtual environment activated.

```bash
python basic_chat.py
python llm.py
python minimal_agent.py
python structure_output.py
python dynamic_prompt_template.py
python simple_calculator_tool.py
python controlled_execution_agent.py
python human_in_the_loop.py
python react_pattern_agent.py
python reasoning_enhanced_agent.py
python test_wiki.py
python test_wiki_agent.py
python -m multi_agent.multi_agent_travel_planner
```

The multi-agent travel planner lives in the `multi_agent` package and must be run from the project root with module syntax:

```bash
python -m multi_agent.multi_agent_travel_planner
```

## Agent Patterns Implemented

- **Minimal agent** (`minimal_agent.py`): a `RequirementAgent` with no tools — pure reasoning.
- **Tool use & orchestration**: `controlled_execution_agent.py`, `react_pattern_agent.py`, `reasoning_enhanced_agent.py` use `ThinkTool`, `WikipediaTool`, conditional requirements, and `GlobalTrajectoryMiddleware`.
- **Human-in-the-loop**: `human_in_the_loop.py` uses `AskPermissionRequirement` for approval-gated tool execution.
- **Structured output**: `structure_output.py` uses `create_structure` with a Pydantic schema.
- **Prompt templates**: `dynamic_prompt_template.py` renders reusable templates.
- **Custom tools**: `simple_calculator_tool.py` implements a tool with input schema and safe evaluation.
- **Multi-agent system** (`multi_agent/`): coordinator agent with handoff tools (`HandoffTool`) to destination, weather, and language experts, plus conditional requirements and ask-permission approval.

## Current Status & Known Limitations

- Requires Python 3.12 and valid provider credentials (see [Configuration](#configuration)).
- Examples that call LLMs require working watsonx/Gemini credentials and incur usage costs.
- The multi-agent travel planner pauses for human approval before delegated tool use.
- No automated test suite is included; verification is currently done by running the examples.
- `text.py` is an experimental script that calls OpenRouter and is not integrated into the core lab configuration.

## License

This project does not currently declare a license. A license will be added upon your approval.
