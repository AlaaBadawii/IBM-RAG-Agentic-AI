# BeeAI Framework Lab

Hands-on examples for building **agentic AI systems** with the [BeeAI Framework](https://github.com/i-am-bee/beeai-framework), using its Python agents, tools, requirements, and middleware APIs.

**Status: Educational pattern implementations with experimental APIs and a broken standalone factory demo.** [Course 8](../README.md) · [Certificate](../../README.md)

The lab explores tool use, reasoning, orchestration, human-in-the-loop approval, structured output, prompt templates, and multi-agent coordination. Source presence is not a claim that every script was executed successfully.

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
- [BeeAI Framework](https://github.com/i-am-bee/beeai-framework) (`beeai-framework==0.1.35`) — agents, tools, memory, middleware, emitters
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

From the repository root:

```bash
cd Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/BeeAI-Framework-Lab

python -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows

python -m pip install -r requirements.txt
cp .env.example .env
```

## Configuration

Copy `.env.example` to `.env` and configure the provider used by the chosen script:

| Variable | Purpose |
|---|---|
| `WATSONX_API_KEY` | Local watsonx key, consumed by BeeAI's watsonx adapter; ambient lab auth is also supported |
| `WATSONX_PROJECT_ID` | Consumed by the watsonx adapter for project-scoped requests |
| `WATSONX_URL` | Optional endpoint override consumed by the watsonx adapter |
| `GEMINI_API_KEY` | Consumed by BeeAI's Gemini adapter for `minimal_agent.py` and `structure_output.py` |
| `OPENROUTER_API_KEY` | Read directly by the independent `text.py` experiment; not listed in `.env.example` |

Provider consumption was checked against the pinned framework's
[watsonx adapter](https://github.com/i-am-bee/beeai-framework/blob/python_v0.1.35/python/beeai_framework/adapters/watsonx/backend/chat.py)
and [Gemini adapter](https://github.com/i-am-bee/beeai-framework/blob/python_v0.1.35/python/beeai_framework/adapters/gemini/backend/chat.py).
The adapters, rather than this repo's `llm.py`, read those provider credentials.

Model IDs are hardcoded in `llm.py` and `multi_agent/llm.py`.
`WATSONX_MODEL_ID`, `WATSONX_PROJECT_NAME`, and `GEMINI_CHAT_MODEL` in the template
do not select models for these examples. BeeAI supports a Gemini default-model
variable, but the explicit model identifier supplied here takes precedence.

Scripts importing the factory load `.env` with `override=True`. `basic_chat.py`
does not load `.env`, so its provider variables must already be in the process
environment. `text.py` explicitly loads `.env` from the current directory.

## Running the Examples

All commands are run from the project root with the virtual environment activated.

```bash
python basic_chat.py
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

`python llm.py` is not listed as a working demo: its `main()` passes
`"gemini:gemini-3.5-flash-lite"` to a factory that only accepts `"watsonx"` or
`"gemini"`, causing a `KeyError` before inference. The duplicate standalone
`multi_agent/llm.py` demo has the same mismatch. Other scripts pass the short
provider keys. No script execution is claimed by this documentation update.

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
- **Custom tools**: `simple_calculator_tool.py` implements an input schema and character-allowlisted arithmetic using `eval` with empty builtins; this is different from the ReAct project's bounded AST evaluator.
- **Multi-agent system** (`multi_agent/`): coordinator agent with handoff tools (`HandoffTool`) to destination, weather, and language experts, plus conditional requirements and ask-permission approval.

## Current Status & Known Limitations

- Requires Python 3.12 and valid provider credentials (see [Configuration](#configuration)).
- Examples that call LLMs require working watsonx/Gemini credentials and incur usage costs.
- The multi-agent travel planner pauses for human approval before delegated tool use.
- No offline automated test suite is included; the `test_wiki*.py` files are live example scripts, not evidence of a passed pytest suite.
- `text.py` is an experimental script that calls OpenRouter and is not integrated into the core lab configuration.
- The calculator's allowed characters also permit `**` and very long expressions; it has no explicit exponent/complexity bound.
- Credential presence does not prove that hardcoded model IDs are available to the account/provider.

## License

No license file is tracked in this lab.
