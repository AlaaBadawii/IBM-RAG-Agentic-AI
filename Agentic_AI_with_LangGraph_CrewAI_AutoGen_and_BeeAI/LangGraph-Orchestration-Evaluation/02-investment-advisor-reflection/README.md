# 02 Investment Advisor Reflection — Evaluator-Optimizer Pattern

Implementation of the *Reflection Pattern* section (cells 62–105) of
`../Agentic Design Patterns in LangGraph-v1.ipynb`: an investment advisory system
that generates a portfolio plan, evaluates it against a target risk grade, and
iteratively refines it through feedback (see
[Current Status / Remaining Work](#current-status--remaining-work) for caveats).

**Status: Implemented guided evaluator-optimizer workflow with termination caveats.** [Lab overview](../README.md) · [Course 8](../../README.md) · [Certificate](../../../README.md)

Model provider: **IBM watsonx.ai** (`ChatWatsonx` from the shared root
`../llm.py`, configured via the `WATSONX_*` environment variables). The notebook
itself uses OpenAI; this deviation is intentional and preserved everywhere in this lab.

## State and schemas

- **`state.py` — `ReflectionState`** (notebook cell 64), current fields:
  - `investment_plan` — the generated plan being evaluated and revised
  - `investor_profile` — user-supplied profile used as the reference
  - `target_grade` — ideal risk grade pushed toward by the setup node
  - `feedback` — evaluator feedback for the plan
  - `grade` — evaluated risk grade of the plan
  - `n` — evaluation-iteration counter
- **`schemas.py` — `grades`**: `Literal` of `"ultra-conservative", "conservative",
  "moderate", "aggressive", "high risk"`, plus the placeholder value `"MISSING"`
  used by routing defaults (the notebook defines only the five; see caveats).
- **`schemas.py` — `Feedback`**: the evaluator's structured output schema
  (`grade` + `feedback`), used by `buffett_evaluator_pipe` (cell 77/85).

## Existing components

- **`determine_target_grade.py`** — node for notebook cell 69. Invokes
  `grade_pipe` with `investor_profile` and returns
  `{"target_grade": <grade text lowercased>}`, which LangGraph merges into the
  `target_grade` state channel. Runnable standalone
  (`python 02-investment-advisor-reflection/determine_target_grade.py`) with a
  sample investor profile — performs a live watsonx.ai call.
- **`investment_plan_generator.py`** — node for notebook cell 81. Two-phase
  generator:
  - *Phase 1 (initial, no feedback)*: `cathie_wood_pipe` — bold, innovation-driven
    strategist persona.
  - *Phase 2 (refinement, when `state["feedback"]` is set)*: `ray_dalio_pipe` —
    conservative, feedback-adaptive persona.
  Runnable standalone
  (`python 02-investment-advisor-reflection/investment_plan_generator.py`) —
  performs a live watsonx.ai call.
- **`pipe.py`** — `grade_pipe`, `cathie_wood_pipe`, `ray_dalio_pipe`,
  `buffett_evaluator_pipe` (structured output), built on the shared client from
  `../llm.py`.
- **`prompt.py`** — `grade_prompt`, `cathie_wood_prompt`, `ray_dalio_prompt`,
  `evaluator_prompt` (texts taken verbatim from the notebook).

Live standalone examples require valid watsonx.ai credentials. Their imported
`pipe.py` calls the otherwise-lazy `get_llm()` factory during import, which
validates configuration and raises `OSError` for missing values.

## Current Status / Remaining Work

The previously missing pieces — Buffett evaluator pipe + `evaluate_plan`,
`route_investment`, the reflection graph, iteration/termination, and end-to-end
execution — have **since been completed** and the workflow now runs end to end
in source:

- `pipe.py` — `buffett_evaluator_pipe = evaluator_prompt | llm.with_structured_output(Feedback)`
- `evaluate_plan.py` — evaluator node returning `grade`, `feedback`, and incrementing `n`
- `route_investment.py` — grade-match routing or termination when `n > 5`; both use the `Accepted` branch
- `graph.py` — `optimizer_workflow`:
  `START → determine_target_grade → investment_plan_generator → evaluate_plan`,
  conditional edge `Accepted → END` / `Rejected + Feedback → investment_plan_generator`
- `agent.py` — end-to-end runner with `pretty_print_final_state`

Remaining work / caveats:
- `determine_target_grade` asks the LLM for "ONLY the grade" without structured
  output, so a verbose or differently-worded response will not equal the target
  grade and the loop will run to the iteration limit before stopping gracefully.
- The workflow has not been re-verified with a live model call during this fix;
  a live `agent.py` run requires valid watsonx.ai credentials.
- Starting from a zero/default counter, the strict `n > 5` check allows six evaluations. A limit stop is labeled `Accepted` even if the evaluated grade differs from the target; termination is not proof of successful optimization.
- `schemas.py` keeps a non-notebook placeholder value (`"MISSING"`) inside the
  `grades` Literal to accommodate the `"MISSING"` defaults used by routing.

## Files

| File | Role |
| --- | --- |
| `state.py` | `ReflectionState` |
| `schemas.py` | `grades`, `Feedback` |
| `prompt.py` | Section-2 prompt templates (incl. `evaluator_prompt`) |
| `pipe.py` | the four LLM pipes |
| `determine_target_grade.py` | target-grade node (+ standalone test) |
| `investment_plan_generator.py` | generator node (+ standalone test) |
| `evaluate_plan.py` | evaluator node |
| `route_investment.py` | routing / termination logic |
| `graph.py` | reflection graph build/compile (+ workflow info printer) |
| `agent.py` | end-to-end runner |

## Execution

From this lab's root directory (`LangGraph-Orchestration-Evaluation/`), with
`.env` configured and the project-local environment activated (see [lab setup](../README.md#python-environment)):

```bash
python 02-investment-advisor-reflection/agent.py
```

`agent.py` is the end-to-end runner (live watsonx.ai calls; fails without valid
credentials). Standalone component tests that also make live calls:

```bash
python 02-investment-advisor-reflection/determine_target_grade.py
python 02-investment-advisor-reflection/investment_plan_generator.py
```

Offline validation uses the root test suite instead — run from the lab root:

```bash
python -m pytest
```

Regenerate the graph image (writes `graph.png` in this directory):

```bash
python 02-investment-advisor-reflection/graph.py
```

The shared offline suite contains five test modules with 44 functions/methods
across both sections. No new live-model run, test-pass count, or measured coverage
is claimed here. This is a workflow-pattern example, not a validated investment
recommendation system.
