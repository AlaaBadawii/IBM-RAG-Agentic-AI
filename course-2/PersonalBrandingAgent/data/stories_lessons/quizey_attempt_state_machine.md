# Quizey Attempt State Machine — Explicit Transitions, No Invalid States

## Type

Architecture

## Context

Quizey V2. An attempt (a student "taking an exam") moves through several states:
in-progress, paused, submitted, graded, archived.

## Problem

Without discipline, an attempt could jump between arbitrary states — e.g., be
"submitted" and "graded" inconsistently, or resurrect a paused attempt after
expiry — corrupting the flow and grading.

## What I Did

Enforced a state machine via a `StateMachineMixin` with a `@validates` guard on
the `status` column. Defined an explicit transition map
(`ATTEMPT_TRANSITIONS`): in_progress → {paused, submitted} → submitted → graded
→ archived. Any illegal transition raises `InvalidTransitionError`.

## Decision / Insight

State transitions should be defined explicitly, not inferred. Guarding the
column at the ORM layer means the allowed transitions are enforced everywhere,
not just in one route.

## Result

The attempt lifecycle is now modeled with a single source of truth for allowed
transitions (24+ subtest coverage in `test_state_machine.py`). Later lifecycle
features (pause, lazy expiry, submission) sit on a stable state model.

## Engineering Lesson

When a domain has a lifecycle, model it as a state machine early. It prevents a
whole class of invalid-state bugs before they happen.

## Why This Matters

Modeling core domain logic correctly is a foundational backend skill. This state
machine is what allows the later attempt-lifecycle work (pause, expiry,
submission) to be safe and inspectable.

## Evidence

- `/home/alaabadawii/Quizey_V2/app/models/state_machine.py`
- `/home/alaabadawii/Quizey_V2/app/models/attempt.py`
- `/home/alaabadawii/Quizey_V2/tests/test_models/test_state_machine.py`
- KB: `in_progress_projects/quizey_v2.md`

## Content Potential

- Architecture post ("model your domain as a state machine")
- Engineering decision story about domain integrity

Story strength:
STRONG

Reason:
A concrete design decision (state machine at the ORM layer) with clear rationale,
implementation, test coverage, and a transferable engineering lesson.