# Quizey V2 — Flask assessment platform (backend)

## Status
IN PROGRESS. The deep, production-oriented re-architecture of the old ALX
Quizey (`data/completed_projects/quizey.md`, which is a *different*, earlier
repo at `/home/alaabadawii/ALX/Quizey/`). This is Alaa's **main current backend
engineering project**. Source: `/home/alaabadawii/Quizey_V2/`.

Phase 1 (Foundation) is COMPLETE. Phase 2 (Production Assessment Platform)
is IN PROGRESS — prerequisites done, **Milestone 2.1.1 (Attempt Lifecycle) is
code-complete and test-verified but NOT yet committed** (work sits uncommitted
in the working tree; git HEAD is `bc8f7f5 phase2 prerequisites done`).
Phase 3 (AI-Native) is PLANNED.

## Project purpose
Backend-only exam/training platform: teachers create, publish, and manage
quizzes; students take and submit them; the engine auto-grades. Product thesis:
*"Exams are the mechanism. Continuous, measurable learning improvement is the
product."* Three personas: **Creators** (teachers), **Learners** (students),
**Organizations** (schools/companies). Phase 3 intends to add AI analytics on
top of the clean assessment data this phase shapes.
Evidence: `README.md` (lines 1-7), `docs/engineering/03-vision.md`.

## Technologies
Flask · Flask-SQLAlchemy · Flask-Migrate (Alembic) · Flask-JWT-Extended ·
PyMySQL (dev/prod) · SQLite-in-memory (tests) · Werkzeug password hashing ·
Python unittest/pytest. Evidence: `README.md` Tech Stack (lines 11-22). Note:
`requirements.txt` is empty (0 bytes); deps live implicitly in the venv —
an open housekeeping gap.

## Architecture
- **Pattern:** `Route → Service → Model → Database`. Routes are thin (parse
  JSON, delegate, return); services hold all business logic + validation; no
  business logic in routes, ever. Evidence: `README.md` lines 28-30,
  `docs/engineering/phase-1-foundation/00-summary.md` line 22.
- **Modular monolith** by feature blueprint: `auth/`, `exams/`, `attempts/`,
  `grading/` (planned), `agents/` (planned); plus `models/`, `services/`,
  `extensions/` (db, jwt, migrate), `config/`, `utils/`. Evidence: `app/` tree,
  `README.md` lines 32-44.
- Blueprint prefixes under `/api/v1`. Evidence: `README.md` line 128.

## Domain model
Tables: `users` → `exams` (self-referential `root_exam_id` for version
families) → `questions` (soft-delete + `locked_at`) → `options` → `attempts`
(state machine) → `answers`; plus `token_blocklist`, `audit_logs`,
`idempotency_keys`. Evidence: `README.md` lines 46-48, `app/models/`.
- `BaseModel`: `id`, `created_at`, `updated_at`, `save()`/`flush()`/`delete()`.
  Evidence: `app/models/base.py`.
- `User`: unique username/email, `password_hash`, `role` enum
  (student/teacher), `is_active`. Evidence: `app/models/user.py`.
- `Exam`: title, description, `is_published`, `max_attempts`, `duration_minutes`,
  `deadline_at`, `allow_pausing`, `exam_type` (locked/living), `root_exam_id`
  (self-FK, version family), `teacher_id`. Evidence: `app/models/exam.py`.
- `Question`: text, `question_type` (multiple_choice / true_false), `points`,
  `exam_id`, `locked_at`, `deleted_at` (soft delete). Evidence:
  `app/models/question.py`.
- `Attempt`: started_at, submitted_at, score, last_loaded_at, paused_at,
  total_paused_seconds, status (state machine). Evidence: `app/models/attempt.py`.
- `Answer`: `UNIQUE(attempt_id, question_id)`, selected_option_id. Evidence:
  `app/models/answer.py`.
- Audit/housekeeping infra: `AuditLog` (immutable), `IdempotencyKey` (per-user
  per-key, with TTL + in_progress/completed status). Evidence: those model files.

## Auth
- Flask-JWT-Extended: access + refresh token pair on login; refresh route;
  logout blacklists the refresh token's `jti` in `TokenBlocklist` (DB-backed,
  not Redis). Evidence: `app/services/auth_service.py`, `app/models/token_blocklist.py`.
- Registration validates username/email (via `email-validator`) / password
  (8-64 chars, no spaces) / role. Passwords hashed with Werkzeug
  `generate_password_hash`. Evidence: `app/services/auth_service.py`.
- Security note: the authoritative user role is read from the **DB**, not from
  JWT claims (see Authorization).

## Authorization (RBAC)
- `app/utils/rbac.py`: `require_role(*roles)` decorator + `require_student`,
  `require_teacher`. DB is the source of truth for role; looks up `User.role`.
  Returns 403 `Insufficient permissions`. Evidence: `app/utils/rbac.py`.
- Applied across exam routes (`@require_teacher`), attempt routes
  (`@require_student`). PLUS ownership checks in services (teacher owns exam;
  student owns attempt). Evidence: `app/exams/routes.py`, `app/attempts/routes.py`,
  `app/services/exam_service.py`, `attempt_service.py`.
- **Known OPEN gap (Milestone 2.1.4 deck):** the Phase-1 negative Postman test
  confirmed a teacher JWT could hit student-only endpoints before RBAC;
  decorators now exist but Stage 2.1.4 still needs to audit every route and
  re-verify the original 6c test → 403. Evidence: stage-2.1-assessment-platform.md
  lines 396-468.

## APIs (v1 prefix)
- Auth: POST /auth/register, /auth/login, /auth/refresh, /auth/logout,
  GET /auth/me.
- Exams: GET /exams (list, owner-scoped), POST /exams, GET/PUT /exams/<id>,
  POST /exams/<id>/publish, POST /exams/<id>/version, POST/GET
  /exams/<id>/attempts, + questions/options CRUD.
- Attempts: GET /attempts, GET /attempts/<id>, POST /attempts/<id>/answers,
  POST /attempts/<id>/submit, GET /attempts/<id>/result, plus NEW pause/resume:
  POST /attempts/<id>/pause, /resume.
Evidence: `README.md` (lines 126-155), `app/attempts/routes.py`,
`app/exams/routes.py`.

## Services
- `auth_service.py` — register/login/refresh/logout/get_current.
- `exam_service.py` — create/get/get-list/publish/version/update; family
  resolution (`get_family_exam_ids`); publish validation per question type;
  timing-config parsing/validation.
- `question_service.py`, `option_service.py` — CRUD with soft/hard delete
  logic + ownership + `exam_id` argument consistency.
- `attempt_service.py` — the core: family-aware start/resume, pause/resume,
  lazy expiry + auto-finalize-and-grade, timing (4-case), telemetry, retry
  policy (`max_attempts`), answers, submit (idempotent), result, list.
- `grading_service.py` — single `grade_attempt()`; MCQ/T-F, unanswered→0,
  student-favoring multiple-correct; N+1 avoided by batching option fetch.
- `audit_service.py` — `log_action()` writes immutable audit rows (flush(), joins
  enclosing `atomic()`).

## State machine
- `app/models/state_machine.py`: `StateMachineMixin` guarding `status` via
  `@validates`; `ATTEMPT_TRANSITIONS` =
  in_progress → {paused, submitted} → submitted → graded → graded → archived
  → archived terminal. Only legal transitions allowed; others raise
  `InvalidTransitionError`. Evidence: `app/models/state_machine.py`.
- `AttemptStatus` enum: in_progress, paused, submitted, graded, archived.
- Applied via `Attempt(StateMachineMixin, BaseModel)`. Evidence: `app/models/attempt.py`.
- 24 subtest coverage in `tests/test_models/test_state_machine.py`.

## Versioning (copy-on-write)
- Published exams are immutable; editing them (`PUT`) auto-creates a new
  version via `create_exam_version()` (copy active questions+options), new
  version starts as draft (`is_published=False`), `root_exam_id` links the
  family. Explicit `POST /exams/<id>/version` is a pure clone (payload ignored).
- Only one version per family is published at a time (sibling demotion happens
  only on new *publish*, not on version *creation* — old stays live/gradable
  while the new draft is edited).
- Title suffix `(v{n})`; 249-char cap to fit DB 255 (suffix `(v99)`). Evidence:
  `app/services/exam_service.py`, `docs/.../phase-1-foundation/00-summary.md`.

## Database design / migrations
- 10 tables total (users, exams, questions, options, attempts, answers,
  token_blocklist, audit_logs, idempotency_keys). Evidence: `app/models/`,
  `migrations/versions/`.
- Migrations present (Alembic): initial all-models, add_root_exam_id,
  add_idempotency_keys, add_audit_logs, widen password hash, and
  `1f9d2b3c5a7e_attempt_lifecycle_timing.py` (paused_at /
  total_paused_seconds). Evidence: `migrations/versions/`.
- Dev DB MySQL/PyMySQL; tests SQLite in-memory (EXCEPT concurrency tests which
  need a file-backed DB because in-memory gives each pooled connection a
  private DB — documented in `tests/test_attempts/test_concurrency.py`).

## Engineering decisions (evidence-backed)
- **Layers don't leak:** routes never contain business logic.
- **DB is role source of truth** (not JWT claims) — Prereq 5 decision.
- **Audit log immutable at 2 levels** (ORM guard + DB trigger `RAISE(ABORT)`),
  no `updated_at` — Prereq 6. Evidence: `app/models/audit_log.py`.
- **Atomic transactions:** `@atomic` context manager nests; only outermost
  commits/rolls back; services use `atomic()` not bare `save()` for multi-step
  ops. Evidence: `app/utils/transactions.py`.
- **Idempotency:** `@idempotent("endpoint")` decorator + `Idempotency-Key`
  header; exactly-one-winner under `(user,key,` endpoint)` unique constraint;
  completed responders replayed, in-flight → 409; TTL 24h, stale-lock 5min.
  Evidence: `app/utils/idempotency.py`, `app/models/idempotency_key.py`.
- **Four-case assessment model:** (no duration+no deadline=untimed→null;
  duration only→active remaining; deadline only→wall-clock; both→min of the
  two); expiry computed *lazily* (on each read/write), NOT a background
  scheduler. Evidence: `app/services/attempt_service.py`, milestone doc.
- **Pause is exam-controlled** (`allow_pausing`); pause freezes active clock
  but a wall-clock `deadline_at` keeps advancing while paused. Evidence:
  stage-2.1 doc Engineering Decisions Log.
- **`submitted_at` = real finalization time** (never the configured deadline);
  expiry is a derived flag. Evidence: attempt doc.
- **Student-favoring grading** when a question has multiple correct options.
  Evidence: `grading_service.py` docstring.
- **Soft-delete on questions** (not hard) preserving grading/audit trails;
  hard-delete only when answer_count == 0 on a locked question. Evidence:
  phase-1 summary, `question_service.py`.
- **N+1 optimization:** grader fetches all selected options in one `IN` query.
  Evidence: `grading_service.py` line 21-25, phase-1 summary audit #.

## Testing
- **AUTHORITATIVE test count: 254/255 passing,** 1 pre-existing failure
  (`test_structure.py`, trailing-slash assertion — unrelated to functional
  code, confirmed `01.failed,254 passed` this session). Evidence: current
  pytest run. This is the single authoritative figure for Quizey V2; older
  figures are historical snapshots only — README.md documents 226 (older), and
  the portfolio (2026-07-15) documents 174 (stale, pre-Phase-2-prereqs). See
  `../audit/cross_source_audit.md` §B1 and `../public_positioning/portfolio.md` §A.
- unittest-style (pytest collection) with factories (user/exam/question/option
  /attempt/answer) and a scenario helper (`tests/scenarios/attempt_scenario.py`).
- Coverage areas (approx per phase-1 summary): auth (34), attempts routes (13),
  attempts service (12), attempt integration (18), attempt lifecycle (28, NEW),
  concurrency (6), exams routes (13) + service (23) + advanced (21), questions
  service (17+4), structure (1), transaction, etc.
- Concurrency harness (tests/machines/concurrency.py) built to prove
  10 concurrent /submit → exactly 1 graded. Evidence: `tests/concurrency.py`,
  `tests/test_attempts/test_concurrency.py`.

## Postman / API testing
- `docs/engineering/phase-1-foundation/02-postman-testing-guide.md` — Phase 1
  manual verification (Auth folder; Exams folder; Questions folder) — surfaced
  and fixed multiple input-validation bugs (null-crashes, header-type crashes,
  title-suffix length, payload-drop on versioning PUT, question_type not
  applied, exam_id mismatch, non-string option text).
- NEW: `docs/engineering/phase-2-production-platform/postman_collection.json`
  (a full 9-folder collection) + a testing-guide for Milestone 2.1.1
  (Attempt Lifecycle, Timing Configs, Pause & Resume, Expiry, Telemetry,
  Submission/Idempotency, Authorization, Retry, Version Family).
  **Status: collection is WRITTEN but not yet run live end-to-end** — this is
  the one open DoD item for 2.1.1.

## Completed phases
- **Phase 1 — Foundation ✅** CODE-COMPLETE, test-verified, previously
  Postman-verified (Auth done, Exams+Questions at the time). Auth, exam CRUD,
  versioning, attempts, auto-grading, full test suite.
  Evidence: `docs/engineering/phase-1-foundation/00-summary.md` (incl. 7-item
  post-implementation audit of severity: plaintext-password fallback removed,
  unauthenticated grading crash removed, lazy-expiry list skip fixed,
  hardcoded (v2) fixed to computed version number, 204-with-body→200, N+1 in
  grading, test helper relying on the password bug). Commits: `phase1-Done` etc.

## Current phase / current work (IN PROGRESS)
- **Phase 2 prerequisites** all seven complete & signed off (state machine,
  idempotency, transactions, concurrency harness, RBAC, immutable audit log,
  idempotency middleware). Evidence: `docs/.../stage-2-prerequisites.md`.
- **Milestone 2.1.1 Attempt Lifecycle — code done, Postman pending:**
  pause/resume (model `attempt.py`, services, routes), timing four-case model,
  lazy expiry for in_progress AND paused (no resurrection), telemetry
  (elapsed/active/paused, real submitted_at), retry policy from exam config,
  double-submission hardening (status check + idempotency). 26 lifecycle tests
  pass. Postman folders written; manual live rund not yet done.
  Evidence: code files, `tests/test_attempts/test_attempt_lifecycle.py`,
  `docs/.../stage-2.1`, `docs/.../postman-testing-guide.md`.

## Planned work (PLANNED)
- **Milestone 2.1.2 Advanced Grading** — Strategy-pattern grading engine,
  partial credit for multi-select, Question.weight / is_bonus /
  negative_marking_enabled, scoring order-of-ops, Rubric+RubricCriterion,
  manual grading queue, GradeOverride + grade history. Not started.
- **2.1.3 Assessment Rules** — ExamRules model (shuffle/pool/max_attempts/
  passing_score/availability/access_code), seeded reproducible shuffle, pools,
  rules enforced at start_attempt. Not started.
- **2.1.4 Integrity & Audit** — audit role coverage, wire immutable-submission
  guarantee, define admin bypass, re-verifying the 403 Postman test. Foundation
  done; wiring remains.
- **2.2 Publishing/Version Mgmt · 2.3 Question Bank · 2.4 Instructor Dashboard
  · 2.5 Student Experience · 2.6 Platform Services (Redis/Celery, storage,
  security) · 2.7 DevOps/CI-CD/monitoring.**
- **Phase 3 AI-Native** (authoring, intelligent grading with human-in-loop,
  personalized learning via, multi-agent) — outline only.
- **Open documented gap:** an Admin flow (manage users/exams) that was NEVER
  built and has NO milestone anywhere in this Phase 2 roadmap (see
  `docs/engineering/phase-2-production-platform/00-overview.md` "Open Gap").

## Important milestones
1. **2026-05-23** initial scaffold (monolithic Flask starter via Copilot PR).
2. **2026-07-14/29** Phase 1 marked "Done" — core loop
   (create→publish→attempt→grade) + full Phase 1 test suite; 7-item audit fixed.
3. **2026-08-05→07** Stage 2 prerequisites completed; Phase 2 planning docs +
   all 7 foundations (state machine, idempotency, transactions, concurrency,
   RBAC, audit, idempotency-middleware).
4. **Milestone 2.1.1 code done (post-prereq)** — pause/resume + lifecycle
   timing + 26 tests + Postman collection written (yet to be executed).

## Lessons documented
Cross-referenced where applicable — the KB's `stories_lessons/` captures general
lessons (e.g., "verify LLM output with code", "never commit secrets"); the
project-specific ones for Quizey_V2 are logged inside
`docs/engineering/phase-1-foundation/00-summary.md` ("bugs found & fixed this
session") and the seven-item Phase-1 audit. Key transferable takeaways:
- **Test-driven loop hardens real edge cases** — the Postman pass turned 5+
  crash bugs (null / wrong-type payload) into clean 422s and guards before
  `.strip()`.
- **Copy-on-write + self-referential FK** is a clean way to make published
  artifacts immutable while still editable; demote-on-publish (not create)
  preserves the old version gradable throughout editing.
- **Idempotency + status-check** are both needed to make double-submission
  provably impossible under concurrent retries.
- **DB as role source of truth** avoids stale JWT claims.
- **Concurrency tests need a file-backed DB** — a subtle gotcha with in-memory
  SQLite (each pooled connection gets its own private DB, so threads never
  share rows).

## Potential personal-branding stories (NOT YET WRITTEN — topics only)
1. Rebuilding an assessment platform with a real engineering lifecycle:
   state machines, transactions, idempotency, RBAC, immutable audit — turning
   "a quiz app" into a defensibly-production-grade assessment backend.
2. The seven prerequisites work as a deliberate design (why you build a state
   machine, concurrency harness, and audit trigger *before* features).
3. Copy-on-write / version families + publish-demote semantics — a clean
   design-for-immutability story.
4. Found-and-fixed audit (plaintext-password fallback, unauth grading route)
   — an honest "self-review before shipping" engineering story.
5. The frustrating reality that only noisy frontend/Postman verification catches
   crashes (null IDs) that unit tests miss — testing-vs-real-world-usage.

Provenance above is in-file; see evidence keys for each.

---
## Provenance / evidence file-map
- `README.md` — product, stack, architecture, API list, roadmap.
- `docs/engineering/01-roadmap.md` — phase/stage/milestone structure.
- `docs/engineering/phase-1-foundation/00-summary.md` — Phase 1 record + audit.
- `docs/engineering/phase-2-production-platform/` — stage-2.1 assessment
  platform (milestone detail), 00-overview, stage-2-prerequisites(+notes),
  postman-testing-guide + postman_collection.json.
- `app/` source (models/, services/, utils/, attempts/, exams/, auth/).
- `tests/` (incl. test_attempts/test_attempt_lifecycle.py).
- `migrations/versions/`.
- Git history at `/home/alaabadawii/Quizey_V2/.git`.