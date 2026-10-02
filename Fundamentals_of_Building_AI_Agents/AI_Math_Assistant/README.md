# AI Math Assistant

A LangChain-based mathematical assistant that performs arithmetic via tools
and can look up factual information on Wikipedia.

Course project: **Fundamentals of Building AI Agents** (IBM RAG and Agentic AI).

## Features

- Math tools: `add_numbers`, `add_numbers_with_options`, `sum_numbers_with_complex_output`, `sum_numbers_from_text`, `subtract_numbers`, `multiply_numbers`, `divide_numbers`
- Knowledge tool: `search_wikipedia`
- Agent wiring in `src/agent.py` using `langchain.agents.create_agent`
- LLM configured in `src/llm.py` (OpenRouter-compatible endpoint)
- Pytest suite in `tests/` (37 tests, Wikipedia mocked — no network needed)

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
cd AI_Math_Assistant

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# edit .env with your own keys
```

Required variables (see `.env.example`):

- `OPENROUTER_API_KEY` — your OpenRouter API key (**required**)
- `BASE_URL` — OpenRouter-compatible base URL, e.g. `https://openrouter.ai/api/v1`

## Run tests

```bash
python -m pytest tests/ -v
```

No API key or network access needed — the Wikipedia tool is mocked in tests.

## Notes

- `.env` is git-ignored. Never commit real keys.
- `venv/`, `__pycache__/`, and `.pytest_cache/` are git-ignored.
