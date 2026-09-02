# Test Every AI Step with a Fake LLM Before a Real API Call

## Type

AI Engineering

## Context

During the **Evaluator Core** build, AI steps (Judge scoring, Critic agreement)
needed to be tested — but calling a real LLM on every test would be slow and
unpredictable.

## Problem

How to verify the AI pipeline logic without repeated, cost-burning, non-
deterministic real API calls.

## What I Did

Structured the code so LLM access goes through a single `core/llm.py` layer with
a `(prompt, schema) -> dict` interface. In tests, a **fake LLM** is swapped in
behind that interface, and the environment/action context uses dependency
injection so tests run with zero API calls.

## Decision / Insight

Separate "the step logic" from "the LLM being called." If every AI step can be
verified with a fake before a real call, you validate correctness deterministically
and cheaply, and keep the real API path as a thin layer.

## Result

Tests (`test_judge.py`, `test_critic.py`, `test_evidence.py`, `test_pipeline.py`)
all run against fake-LLM stubs with no API calls; the real LLM path exists but is
only exercised live when intended.

## Engineering Lesson

Design AI systems so logic and model are decoupled. A fake LLM behind a stable
interface makes the non-AI logic fully testable, and makes the real model a
swappable detail.

## Why This Matters

Building dependable AI systems requires testing what you can deterministically.
This is a practical technique for the AI engineering / testing direction.

## Evidence

- `/home/alaabadawii/LLMs/AI-Agents/evaluator_core/core/llm.py`
- `/home/alaabadawii/LLMs/AI-Agents/evaluator_core/core/action_context.py`,
  `core/environment.py`
- `/home/alaabadawii/LLMs/AI-Agents/evaluator_core/tests/`
- KB: `in_progress_projects/evaluator_core.md`, `evidence/ai/evaluator_core.md`

## Content Potential

- AI engineering technique post (fake LLM / dependency injection)
- Testing approach story
- Engineering decision insight

Story strength:
MEDIUM

Reason:
An excellent, transferable technique with concrete evidence, but it reads more as
a design approach than a first-hand incident with a specific problem/result
arc. Strong technique, moderate story shape.