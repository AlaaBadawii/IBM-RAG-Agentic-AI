# Quizey Idempotency — Exactly One Graded Attempt Under Concurrency

## Type

Engineering Decision

## Context

Quizey V2. Students submit an exam via `/submit`; the system grades and stores
the attempt. A double-click, retry, or network replay should not create a second
result.

## Problem

A concurrent double-submit could grade an attempt twice or leave two conflicting
results. The grading must happen **exactly once**, even under retries and
parallel requests.

## What I Did

Implemented two layers working together: an `@idempotent` decorator backed by an
`Idempotency-Key` header with a unique `(user, key, endpoint)` constraint, plus
a status check inside the attempt service. Completed requests are replayed;
in-flight ones return 409. Also built a concurrency harness proving that
10 concurrent `/submit` calls produce **exactly one** graded attempt.

## Decision / Insight

Idempotency + status check are both needed. The unique constraint prevents a
second writer from succeeding; the status check prevents logically re-processing
an already-finalized attempt. Either alone is insufficient.

## Result

Double-submission is provably prevented under concurrent retries (verified by
the concurrency test). The idempotency keys carry a TTL and stale-lock handling.

## Engineering Lesson

Exactly-once behavior is an engineering property you must design and prove, not
hope for. Unique constraints at the data layer + explicit state checks at the
service layer = two complementary guarantees.

## Why This Matters

Reliability under concurrency is a core production-engineering concern. This
shows deliberate design (and proof) of correctness, directly supporting the
reliable-systems direction.

## Evidence

- `/home/alaabadawii/Quizey_V2/app/utils/idempotency.py`
- `/home/alaabadawii/Quizey_V2/app/models/idempotency_key.py`
- `/home/alaabadawii/Quizey_V2/tests/test_attempts/test_concurrency.py`
- `/home/alaabadawii/Quizey_V2/app/services/attempt_service.py`
- KB: `in_progress_projects/quizey_v2.md`

## Content Potential

- Reliability/engineering decision post
- Concurrency + idempotency technical story
- "How I proved double-submission can't happen" post

Story strength:
STRONG

Reason:
A first-hand engineering problem (double-submit under concurrency), a clear
two-part decision, and proof via a concurrency harness. Strong evidence and a
transferable lesson.