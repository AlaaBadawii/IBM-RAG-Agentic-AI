# MealMind — CrewAI Meal and Grocery Planner

**Status: Experimental guided-lab implementation; the default runner is blocked by an input-name mismatch.**

[Course 8](../README.md) · [Certificate overview](../../README.md)

## What Is Implemented

The source composes five agents and five sequential tasks for recipe research,
shopping organization, budget suggestions, leftover reuse, and a final report.
It retains the guided notebook
[`Create a Structured Meal Grocery Planner with CrewAI.ipynb`](Create%20a%20Structured%20Meal%20Grocery%20Planner%20with%20CrewAI.ipynb).

| Stage | Agent/task implementation | Output contract |
|---|---|---|
| Meal planning | Recipe researcher with Serper search | Pydantic `MealPlan` |
| Shopping | Grocery organizer with meal-task context | Pydantic `GroceryShoppingPlan` |
| Budget | Budget adviser with meal and shopping context | Narrative guide |
| Leftovers | YAML-configured waste-reduction specialist through `CrewBase` | Suggested leftover meals |
| Summary | Report compiler with prior task context | Combined meal-planning guide |

[`crew.py`](crew.py) assembles the crew and contains a fixed Chicken Stir Fry
example. [`tasks.py`](tasks.py) declares outputs named `meals.json`,
`Shopping_list.json`, and `shopping_guide.md`; these are potential runtime outputs,
not tracked generated reports or verified results.

## Files and Technologies

- [`agents.py`](agents.py), [`tasks.py`](tasks.py): four Python-configured agents and tasks.
- [`leftover.py`](leftover.py), [`yaml_leftover.py`](yaml_leftover.py): leftover `CrewBase` wiring using [`config/agents.yaml`](config/agents.yaml) and [`config/tasks.yaml`](config/tasks.yaml).
- [`schemas.py`](schemas.py): meal and shopping models; estimated prices/totals are strings, not enforced arithmetic budgets.
- [`llm.py`](llm.py), [`search_tool.py`](search_tool.py): CrewAI LLM and Serper configuration.

Direct dependencies include `crewai`, `crewai-tools`, `pydantic`, and
`python-dotenv`; YAML configuration is loaded by CrewAI. No dependency manifest
or automated test suite is tracked.

## Configuration Actually Consumed

`llm.py` requires `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, and
`WATSONX_MODEL_ID`, passing them into `crewai.LLM`. `search_tool.py` additionally
requires `SERPER_API_KEY` at import time. The existing `.env.example` omits the
Serper key, so a local copy needs that additional value. Model/endpoint routing
must be compatible with the chosen CrewAI provider integration.

## Entry Point and Current Blocker

The retained entry point is `python crew.py` from
`Agentic_AI_with_LangGraph_CrewAI_AutoGen_and_BeeAI/MealMind-CrewAI-Meal-Planner`
relative to the repository root. It is **not a working default workflow** as written:
the first task interpolates `{seervings}`, but `crew.py` supplies only `servings`.
Correcting that name requires a separate code change.

The runner's source inputs are `meal_name`, `servings`, `budget`,
`dietary_restrictions`, and `cooking_skill`. There is no argument-based CLI,
Gradio app, or completed generated report to document.

## Remaining Limitations and Engineering Lessons

- Fix the task/input spelling mismatch before claiming an end-to-end run.
- The leftover task's YAML asks about the shopping list but does not explicitly declare shopping-task context; sequential ordering is not the same as a documented data dependency.
- Structured meal/shopping outputs do not independently verify prices, totals, recipes, or dietary suitability.
- Agents and tasks are constructed during import, requiring configuration before execution.
- Runtime output filenames are fixed; repeated runs can overwrite earlier outputs.
- Dependency packaging, live provider integration, and assertion-based tests still need verification. This is a meaningful lab implementation with unfinished execution details, not a production meal planner.
