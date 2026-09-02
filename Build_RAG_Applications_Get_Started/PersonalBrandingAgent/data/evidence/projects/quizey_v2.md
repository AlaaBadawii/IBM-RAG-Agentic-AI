# Quizey V2 — Evidence

Flagship project. Primary source:
`../in_progress_projects/quizey_v2.md` (authoritative). Repo
`/home/alaabadawii/Quizey_V2/`.

## Evidence state

IN_PROGRESS (Phase 1 completed; Phase 2 prerequisites complete; Milestone 2.1.1
code-complete but not committed; Phase 3 AI planned).

## What was actually built (evidence-backed)

- **Modular monolith** backend: feature blueprints `auth/`, `exams/`,
  `attempts/` under `/api/v1`, with `models/`, `services/`, `extensions/`,
  `utils/`. Layer discipline `Route → Service → Model → Database`; no business
  logic in routes.
- **Auth:** Flask-JWT-Extended access+refresh tokens; DB-backed refresh-token
  blacklist; register validates username/email/password; Werkzeug password hashing.
- **RBAC:** `require_role` decorators + ownership checks; **DB is the role source
  of truth** (not JWT claims). Known open gap: re-audit of every route (2.1.4).
- **Exam versioning (copy-on-write):** published exams immutable; edit creates a
  new version via `create_exam_version()`; self-referential `root_exam_id`
  version families; only one version per family published at a time
  (demote-on-publish). Title suffix `(v{n})`, 249-char cap.
- **Attempt lifecycle state machine:** `StateMachineMixin` guarding `status`;
  transitions in_progress → {paused, submitted} → submitted → graded → … → archived;
  invalid transitions raise `InvalidTransitionError`.
- **Milestone 2.1.1 (attempt lifecycle)**: pause/resume (exam-controlled by
  `allow_pausing`), four-case timing model (untimed / duration / deadline / both),
  **lazy** expiry (no background scheduler), telemetry (elapsed/active/paused,
  real `submitted_at`), retry policy from exam config, double-submission
  hardening (status check + idempotency).
- **Grading:** `grading_service.py` `grade_attempt()`; MCQ/T-F; unanswered → 0;
  student-favoring when multiple correct; N+1 avoided by batching option fetch in
  one `IN` query.
- **Audit integrity:** immutable `AuditLog` at two levels (ORM guard + DB trigger
  `RAISE(ABORT)`), no `updated_at`.
- **Transactions:** `@atomic` context manager nests; services use `atomic()` for
  multi-step ops.
- **Idempotency:** `@idempotent` decorator + `Idempotency-Key` header; unique
  `(user, key, endpoint)`; exactly-one-winner; completed requests replayed,
  in-flight → 409; TTL 24h, stale-lock 5min.
- **Database/migrations:** ~10 tables; Alembic migrations incl.
  `1f9d2b3c5a7e_attempt_lifecycle_timing.py`; dev MySQL/PyMySQL, tests
  SQLite-in-memory (concurrency tests need file-backed SQLite).
- **Soft-delete questions** (preserves grading/audit); hard-delete only when
  answer_count == 0 on a locked question.

## Testing

- **Authoritative: 254/255 passing**, 1 pre-existing `test_structure.py`
  failure (trailing-slash — unrelated). Verified via current pytest run.
- unittest-style (pytest) with factories + scenario helper.
- Concurrency harness proved 10 concurrent `/submit` → exactly 1 graded.
- Postman guides surfaced & fixed real bugs (null/wrong-type payload crashes,
  title-suffix length, payload-drop on versioning PUT, exam_id mismatch).

## AI / Docker (important — do NOT overclaim)

- **AI → ASPIRATIONAL / PLANNED (Phase 3):** Phase 2 is deliberately
  AI-free; no AI implemented in the current repo. The portfolio's "AI" tag
  overstates current state (audit §F4/§J). The AI path is a planned future
  direction via Evaluator Core → Quizey Phase 3.
- **Docker → NOT demonstrated in Quizey V2.** No Dockerfile/compose in the repo.
  The portfolio's "Docker" tag overstates current state. Docker is demonstrated
  only in separate DevOps projects (see `../devops/devops.md`).
- Any claim that Quizey V2 currently uses AI or Docker is unsupported by source.

## Publicly safe claims (backend)

- "I'm re-building a production-style assessment backend with Flask, using a
  Route → Service → Model layout, JWT auth + RBAC, copy-on-write exam versioning,
  an attempt state machine, idempotency, and an immutable audit log."
- "The current suite is 254 passing tests plus one pre-existing structural
  failure."

## Claims requiring caution

- Any "Docker"/"AI" stack claim about Quizey V2.
- Any test-count figure other than 254/255 (the portfolio's **174 is STALE**).
- Claiming Phase 2 is fully done: 2.1.1 is code-complete but **not committed**
  and its Postman run is pending.
- "Completed exam attempts / result" beyond what Phase 1 + 2.1.1 proves (2.1.2+
  grading, pools, dashboard not built).

## Known limitations

- Admin flow (manage users/exams) was never built and has no milestone (audit + repo gap).
- `requirements.txt` empty (deps only in venv) — reproducibility gap.

## Related

- Distinct from `projects/quizey_v1.md` (old ALX repo, also labeled Quizey V1).
- AI direction: `ai/evaluator_core.md` (→ Quizey Phase 3).

## Evidence source

`quizey_v2.md`, `README.md`, `docs/engineering/*`, `app/*`, `tests/*`,
`migrations/versions/*`, git history at `/home/alaabadawii/Quizey_V2/.git`.