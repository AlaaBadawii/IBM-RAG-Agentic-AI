# AI Powered Data Analysis with LCEL

A LangChain agent that inspects local CSV files and tells you whether each
dataset is a **classification** or **regression** task — with evidence
(sample rows, `describe` stats, and a trained baseline model score).

Course project: **Fundamentals of Building AI Agents** (IBM RAG and Agentic AI).

## Features

- Dataset tools (`tools.py`):
  - `list_csv_files` — find CSVs in the working directory
  - `preload_datasets` — load CSVs once into an in-memory cache
  - `get_dataset_summaries` — column names + dtypes per dataset
  - `call_dataframe_method` — run `head` / `tail` / `describe`, etc.
  - `evaluate_classification_dataset` — RandomForest accuracy (returns an
    `error` dict instead of crashing on continuous targets)
  - `evaluate_regression_dataset` — RandomForest R² + MSE
- Conversational agent (`llm.py`):
  - `create_openai_tools_agent` + `AgentExecutor` with `handle_tool_error`
  - Multi-turn chat loop with `chat_history` (type `exit`/`quit` to stop)
  - One bad tool call can't kill the session — errors are returned to the
    model and the loop continues
- Bundled datasets: `classification-dataset.csv` (Breast Cancer Wisconsin,
  ~95% accuracy) and `regression-dataset.csv` (California Housing,
  R² ~0.82)
- Offline pytest suite in `tests/` (9 tests, no API key or network needed)

## Project structure

```
AI_Powered_Data_Analysis_with_LCEL/
├── llm.py
├── tools.py
├── tests/
│   └── test_tools.py
├── classification-dataset.csv
├── regression-dataset.csv
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Setup

```bash
cd AI_Powered_Data_Analysis_with_LCEL

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# edit .env with your own key
```

Required variables (see `.env.example`):

- `OPENROUTER_API_KEY` — your OpenRouter API key (**required**)
- `OPENROUTER_BASE_URL` (or `BASE_URL`) — e.g. `https://openrouter.ai/api/v1`
- `OPENROUTER_MODEL` — default `deepseek/deepseek-v4-flash`

## Run the agent

```bash
python llm.py
```

```
📊 Ask questions about your dataset (type 'exit' to quit):
 You: tell me about the datasets
my Agent: <summaries, head/describe output, 95%+ accuracy / 0.82 R², ...>
 You: exit
see ya later
```

## Run tests

```bash
python -m pytest tests/ -v
```

No API key or network access needed — tool tests run locally with
pandas/scikit-learn. (`test_llm_*` only imports `llm.py`; the chat loop is
guarded by `if __name__ == "__main__"`.)

## Notes

- `.env` is git-ignored. Never commit real keys (`.env.example` holds
  placeholders only).
- Requires Python 3.10+ (uses `X | Y` type unions).
- `venv/`, `__pycache__/`, and `.pytest_cache/` are git-ignored.
