# The DB Is the Source of Truth for Roles, Not the JWT

## Type

Engineering Decision

## Context

Quizey V2. Auth uses JWT (access + refresh tokens), and there are two roles:
student and teacher. Authorization checks needed to know the caller's role.

## Problem

JWT claims can become stale: a user's role in the token could differ from their
actual role in the database, enabling stale-role authorization.

## What I Did

Decided that the **authoritative role is read from the database** at
authorization time, not from the JWT claims. RBAC decorators (`require_role`,
`require_student`, `require_teacher`) look up `User.role` in the DB and return
403 on mismatch. Ownership checks (teacher owns exam, student owns attempt) run
in services on top of that.

## Decision / Insight

Treat identity claims as a convenience, not a source of truth. For authorization,
the current persisted state is more trustworthy than an immutable token that can
carry stale data.

## Result

Authorization is now DB-backed and role changes take effect immediately. A known
open gap remains: re-auditing every route and re-verifying the 403 negative test
(Milestone 2.1.4).

## Engineering Lesson

Know where your source of truth lives. For authorization, current persisted
state beats a potentially-stale token claim.

## Why This Matters

Security is an engineering concern (per the vision: security as a first-class
engineering concern). A deliberate, defensible auth decision shows judgment.

## Evidence

- `/home/alaabadawii/Quizey_V2/app/utils/rbac.py`
- `/home/alaabadawii/Quizey_V2/app/services/auth_service.py`
- `/home/alaabadawii/Quizey_V2/docs/engineering/phase-2-production-platform/`
  (stage-2.1 assessment-platform docs, RBAC discussion)
- KB: `in_progress_projects/quizey_v2.md`

## Content Potential

- Security/auth engineering decision post
- Short lesson on source-of-truth vs tokens
- Engineering decision story

Story strength:
MEDIUM

Reason:
A real, defensible design decision with clear rationale and evidence, but the
open 2.1.4 gap means the story is about the decision itself rather than a fully
verified end-to-end result.