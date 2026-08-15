# Never Trust an LLM's Arithmetic — Recompute It in Code

## Type

AI Engineering

## Context

Building **Evaluator Core** (`/home/alaabadawii/LLMs/AI-Agents/evaluator_core/`),
a two-stage AI grading engine where a Judge LLM scores a submission and a Critic
LLM checks the reasoning.

## Problem

An LLM asserted `overall_score == 2.75` for scores `4, 2, 3, 4` each weighted
`0.25`. The correct weighted average is `3.25`. The model's arithmetic was wrong.

## What I Did

Caught the error by doing the weighted average by hand instead of trusting the
model. Changed the project rule: neither the Judge's weighted average nor the
Critic's agreement is taken verbatim from the LLM — both are recomputed in plain
Python.

## Decision / Insight

Deterministic math belongs in code, not in the LLM. An LLM can reason, but its
arithmetic is not reliable. Any computation the system depends on must be
recomputed where it can be tested.

## Result

Scoring and agreement are now computed deterministically in Python
(`_compute_weighted_score`; Critic agreement recomputed), so the numbers are
correct and auditable.

## Engineering Lesson

Never collect numeric results from an LLM and trust them. Recompute any
deterministic calculation in verifiable code — this is cheap insurance against
silently wrong output.

## Why This Matters

Building dependable AI systems means knowing where the AI ends and where
verifiable code begins. This is exactly the kind of judgment the AI engineering
direction calls for.

## Evidence

- `/home/alaabadawii/LLMs/AI-Agents/evaluator_core/PROGRESS.md` (real bug hit
  and fixed)
- `/home/alaabadawii/LLMs/AI-Agents/evaluator_core/agents/judge.py`
- `/home/alaabadawii/LLMs/AI-Agents/evaluator_core/agents/critic.py`
- KB: `in_progress_projects/evaluator_core.md`, `evidence/ai/evaluator_core.md`

## Content Potential

- AI engineering insight (deterministic math + LLM)
- Debugging story
- Short lesson on validating LLM output with code

Story strength:
STRONG

Reason:
A concrete, reproducible bug with hand-verifiable numbers, a clear engineering
decision (recompute in code), and a generalizable lesson about dependable AI
systems. Directly supports the "verify LLM output with code" identity.