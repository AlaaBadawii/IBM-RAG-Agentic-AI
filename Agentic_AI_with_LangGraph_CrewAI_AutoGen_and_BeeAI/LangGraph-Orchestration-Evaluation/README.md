# LangGraph Orchestration & Evaluation

**Status: Implemented notebook-derived workflows with offline tests; live-model and termination caveats remain.** [Course 8](../README.md) · [Certificate](../../README.md)

Hands-on lab companion for the IBM Skills Network notebook
**"Agentic Design Patterns in LangGraph-v1"** (`Agentic Design Patterns in LangGraph-v1.ipynb`,
kept at this directory root as the shared reference for both projects).

The notebook's two sections are implemented as two independent, runnable projects:

| Project | Notebook section | Pattern |
| --- | --- | --- |
| [01-parallel-meal-planning](01-parallel-meal-planning/README.md) | *Orchestrator-Worker Pattern* | Orchestrator decomposes a meal request, parallel chef workers generate recipes, a synthesizer merges them |
| [02-investment-advisor-reflection](02-investment-advisor-reflection/README.md) | *Reflection Pattern* | Iterative generate–evaluate–route loop that refines an investment plan |

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

Use a project-local environment rather than a machine-specific interpreter from
another project. From the repository root:

```bash
cd Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/LangGraph-Orchestration-Evaluation
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

The manifest retains pinned versions from the earlier development environment;
this documentation update has not installed or validated them in a clean
environment. Fill in the four consumed variables before live runs. Node pipe
modules call `get_llm()` during import, so importing a workflow needs configuration
even though model invocation occurs later.

## Running Section 1

From this directory (`LangGraph-Orchestration-Evaluation/`), with `.env` configured:

```bash
python 01-parallel-meal-planning/agent.py
```

Optionally regenerate the graph image (writes `01-parallel-meal-planning/graph.png`):

```bash
python 01-parallel-meal-planning/graph.py
```

A live watsonx.ai call is required for `agent.py`; without valid credentials it fails by design.

Optionally regenerate the Section 2 graph image (writes `02-investment-advisor-reflection/graph.png`):

```bash
python 02-investment-advisor-reflection/graph.py
```

## Running Section 2

The reflection workflow (target grade + two-phase generator + Buffett evaluator +
conditional routing with iteration limit) is implemented end to end in
[02-investment-advisor-reflection](02-investment-advisor-reflection/README.md):

```bash
python 02-investment-advisor-reflection/agent.py
```

This makes live watsonx.ai calls; without valid credentials it fails by design.
See that project's README for current status and known caveats.

## Tests

An offline test suite lives in `tests/`. It needs **no** watsonx.ai credentials and
never calls the model (model calls are replaced by fakes; an accidental call fails the run):

```bash
python -m pytest
```

The five test modules contain 44 test functions/methods, covering schemas,
workers, reducers, routing, shared utilities, and mocked workflow execution.
This is a source inventory, not a new pass count or measured coverage result.

## Engineering Lessons and Limitations

- Section 1 uses `Send` for dynamic fan-out and `operator.add` to merge worker lists. Its synthesizer joins the outputs in Python rather than making another model call.
- Section 2 passes evaluator feedback into a refinement generator, unlike a retry that simply repeats the original prompt.
- The target grade is free-form model text and can fail to match the evaluator's grade vocabulary.
- `route_investment` stops when `n > 5` (six evaluations from the default initial count), and uses the same `Accepted` route for a grade match and an iteration-limit stop. Reaching `END` does not prove that the target grade was met.
- Graph rendering uses a remote Mermaid service and requires network access; graph/node imports also require configuration.

## Retained Reference Material

- [Shared notebook](Agentic%20Design%20Patterns%20in%20LangGraph-v1.ipynb) — original course reference, with provider differences explained above.
- [Enhancement notes](ENHANCEMENT.md) — ideas and limitations for further work.

The earlier audit/refactor documents referenced by the old README are not
tracked here; they are not available navigation targets.
