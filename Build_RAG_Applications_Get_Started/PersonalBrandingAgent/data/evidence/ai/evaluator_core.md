# Evaluator Core — Evidence (later build, in progress)

Two-stage AI grading engine (Judge + Critic). **Later, separate** build in
`/home/alaabadawii/LLMs/AI-Agents/evaluator_core/`. Source:
`../in_progress_projects/evaluator_core.md`.

## Evidence state

IN_PROGRESS (Steps 1–5 implemented with tests; Steps 6–10 pending).

## What was actually built (Steps 1–5, evidence-backed)

- `rubrics/code_review_rubric.py` — 4 criteria (correctness, security,
  error_handling, code_quality), weight 0.25 each, with bad/good examples.
- `evidence/code_evidence.py` — `gather_code_evidence()` returns
  `{code, requirement, lint_warnings: []}` (no LLM I/O).
- `schemas/verdict_schema.py` — forced Judge output shape (1–5 scale).
- `agents/judge.py` — prompt builder + `judge_submission` + `_compute_weighted_score`
  (weighted average in plain Python; verified `overall_score == 3.25`).
- `agents/critic.py` + `schemas/critique_schema.py` — second-stage check that
  the Judge's reasoning is evidence-backed; agreement recomputed in Python.
- `core/action_context.py`, `core/environment.py` — dependency injection so tests
  substitute a fake LLM (zero API calls).
- `core/llm.py` — real `real_llm_call()` via litellm + OpenRouter (written,
  "not yet run live").
- Tests: `test_judge.py`, `test_critic.py`, `test_evidence.py`, `test_pipeline.py`
  (fake-LLM stubs).

## Pending (Steps 6–10)

6. Selective memory sharing; 7. Confidence + escalation (`pipeline/evaluate.py`
   empty); 8. Controllers + interview rubric; 9. Eval harness; 10. Quizey adapter.

## Documented lessons (real bugs caught)

- Env returned `"tool-executed"` (hyphen) but test checked `"tool_executed"`
  (underscore) — dict keys are exact.
- An LLM asserted `overall_score == 2.75` when the correct weighted average of
  `4,2,3,4` at 0.25 is `3.25` — recompute deterministic math in code, never trust
  LLM arithmetic.

## Publicly safe claim

- "I'm building a two-stage AI grading engine (Judge + Critic) with deterministic
  scoring and fake-LLM-tested steps — designed to feed Quizey's Phase 3."

## Avoid

- "I built a production AI grading system." (In progress; Steps 6–10 pending.)

## Relationship

- Distinct from AI Agents From Scratch (`../ai/ai_agents_from_scratch.md`) — later,
  separate build.
- **Intended future**: Evaluator Core → Quizey Phase 3 AI grading.

## Evidence source

`../in_progress_projects/evaluator_core.md`, `/home/alaabadawii/LLMs/AI-Agents/evaluator_core/`
(`PLAN.md`, `PROGRESS.md`, `agents/`, `schemas/`, `core/`, `rubrics/`, `tests/`).