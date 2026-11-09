# Crew Research to Content

**Status: Implemented experimental three-agent CrewAI workflow; live provider routing is unverified.**

[Course 8](../README.md) · [Certificate overview](../../README.md)

## Overview and Architecture

This course-pattern implementation turns a research topic into a report, a blog
draft, and social-media drafts. It generates content; it does not publish posts.

| Agent | Task | Tools |
|---|---|---|
| Senior Research Analyst | Research trends and technologies for `{topic}` | `SerperDevTool` web search |
| Tech Content Strategist | Turn research into a requested four-paragraph blog draft | No explicit tool list; delegation enabled |
| Social Media Content Creator | Request two or three social-media drafts | No explicit tool list; delegation enabled |

[`crew_workflow.py`](crew_workflow.py) assembles the three agents/tasks with
`Process.sequential`. Task ordering provides the workflow progression; these
task definitions do not declare explicit `context=[...]` dependencies.
[`run.py`](run.py) uses the fixed topic "Latest Generative AI breakthroughs" and
prints final output, each task output/agent, and token-usage fields.

## Files and Technologies

- [`agents.py`](agents.py): agent roles, tools, delegation flags, model wiring.
- [`tasks.py`](tasks.py): research, writing, and social-media task prompts.
- [`llm.py`](llm.py): cached `crewai.LLM` factory, required-variable checks, 2,000-token setting.
- [`search_tool.py`](search_tool.py): `SerperDevTool` construction and import-time key check.
- [`crew_workflow.py`](crew_workflow.py), [`run.py`](run.py): sequential crew and example runner.

Direct dependencies are `crewai`, `crewai-tools`, and `python-dotenv`. No
dependency manifest or automated test suite is tracked, so a clean, version-pinned
installation has not been established.

## Configuration

| Consumed variable | Purpose |
|---|---|
| `WATSONX_API_KEY` | Passed as the CrewAI LLM API key |
| `WATSONX_PROJECT_ID` | Passed as its project ID |
| `WATSONX_URL` | Passed as its base URL |
| `WATSONX_MODEL_ID` | Passed as its model identifier |
| `SERPER_API_KEY` | Required by `search_tool.py` and Serper search |

The existing `.env.example` lists only the four watsonx variables. Add your own
`SERPER_API_KEY` to the local ignored `.env` before importing/running the workflow.
The `crewai.LLM` model name and endpoint must be compatible with CrewAI's provider
routing; no endpoint/credential exchange is validated by this documentation update.

## Entry Point

From the repository root, in a compatible isolated runtime with the direct
dependencies installed:

```bash
cd Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/Crew_Research_2_Content
cp .env.example .env
# Configure the four watsonx variables and add SERPER_API_KEY in your local .env.
python run.py
```

The runner takes no CLI arguments. These commands match tracked paths and source
entry points; they are not reported as an executed workflow.

## Limitations and Lessons

- Agents are built at import time, so imports can require credentials before the runner begins.
- Requested paragraph/post counts and factual quality are prompt-level expectations, not deterministic validation.
- No independent evidence verifier, persisted content store, publishing integration, or evaluation benchmark is implemented.
- The runner assumes exactly three task outputs and available token-usage metadata.
- Separating agents, tasks, model configuration, and orchestration makes the workflow inspectable without claiming that delegation alone guarantees correctness.
