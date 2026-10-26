# LangGraph Orchestration & Evaluation

Hands-on lab companion for the IBM Skills Network notebook
**"Agentic Design Patterns in LangGraph-v1"** (`Agentic Design Patterns in LangGraph-v1.ipynb`,
kept at this directory root as the shared reference for both projects).

The notebook's two sections are implemented as two independent, runnable projects:

| Project | Notebook section | Pattern |
| --- | --- | --- |
| [01-parallel-meal-planning](01-parallel-meal-planning/) | *Orchestrator-Worker Pattern* (cells 17–61) | Orchestrator decomposes a meal request, parallel chef workers generate recipes, a synthesizer merges them |
| [02-investment-advisor-reflection](02-investment-advisor-reflection/) | *Reflection Pattern* (cells 62–105) | Iterative generate–evaluate–route loop that refines an investment plan |

Both projects deliberately use **IBM watsonx.ai** (`ChatWatsonx` via `langchain-ibm`) as
the model provider instead of the notebook's OpenAI/gpt-4o-mini configuration. The notebook
remains the structural reference; the source is the authoritative implementation.

## Shared configuration

- `llm.py` — the single watsonx.ai client factory (`get_llm()`, lru-cached, no network request at import).
- `print_workflow_info.py` — helper that prints graph nodes/edges and renders a Mermaid PNG.
- `.env.example` — template for the required credentials.

Required environment-variable names (see `.env.example`; values are never committed):

- `WATSONX_API_KEY`
- `WATSONX_PROJECT_ID`
- `WATSONX_URL`
- `WATSONX_MODEL_ID`

## Python environment

This lab shares an existing virtual environment with other educational projects —
**do not create a new one**:

```bash
/home/alaabadawii/LLMs/IBM/Agentic_AI_with_LangChain_and_LangGraph/DocChat_Multi_Agent_RAG/venv
```

`requirements.txt` documents the tested, *already installed* dependency versions
(see `ENVIRONMENT_AUDIT.md`). It is a record for reproducibility, **not** an
instruction to install anything during lab work — the environment must not be
changed to match it, and it has not been tested in a clean environment.

## Running Section 1

From this directory (`LangGraph-Orchestration-Evaluation/`), with `.env` configured:

```bash
/home/alaabadawii/LLMs/IBM/Agentic_AI_with_LangChain_and_LangGraph/DocChat_Multi_Agent_RAG/venv/bin/python 01-parallel-meal-planning/agent.py
```

Optionally regenerate the graph image (writes `01-parallel-meal-planning/graph.png`):

```bash
/home/alaabadawii/LLMs/IBM/Agentic_AI_with_LangChain_and_LangGraph/DocChat_Multi_Agent_RAG/venv/bin/python 01-parallel-meal-planning/graph.py
```

A live watsonx.ai call is required for `agent.py`; without valid credentials it fails by design.

Optionally regenerate the Section 2 graph image (writes `02-investment-advisor-reflection/graph.png`):

```bash
/home/alaabadawii/LLMs/IBM/Agentic_AI_with_LangChain_and_LangGraph/DocChat_Multi_Agent_RAG/venv/bin/python 02-investment-advisor-reflection/graph.py
```

## Running Section 2

The reflection workflow (target grade + two-phase generator + Buffett evaluator +
conditional routing with iteration limit) is implemented end to end in
[02-investment-advisor-reflection](02-investment-advisor-reflection/):

```bash
/home/alaabadawii/LLMs/IBM/Agentic_AI_with_LangChain_and_LangGraph/DocChat_Multi_Agent_RAG/venv/bin/python 02-investment-advisor-reflection/agent.py
```

This makes live watsonx.ai calls; without valid credentials it fails by design.
See that project's README for current status and known caveats.

## Tests

An offline test suite lives in `tests/`. It needs **no** watsonx.ai credentials and
never calls the model (model calls are replaced by fakes; an accidental call fails the run):

```bash
/home/alaabadawii/LLMs/IBM/Agentic_AI_with_LangChain_and_LangGraph/DocChat_Multi_Agent_RAG/venv/bin/python -m pytest
```

## Audit history

- [`ENVIRONMENT_AUDIT.md`](ENVIRONMENT_AUDIT.md) — shared-environment inventory and dependency findings.
- [`REFACTOR_PLAN.md`](REFACTOR_PLAN.md) — notebook-to-source mapping, file-ownership decisions, and the implementation record of the two-project separation (Section 2 was completed later, after that record).
