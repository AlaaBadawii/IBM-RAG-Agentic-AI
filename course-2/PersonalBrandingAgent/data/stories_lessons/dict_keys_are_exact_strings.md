# Dictionary Keys Are Exact Strings — a One-Char Typo Breaks Everything

## Type

Debugging

## Context

During the **Evaluator Core** build, the AI agent's `Environment` returned a
status string that a test needed to match.

## Problem

`Environment` returned `"tool-executed"` (with a hyphen) but the test checked
for `"tool_executed"` (with an underscore). The test "failed" for no apparent
reason — the logic was right, the strings just didn't match.

## What I Did

Tracked down the mismatch between the produced value and the expected value. The
fix was aligning the exact string constant, not changing any logic.

## Decision / Insight

Dictionary lookups and string comparisons are exact — there is no typo
tolerance. A one-character difference breaks a lookup silently.

## Result

The test passed once the strings matched. No logic changed; the "bug" was purely
an exactness issue.

## Engineering Lesson

When an exact-match comparison fails, expect the mismatch to be in the exact
bytes, not in the surrounding logic. Keep status/enum strings defined once and
reused, rather than hand-typed in multiple places.

## Why This Matters

Attention to detail and systematic debugging are core engineering habits. This
is a small but real example of tracking down a silent failure.

## Evidence

- `/home/alaabadawii/LLMs/AI-Agents/evaluator_core/PROGRESS.md` (documented bug)
- KB: `in_progress_projects/evaluator_core.md`

## Content Potential

- Short debugging lesson
- Small technical insight (exact strings) — usable as a brief post

Story strength:
MEDIUM

Reason:
A real, documented bug with a clear root cause, but the lesson is limited in
scope and shows less independent judgment/result than a deeper engineering
story. Still useful and honest.