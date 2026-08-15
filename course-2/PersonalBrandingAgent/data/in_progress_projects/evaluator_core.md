# Evaluator Core — two-stage AI grading engine (Judge + Critic)

> **Relationship note (from the cross-source audit):** this is a **later,
> separate** build in `/home/alaabadawii/LLMs/AI-Agents/`, distinct from the
> earlier **AI Agents From Scratch** (`../completed_projects/ai_agents_from_scratch.md`
> — the 3 framework-free agents). Step 10 ("Quizey adapter") ties this engine
> into Quizey Phase 3 AI grading. Keep the two projects separate.

## Status
IN PROGRESS. A guided learning build (a mentor-style session drives it step by
step). Steps 1-5 done; 6-10 pending. Source:
`/home/alaabadawii/LLMs/AI-Agents/evaluator_core/`.

## Vision (from PLAN/PROGRESS)
A two-stage AI grading engine. A student submits backend code (or, later, a
spoken mock-interview answer). A **Judge** LLM scores it against a fixed
hand-written rubric with reasoning; a **Critic** LLM checks whether that
reasoning is actually backed by evidence. Agree -> return grade; disagree / low
confidence -> flag **"needs human review"**. Eventually becomes a real feature
inside Quizey for grading open-ended answers/code.

## What is actually implemented (Steps 1-5, evidence-backed)
- `rubrics/code_review_rubric.py` — pure data: 4 criteria (correctness,
  security, error_handling, code_quality), each weight 0.25, description +
  bad/good example.
- `evidence/code_evidence.py` — pure function `gather_code_evidence(code,
  requirement)` returns `{code, requirement, lint_warnings: []}` (no LLM/I-O).
- `schemas/verdict_schema.py` — Judge's forced output shape (1-5 scale).
- `agents/judge.py` — `build_judge_prompt`, `judge_submission`,
  `_compute_weighted_score` (weighted average in plain Python; verified
  `overall_score == 3.25`).
- `agents/critic.py` + `schemas/critique_schema.py` — second plain function with
  no tool access; agreement recomputed in Python (fake LLM claimed `True`, code
  verified `False`).
- `core/action_context.py`, `core/environment.py` — dependency injection so
  tests substitute a fake LLM (zero API calls).
- `core/llm.py` — real `real_llm_call(prompt, schema, model)` via
  litellm + OpenRouter (written but "not yet run live").
- `tests/test_judge.py`, `tests/test_critic.py`, `tests/test_evidence.py`,
  `tests/test_pipeline.py` — fake-LLM stubs.

## What is still pending (Steps 6-10)
6. Selective memory sharing (AgentRegistry + Memory + slice selector).
7. Confidence + escalation (pipeline/evaluate.py — file exists but is empty).
8. Controllers (CodeReviewAgent, InterviewAgent) + interview rubric/evidence.
9. Eval harness (hand-scored dataset vs agreement rate).
10. Quizey adapter (optional, last).

## Technologies / concepts
Python 3, Pydantic, litellm, OpenRouter, dependency injection, fake-LLM
stubbing for tests, deterministic score math, two-stage LLM critique,
escalation design.

## Lessons documented (evidence: PLAN/PROGRESS)
- Real bug: `Environment` returned `"tool-executed"` (hyphen) but test checked
  `"tool_executed"` (underscore) — dict keys are exact, no typo tolerance.
- Real bug: an LLM (Claude) asserted `overall_score == 2.75` when the correct
  weighted average of `4,2,3,4` at 0.25 each is `3.25`; caught by hand-arithmetic.
  Lesson: never trust an LLM's arithmetic — recompute deterministic math in code.
- Design rule: keep the "plain code vs LLM" line sharp; test every AI step with
  a fake LLM before calling a real API.

## Provenance
`/home/alaabadawii/LLMs/AI-Agents/evaluator_core/PLAN.md` (project plan, step
statuses + decisions)
`/home/alaabadawii/LLMs/AI-Agents/evaluator_core/PROGRESS.md` (vision + bugs +
decisions log)
`/home/alaabadawii/LLMs/AI-Agents/evaluator_core/pipeline/evaluate.py` (empty =
pending Step 7)