# Course 7 — Agentic AI with LangChain and LangGraph

**Course status: Completed as of November 9, 2026 · Estimated duration: 11 hours**

[← Certificate overview](../README.md)

## Overview and Learning Objectives

The course introduces stateful, iterative agent architectures: ReAct, Reflection,
Reflexion, orchestration, and agentic RAG. The retained implementations adapt
guided patterns and extend them with explicit configuration, offline tests, and
document-processing workflows. Completion of the course does not establish
production readiness or measured answer quality.

- Build state graphs, node updates, conditional edges, and message reducers.
- Execute tool calls and link observations to their originating requests.
- Distinguish self-critique, search-supported revision, and separate verification.
- Coordinate document conversion, retrieval, relevance, generation, and verification.
- Bound loops and test state transitions with deterministic model/search fakes.

## Project and Lab Index

| Project | Actual implementation and state | Documentation |
|---|---|---|
| LangGraph Stateful AI Workflows | Toy auth-routing and canned-context QA graphs; notebook counter exercise is still a stub | [README](LangGraph_Stateful_AI_Workflows/README.md) |
| Reflection Agent | Two-node LinkedIn draft/critique loop; four generations in the demo, no factual verifier | [README](Reflection_Agent_with_LangGraph/README.md) |
| Deep Research Reflexion Agent | Draft → critique/search queries → Tavily research → revision/citations; legacy `MessageGraph` with offline tests | [README](Deep_Research_Reflexion_Agent/README.md) |
| ReAct Agent | Two-node `StateGraph`, four registered tools, tool-result linking, bounded routing, offline tests | [README](ReAct_Agent_with_LangGraph/README.md) |
| DocChat Multi-Agent RAG | Experimental Gradio document app with Docling, hybrid retrieval, relevance/research/verification stages, bounded research retries | [README](DocChat_Multi_Agent_RAG/README.md) |

## Technologies and Important Implementation Details

- **LangChain/LangGraph:** prompts, tool schemas, `StateGraph`, legacy `MessageGraph`, `add_messages`, conditional routing, and LCEL model chains.
- **Providers:** watsonx through `ChatWatsonx`, `ModelInference`, and `WatsonxEmbeddings`; Tavily web search in ReAct and Reflexion.
- **Document RAG:** Docling conversion, BM25 + Chroma `EnsembleRetriever`, `pydantic-settings`, and Gradio.
- **Engineering:** installable `src/` packages for ReAct/Reflexion, pytest fakes, schema and control-flow checks, graph diagrams.

ReAct's registry contains `search_tool`, `remommend_clothing` (source spelling),
`calculator`, and `news_summarizer`. Its limit counts `ToolMessage`s rather than
model turns. Reflexion stops at a fixed research-message budget. Reflection
uses a message-count stop condition rather than choosing the highest-quality draft.

DocChat shares one retrieved document set across relevance, research, and
verification, with up to three research attempts. Its verifier does not receive
the original question, retries do not consume verifier feedback, and embedding
input is configured to truncate to three tokens. These limitations qualify its
retrieval/verification claims.

## Configuration and Execution

For model-backed workflows, the common consumed variables are `WATSONX_API_KEY`,
`WATSONX_PROJECT_ID`, `WATSONX_URL`, and `WATSONX_MODEL_ID`.

| Project | Additional configuration | Actual invocation from its project root |
|---|---|---|
| Stateful Workflows | QA also requires `WATSONX_PROJECT_NAME`; auth needs no IBM key | `python app.py`; `python QAState.py` |
| Reflection | Requires `WATSONX_PROJECT_NAME` at startup | `python graph.py` |
| Deep Research Reflexion | `TAVILY_API_KEY`; importing the search/graph module validates it | `python -m deep_research_agent.graph` after editable installation |
| ReAct | `TAVILY_API_KEY` for search; optional `REACT_MAX_ITERATIONS` (default 6) | `python scripts/run_agent.py` after editable installation |
| DocChat | Optional retrieval/cache/Docling tuning documented in its README | `python app.py` (localhost port 5000) |

`WATSONX_PROJECT_NAME` is not read by ReAct/Reflexion and does not affect DocChat
inference. It is required by the startup checks in Stateful/Reflection even
though it is not sent to the model client.

Use each project's manifest in a separate environment. ReAct and Reflexion's
package metadata requires Python 3.12 (`>=3.12,<3.13`). For those packages, setup
includes `python -m pip install -r requirements-dev.txt` and
`python -m pip install -e .` from the respective project root. The other projects
use their own `requirements.txt` and local entry points.

## Verified Test Inventory

Counts below are source definitions, excluding `conftest.py`; parameterization
can expand the number of collected cases. No application run, pass result, or
measured coverage percentage is claimed by this documentation update.

| Project | Test modules | Test functions/methods | Main behaviors covered |
|---|---:|---:|---|
| ReAct | 11 | 56 | Lazy config, tools, safe arithmetic, message linking, routing, full mocked cycles |
| Deep Research Reflexion | 8 | 45 | Schemas, chains, search execution, routing, answer extraction, mocked workflow |
| DocChat | 6 | 108 | Document validation/conversion, retrieval/agent configuration, verification/retry paths |

Stateful Workflows and Reflection have no tracked automated suites.

## Engineering Lessons

- Shared state and message-role contracts determine whether feedback reaches the next node.
- Tool registration exposes capabilities; execution and result correlation remain application responsibilities.
- A graph reaching `END` is not necessarily an answered or verified task.
- A verifier using the same model/context is not independent factual evidence; inspect its inputs and retry behavior.
- Lazy client factories help offline testing, but callers can still construct clients at import time.
- Course notebooks, standalone rebuilds, and independently extended apps are related artifacts with different maturity levels.
