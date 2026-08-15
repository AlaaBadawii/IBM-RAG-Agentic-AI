# FastAPI: Keep Business Logic Out of Routes

## Type

Engineering Decision

## Context

Learned FastAPI through a small Shipment API practice lab (`/home/alaabadawii/FastAPI/`),
building a typed CRUD API. Separately, Quizey V2 already used a
`Route → Service → Model` discipline.

## Problem

In a small FastAPI it is tempting to put all logic in route handlers. That
pattern grows into routes that do too much, are hard to test, and are painful to
reuse or migrate later.

## What I Did

Applied a layered layout in the FastAPI lab — routes in `main.py`, typed
request/response/table models in `schemas.py`, and the engine/session in
`database/session.py` — mirroring the service-layer discipline used in Quizey V2.

## Decision / Insight

The pattern was: routes stay thin, models are typed and separated, and the DB
session is injected per-request (`Annotated[Session, Depends]`). Consistent
layering, not the specific framework, makes logic testable and portable.

## Result

A working CRUD API (6 routes) over SQLite with typed request/response models and
a documented architecture that mirrors the Quizey discipline. Honest scope:
starter-grade — no tests, no deployment, no async DB layer.

## Engineering Lesson

Layering is about deciding where behavior belongs, not the stack. Keeping routes
thin and separating schemas/session makes code portable and testable.

## Why This Matters

Recognizing and applying the same layering discipline across two unrelated
(FastAPI and Quizey) shows consistent backend-thinking. This is a learning story
about engineering judgment, not a claim of production FastAPI experience.

## Evidence

- `/home/alaabadawii/FastAPI/app/main.py`
- `/home/alaabadawii/FastAPI/app/schemas.py`
- `/home/alaabadawii/FastAPI/app/database/session.py`
- `/home/alaabadawii/FastAPI/async.py`
- KB: `in_progress_projects/fastapi_shipment_api.md`, `evidence/backend/fastapi.md`

## Content Potential

- Architecture comparison post (layering across frameworks)
- Learning story connecting FastAPI to the Quizey discipline
- Short lesson on route design

Story strength:
MEDIUM

Reason:
A genuine design choice with a cross-project insight, but the evidence is a
practice lab (no tests/deployment), so the "result" is modest. Useful as a
learning/architecture story, not an experience claim.