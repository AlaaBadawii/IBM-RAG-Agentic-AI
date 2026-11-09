# Course 8 — Agentic AI with LangGraph, CrewAI, AutoGen and BeeAI

**Course status: Completed as of November 9, 2026 · Estimated duration: 14 hours**

[← Certificate overview](../README.md)

## Overview and Learning Objectives

The course compares graph-based orchestration, task/role-based crews, conversational
multi-agent systems, and requirement-driven agents. Retained work consists of
guided-pattern implementations and extensions with different maturity levels.
The official title uses AutoGen; the conversational lab uses the AG2/`autogen` API.

- Choose an orchestration pattern based on state, dependencies, and termination needs.
- Implement prompt chaining, routing, parallel execution, and dynamic worker fan-out.
- Pass evaluator feedback into an optimizer loop and interpret stop conditions correctly.
- Define CrewAI agents, tasks, tools, context, and structured output boundaries.
- Explore AG2 conversations and BeeAI tools, requirements, middleware, and handoffs.

## Project and Lab Index

| Directory | Actual implementation and state | Documentation |
|---|---|---|
| LangGraph Workflow Patterns | Three implemented guided patterns: sequential resume/cover-letter generation, intent routing, parallel translation | [README](LangGraph-Workflow-Patterns/README.md) |
| LangGraph Orchestration & Evaluation | Two implemented notebook-derived workflows with offline tests and termination caveats | [README](LangGraph-Orchestration-Evaluation/README.md) |
| NourishBot | Guided CrewAI food-image recipe/analysis app; reasoning-model setup is separate from watsonx tool credentials | [README](NourishBot/README.md) |
| Crew Research to Content | Experimental sequential research → blog → social-draft crew; no publishing integration or test suite | [README](Crew_Research_2_Content/README.md) |
| MealMind | Experimental structured meal/grocery crew; default runner blocked by a task/input typo | [README](MealMind-CrewAI-Meal-Planner/README.md) |
| AG2 Lab | Conversation, tool, structured-output, local code-execution, and group-chat scripts using `autogen` | [README](AG2-Lab/README.md) |
| BeeAI Framework Lab | RequirementAgent/tool/handoff examples; experimental APIs and a broken standalone model-factory demo | [README](BeeAI-Framework-Lab/README.md) |

### Nested Orchestration Documentation

- [Parallel Meal Planning](LangGraph-Orchestration-Evaluation/01-parallel-meal-planning/README.md): structured dish decomposition, `Send` worker fan-out, `operator.add` results, Python synthesis.
- [Investment Advisor Reflection](LangGraph-Orchestration-Evaluation/02-investment-advisor-reflection/README.md): target-grade selection, generation, structured evaluation, feedback-based refinement, and a limit stop that is not necessarily successful optimization.

## Technologies and Important Details

- **LangGraph/LangChain:** `StateGraph`, conditional edges, `Send`, reducers, structured output, `ChatWatsonx`.
- **CrewAI:** sequential `Crew` processes, agents/tasks, `context`, `output_json`/`output_pydantic`, `CrewBase`, YAML configuration, and `SerperDevTool`.
- **AG2:** `ConversableAgent`, `AssistantAgent`, `UserProxyAgent`, tool registration, `GroupChat`, `GroupChatManager`, and local command-line code execution.
- **BeeAI Framework 0.1.35:** `RequirementAgent`, tools, memory, trajectory middleware, conditional/permission requirements, and handoff-based travel planning.
- **Interfaces/providers:** Gradio, watsonx, Gemini-backed BeeAI examples, and an independent OpenRouter smoke script.

The AG2 manifest pins `autogen==0.14.1` and `pyautogen==0.10.0` and also lists
Microsoft `autogen-agentchat==0.7.5`/`autogen-core==0.7.5`. The examples import
`autogen`, not the latter packages' APIs. The manifest's package mixture is not
evidence that these framework interfaces are interchangeable.

## Configuration and Entry Points

For the two LangGraph labs, Research to Content, MealMind, and AG2, the common
consumed names are `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, and
`WATSONX_MODEL_ID`. Set values appropriate to each integration; a shared name
does not guarantee identical endpoint/credential handling across frameworks.

Run from the respective project root after its documented setup:

| Project | Additional/effective configuration | Representative source entry point |
|---|---|---|
| Workflow Patterns | Four common variables; some nodes construct clients at import | `python 01-sequential-agent-coordination/agent.py` |
| Orchestration & Evaluation | Four common variables; pipe modules construct clients at import | `python 01-parallel-meal-planning/agent.py` |
| Research to Content | `SERPER_API_KEY` also required; absent from its template | `python run.py` |
| MealMind | `SERPER_API_KEY` also required; absent from its template | `crew.py` is the retained runner, currently blocked by `{seervings}` vs `servings` |
| NourishBot | `WATSONX_API_KEY`, optional `WATSONX_URL`/`WATSONX_PROJECT_ID` for tools; CrewAI reasoning-model setup is separate | `python app.py` (port 5000) |
| AG2 | Four common variables; `WATSONX_PROJECT_NAME` is not read | `python mutli_agent.py` (source filename spelling) |
| BeeAI | Adapter-consumed `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, optional `WATSONX_URL`; `GEMINI_API_KEY` for Gemini examples; `OPENROUTER_API_KEY` only for `text.py` | `python minimal_agent.py` (Gemini) |

BeeAI selects hardcoded model IDs; the template's model-name variables do not
override those explicit selections. The provider credential names were checked
against the pinned framework adapters, as linked in its project README.
NourishBot likewise fixes the vision/text **tool** model IDs in source and does
not use `WATSONX_MODEL_ID` as a tool-model setting.

Most projects have retained manifests; Research to Content and MealMind do not.
Use project-local environments and the linked README's dependency details rather
than an absolute path to another project's virtual environment. No packages were
installed and no live application runs were performed for this documentation update.

## Tests and Engineering Lessons

- Orchestration & Evaluation has five test modules containing 44 test functions/methods. Models/pipes are replaced with deterministic fakes; no new pass count or measured coverage percentage is claimed.
- The other six project directories contain examples/labs, not tracked offline automated suites. BeeAI's wiki scripts are live exercises.
- Dynamic fan-out needs a reducer; sequential task ordering and explicit context dependencies are related but distinct.
- Evaluator feedback can improve the next prompt, but a matching model-generated grade is not independent correctness evidence.
- A shared `Accepted` branch for success and iteration-limit termination needs interpretation; the investment loop can stop after six evaluations with an unmatched grade.
- Missing Serper configuration, hardcoded model selection, and provider routing are reproducibility concerns that documentation must reflect.
- Permission requirements and human-input modes are implemented framework patterns here. MCP/FastMCP remains the next course, not completed work in this directory.
