# AI Math Assistant

A LangChain-based mathematical assistant that performs arithmetic via tools
and can look up factual information on Wikipedia.

**Status: Implemented tool exercises and agent wiring; registry/import-time limitations remain.**

Course 6: **Fundamentals of Building AI Agents** (IBM RAG and Agentic AI Professional Certificate). [Course overview](../README.md) · [Certificate](../../README.md)

## Features

- Math tools: `add_numbers`, `add_numbers_with_options`, `sum_numbers_with_complex_output`, `sum_numbers_from_text`, `subtract_numbers`, `multiply_numbers`, `divide_numbers`
- Knowledge tool: `search_wikipedia`
- Agent wiring in `src/agent.py` using `langchain.agents.create_agent`
- LLM configured in `src/llm.py` (OpenRouter-compatible endpoint)
- Pytest suite in `tests/` (37 test functions across 8 modules; Wikipedia mocked, and tool tests do not import the live LLM)

## Project structure

```
AI_Math_Assistant/
├── src/
│   ├── agent.py
│   ├── llm.py
│   └── tools.py
├── tests/
│   ├── test_add_numbers.py
│   ├── test_add_numbers_with_options.py
│   ├── test_divide_numbers.py
│   ├── test_multiply_numbers.py
│   ├── test_search_wikipedia.py
│   ├── test_subtract_numbers.py
│   ├── test_sum_numbers_from_text.py
│   └── test_sum_numbers_with_complex_output.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Setup

```bash
cd Fundamentals_of_Building_AI_Agents/AI_Math_Assistant

python3 -m venv venv
source venv/bin/activate

python -m pip install -r requirements.txt

cp .env.example .env
# edit .env with your own keys
```

Required variables (see `.env.example`):

- `OPENROUTER_API_KEY` — your OpenRouter API key (**required**)
- `BASE_URL` — set to `https://openrouter.ai/api/v1` for OpenRouter; the source does not supply that default itself

The model ID is fixed to `deepseek/deepseek-v4-flash` in `src/llm.py`; no model-selection environment variable is read.

## Run the Agent Example

From the project root after setup:

```bash
cd src
python agent.py
```

The script uses flat imports (`from llm import llm`, `import tools`), so running
`python -m src.agent` from the project root does not match its import layout. The
retained example asks the agent to add three GDP values; it is not an interactive CLI.

Importing `llm.py` makes an immediate live greeting request before the agent
example runs. A real key, provider/model access, and network connectivity are
therefore required for agent execution, even during import.

## Run tests

```bash
python -m pytest tests/ -v
```

No API key or network access needed — the Wikipedia tool is mocked in tests.

Run tests from the **project root**, not `src/`. They cover tool behavior, not
agent startup or a live provider call. The count above is a source inventory;
no new pass result or coverage percentage is claimed.

## Notes

- `.env` is git-ignored. Never commit real keys.
- `venv/`, `__pycache__/`, and `.pytest_cache/` are git-ignored.
- `agent.py` discovers all public callables in `tools.py`, which also exposes imported `tool` and `WikipediaAPIWrapper` helpers. It is not an explicit allowlist of the eight declared tools; registry/API compatibility needs a separate code review.
