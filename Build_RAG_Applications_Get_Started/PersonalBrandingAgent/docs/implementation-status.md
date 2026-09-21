# Personal Branding Agent — Implementation Status

## Purpose

`PLAN.md` (repository root) is the **master implementation roadmap**. It defines
what is going to be built, in what order, and what "done" means for each step.

This file is the **continuation point**. It records only what has actually been
implemented, verified, and committed — plus what is currently broken and where
work resumes. It is deliberately short.

It is **not** a design document. Architecture belongs in `docs/architecture/`;
decisions belong in `docs/decisions/ADRs/`; technical detail belongs beside the
code. This file answers four questions:

```text
What happened?   What is proven?   What changed from the plan?   Where do we continue?
```

**Rule of truth:** nothing appears here as complete until it has passed its
acceptance criteria and been committed. Plans, intentions, and "should work"
do not belong in this file.

---

## Current Status

```text
Current Step:
    Step 2 — Define the Personal Knowledge Source Registry & Project Lifecycle

Status:
    NOT STARTED

Overall Progress:
    Steps 0 and 1 COMPLETED. The environment is reproducible, the test
    baseline is restored, and the operational state store exists. Steps 2–14
    have not been started.

Last Completed Step:
    Step 1 — Introduce Persistent Operational State (SQLite)

Next Step:
    Step 2 — Define the Personal Knowledge Source Registry & Project Lifecycle
```

The roadmap was rewritten and finalized after an architecture and readiness
analysis of the repository. Steps 0 and 1 have since been implemented,
verified, and committed; every later step remains untouched.

---

## Step Progress

Status vocabulary: `NOT STARTED` · `IN PROGRESS` · `BLOCKED` · `COMPLETED`

| Step | Name | Status |
|---|---|---|
| 0 | Restore a Reproducible, Testable Environment | COMPLETED |
| 1 | Introduce Persistent Operational State (SQLite) | COMPLETED |
| 2 | Define the Personal Knowledge Source Registry & Project Lifecycle | NOT STARTED |
| 3 | Build Incremental Knowledge Synchronization | NOT STARTED |
| 4 | Build the Personal Branding Context & Evidence Layer | NOT STARTED |
| 5 | Harden the LinkedIn Integration for Autonomous Use | NOT STARTED |
| 6 | Build Persistent Publishing, Idempotency & Recovery | NOT STARTED |
| 7 | Build Operational Failure Notifications via Email | NOT STARTED |
| 8 | Build Grounded Post Generation | NOT STARTED |
| 9 | Build Evidence Verification & Revision Gates | NOT STARTED |
| 10 | Build the Autonomous Branding Agent | NOT STARTED |
| 11 | Build the 24h Knowledge-Sync and 8h Branding Workflows | NOT STARTED |
| 12 | Add External Scheduling, Locks & Recovery | NOT STARTED |
| 13 | End-to-End Autonomous Evaluation | NOT STARTED |
| 14 | Operational Documentation, Deployment & Final Hardening | NOT STARTED |

> Step names above are taken verbatim from `PLAN.md` §8. If a step is renamed
> there, rename it here too.

---

## Completed Steps

### Step 1 — Introduce Persistent Operational State (SQLite)

Status: COMPLETED

Implemented:
- Created `app/state/` — the new lowest layer of the application, depending on
  nothing above it. Five modules: `enums.py` (controlled vocabularies),
  `models.py` (typed row models + UTC helpers), `schema.py` (DDL and the
  forward-only migration runner), `store.py` (`StateStore`), and `__init__.py`.
- Single-file SQLite store at `<PROJECT_ROOT>/state_db/operational_state.db`,
  created automatically on first use, with foreign keys and WAL mode set on
  every connection, `busy_timeout` bounded at 5 s, and all timestamps stored
  as UTC ISO-8601 with microseconds.
- Nine tables: `workflow_runs`, `sync_checkpoints`, `source_lifecycle`,
  `publish_intents`, `publications`, `publication_evidence`,
  `operational_failures`, `notifications`, `locks`.
- A `schema_version` ledger and a forward-only migration runner. It is
  idempotent, refuses a store written by a newer build, and refuses a
  non-contiguous migration history rather than applying a migration out of
  order. Each migration runs in its own transaction.
- **Correctness expressed as database constraints, not application checks:**
  one publish intent per run (`MAX_PUBLISHES_PER_RUN = 1`); one *unresolved*
  intent per content hash across runs; one publication per intent; run
  outcome and publish state restricted to their vocabularies; a run has an
  outcome exactly when it has finished; `published` ⟺ a LinkedIn post id is
  present; lifecycle and delivery states restricted to their vocabularies; a
  checkpoint revision and its timestamp travel together; one holder per lock.
- Typed operations only — no SQL leaves the package. Runs, checkpoints,
  lifecycle, intents (`create_publish_intent`, `mark_attempt_started`,
  `record_publication`, which resolves the intent in the same transaction),
  failures with occurrence counting, notifications, and locks with stale
  recovery.
- Added `StateStoreError` and `StateConstraintError` to `app/errors.py`;
  `STATE_DB_DIR` / `STATE_DB_PATH` to `app/paths.py`; `state_db/` to
  `.gitignore`.

Verified:
- Acceptance: the store is created on first use from an unrelated CWD, at a
  gitignored location (`git check-ignore` confirms the rule), and every
  guarantee above is additionally proven by **raw SQL through an independent
  connection** — so none of them can be passing merely because Python checked
  first.
- One-publish-per-run is rejected by the database, not by application logic.
- Fails closed at every boundary: an unusable location raises at construction
  (so no store object exists to ignore), a closed store raises on every
  operation, and a writer that cannot get the lock within the bounded timeout
  raises a typed `StateStoreError` rather than a raw `sqlite3` error. There is
  no path that records a publication without its write-ahead intent.
- Milestone: a run record written by one `StateStore` is read back intact by a
  new `StateStore` after the first is closed.
- The state layer never loads the knowledge layer: a subprocess asserts that
  using the store imports neither `chromadb`, `langchain_chroma`,
  `sentence_transformers`, `app.ingestion`, nor `app.retrieval`. Operational
  data cannot reach the Chroma collection because the code that could write to
  it is never imported.

Tests:
- `tests/test_state_schema.py` (22 tests) and `tests/test_state_store.py`
  (49 tests) — **71 new tests**, none of them touching the network.
- Regression: `.venv/bin/python -m pytest tests/ -q` → **150 passed**, zero
  collection errors, zero failures (79 pre-existing + 71 new). No existing test
  was modified, weakened, or skipped.
- `PYTHONNOUSERSITE=1` was used throughout.

Commit:
- `Step 1: introduce persistent operational state (SQLite)` — the commit
  carrying this record. The subject is used instead of a hash because the hash
  cannot contain itself; find it with `git log --oneline --grep="^Step 1:"`.

Important notes:
- **Two constraints are deliberately stricter than the roadmap's wording**, and
  both are relaxable later by a forward migration:
  - `PLAN.md` says "at most one publication per content hash **per time
    window**". Implemented as one unresolved intent per content hash, with no
    window: publishing identical text again is never desirable, and the intent
    is written *before* the API call, which is the only point at which the
    constraint can prevent the publish rather than merely record it after the
    fact.
  - "At most one **active** publish intent per run" is implemented as one
    intent per run, flat. `MAX_PUBLISHES_PER_RUN = 1` is a hard invariant, and
    retries belong across runs (each 8-hour run is a new run), not within one.
- `workflow_runs.workflow` and `operational_failures.error_category` are
  intentionally **not** CHECK-constrained. Their vocabularies belong to Steps
  11 and 5/8; fixing them here would only force a migration later. The two
  vocabularies the roadmap insists on — run outcome and publish state — are
  constrained.
- A `failed` intent drops out of the content-hash index (an attempt that
  definitely did not publish must not burn the content), while
  `unknown_requires_review` stays in it. This is what makes the ambiguous case
  safe: the one outcome where a post may exist is the one that blocks a retry.
- No CLI was added. The store is a library; Steps 11–12 own the entry points.
- No new configuration key was added — `DEFAULT_LOCK_TTL_SECONDS` is a default
  parameter in `app/state/store.py` because Step 12 owns the configured value.
- `state_db/` was created and removed again during verification; no runtime
  state is committed. It will be created for real the first time a workflow
  runs.

### Step 0 — Restore a Reproducible, Testable Environment

Status: COMPLETED

Implemented:
- Created a project-local `.venv` on Python 3.10.12 from the unmodified
  `requirements.txt` (stdlib `venv` only; no `uv`, Poetry, Conda, or Docker).
- Installed the pinned stack. **No pin was relaxed and `requirements.txt` was
  not changed** — the pins were already correct; the environment did not match
  them.
- Wrote `docs/operations/environment.md` (Python-version justification,
  reproduction procedure, resolved versions, `~/.local` isolation),
  `docs/operations/local-development.md` (configuration authority, CWD
  independence, CLI and test usage), and `docs/operations/security.md`
  (secret/non-secret split, redaction, commit boundary).
- Updated `docs/README.md` to record that `docs/operations/` now exists.

Not changed:
- **No application source, no test, and no `requirements.txt` was modified.**
  Root `config.py` was **not** deleted (Step 0 explicitly scopes that out).
- `Auth_handling/*` working-tree changes remain uncommitted — reconciled by
  Step 5.

Verified:
- `pip check` → no broken requirements; 158 distributions installed.
- Application imports succeed (`app.config`, `app.paths`, `app.errors`,
  `app.logging_config`, `app.ingestion.pipeline`, `app.retrieval.{vector,bm25,engine}`).
- The four previously-failing modules (`test_ingestion`, `test_retrieval`,
  `test_fusion`, `test_evaluation`) import and pass: 63 passed, zero collection
  errors.
- `.venv` is the only package source: `ENABLE_USER_SITE=False`, no `.local` path
  in `sys.path`, and every probed import resolves inside `.venv`.
- All three CLIs run from an unrelated CWD (`/tmp`), exit 0:
  `app.ingestion.pipeline`, `app.retrieval.compare`, `app.retrieval.evaluation`.
  The ingestion report printed `store location : <PROJECT_ROOT>/chroma_db`,
  proving CWD-independent path resolution.
- Ingestion idempotency (milestone): two consecutive runs from `/tmp` produced
  byte-identical reports — 71 sources discovered, 71 unchanged, 0 added, 0
  updated, 0 removed, 342 chunks in store. No writes on either run.
- The pre-existing `chroma_db/` (built under `chromadb` 0.4.24) opened and
  served correctly under `chromadb` 1.5.9 with no migration step.
- Reproducibility from scratch: a throwaway venv created by the documented
  procedure resolved the **identical 158 distributions** and passed the suite.

Tests:
- `.venv/bin/python -m pytest tests/ -q` → **79 passed**, zero collection errors,
  matching the recorded historical baseline (79 across 7 modules). No test
  added, removed, weakened, or skipped.
- `PYTHONNOUSERSITE=1 .venv/bin/python -m pytest tests/ -q` → **79 passed**
  (identical), proving no `~/.local` dependence.

Commit:
- `Step 0: restore a reproducible, testable environment` — the commit carrying
  this record, directly after
  `docs: finalize the implementation roadmap and documentation index`. The
  subject is used instead of a hash because the hash cannot contain itself; find
  it with `git log --oneline --grep="^Step 0:"`.

Important notes:
- The historical "dependency conflict" was **not** a defect in
  `requirements.txt`. Installing the pins resolves cleanly, so the Step 0 commit
  boundary clause *"requirements correction (if the pins prove wrong)"* did not
  apply.
- `python -m app.<module>` is not importable from an unrelated CWD because the
  repository declares no installable package (no `pyproject.toml`/`setup.py`).
  This is an import-path concern, not a CWD-independence defect: with
  `PYTHONPATH=<PROJECT_ROOT>` set, all internal state resolves absolutely from
  `PROJECT_ROOT`. Documented in `local-development.md` §4.
- The configured LLM key is an OpenAI-family key (`sk-proj-…`) sent to the
  OpenRouter base URL, so multi-query expansion degrades to its documented
  fallback (401). Not caused by Step 0, does not affect ingestion or retrieval,
  and does not block any Step 0 criterion. Recorded as Known Issue #5.

*(Older records use the following form.)*

```markdown
### Step N — <Step name>

Status: COMPLETED

Implemented:
- <what actually changed>

Verified:
- <what was proven, and how>

Tests:
- <suite/command and result>

Commit:
- <hash and subject>

Important notes:
- <deviations, surprises, follow-ups>
```

---

## Current Step

```text
Step 2 — Define the Personal Knowledge Source Registry & Project Lifecycle
Status: NOT STARTED
```

The full specification — reason, scope, implementation approach, tests, failure
handling, and acceptance criteria — is in `PLAN.md` §8, Step 2. It is not
duplicated here.

---

## Known Issues / Blockers

Verified conditions that block or complicate implementation. Issue #1 was
resolved by Step 0 and is kept for the record; the rest are open.

### 1. ~~The application cannot currently be imported~~ — RESOLVED in Step 0

The historical retrieval/test environment was **not reproducible**.

```text
tests/test_evaluation.py   → ModuleNotFoundError: rank_bm25
tests/test_fusion.py       → ModuleNotFoundError: rank_bm25
tests/test_retrieval.py    → ModuleNotFoundError: rank_bm25
tests/test_ingestion.py    → ImportError: cannot import name 'Search' from 'chromadb'
```

Installed versus pinned in `requirements.txt`:

| Package | Pinned | Was installed | Now |
|---|---|---|---|
| `langchain` | `>=1.3,<2` | 0.3.12 | 1.4.2 |
| `langchain-core` | `>=1.6,<2` | 0.3.63 | 1.6.4 |
| `langchain-chroma` | `>=1.1,<2` | 1.1.0 | 1.1.0 |
| `chromadb` | `>=1.5,<2` | 0.4.24 (incompatible pair) | 1.5.9 |
| `langchain-huggingface` | `>=1.2,<2` | missing | 1.2.2 |
| `rank_bm25` | `>=0.2.2,<1` | missing | 0.2.2 |

There was no project-local virtual environment; 4 of 8 test modules failed to
collect and only 16 tests collected.

**Resolved** by creating a project-local `.venv` from the unmodified pins. The
pins were correct; the environment did not match them. No test was weakened to
work around it. See *Completed Steps* → Step 0.

### 2. The knowledge base is already stale

`data/in_progress_projects/quizey_v2.md` records a git revision that is now
**18 commits behind** the real repository, and the source path it records no
longer exists. 48 of 71 knowledge-base files embed absolute source paths, some
of them dead.

This is not a one-time cleanup — drift is continuous. Addressed by **Steps 2–3**.

### 3. Uncommitted working-tree changes exist in `Auth_handling/`

`Auth_handling/test_credentials.py` and `Auth_handling/test_post.py` carry
**uncommitted** edits that resolve the token file relative to `__file__`.
`linkedin_oauth_setup.py` — the script that *creates* the token — still uses a
CWD-relative literal path, so it writes the token where the two readers will not
look.

Reconciled by **Step 5**.

### 4. Documentation referenced but not written

`docs/README.md` previously described documents that do not exist. Partly
resolved by Step 0:

- `docs/operations/` — **now written** (`local-development.md`,
  `environment.md`, `security.md`).
- `docs/evaluation/` — still an empty directory.
- `docs/phases/` — contains only phases 01–02.
- `docs/decisions/ADRs/` — contains only an index; the ADRs it lists as
  "Accepted" have no files.

The remainder is addressed by **Step 14**.

### 5. The configured LLM key does not match the configured provider

`app/config.py` sends its key to `OPENROUTER_BASE_URL`
(`https://openrouter.ai/api/v1`), but the key currently in `.env` is an
**OpenAI platform key** (the `sk-proj-…` family), not an OpenRouter key
(`sk-or-v1-…`). OpenRouter rejects it:

```text
WARNING app.retrieval.multi_query: Multi-query LLM call failed
(Error code: 401 - {'error': {'message': 'Missing Authentication header',
'code': 401}}); using original query
```

Impact is bounded. It does **not** affect ingestion, vector search, metadata
filtering, BM25, hybrid fusion, or reranking — none of which use an LLM. Only
multi-query expansion is affected, and it degrades safely: it logs a warning,
falls back to the original query, and the CLI exits 0. The evaluation CLI
records it as `fallbacks`; all 12 gold queries took the fallback path, which
means **`multi_query` currently scores identically to plain `vector` search**.

Not caused by Step 0 and not a Step 0 blocker. It must be corrected before
**Step 8** (grounded post generation), which genuinely requires an LLM. Fix is a
configuration change — put a valid OpenRouter key in `.env` — not a code change.

### 6. The CLIs are not importable from an unrelated CWD without `PYTHONPATH`

The repository declares no installable package (no `pyproject.toml`, `setup.py`,
or `setup.cfg`) and `.venv` has no `.pth` or editable install pointing at the
project root. `python -m app.<module>` therefore fails from any directory other
than the project root:

```text
ModuleNotFoundError: No module named 'app'
```

This is an **import-path** concern only. The application's own state (`.env`,
`data/`, `chroma_db/`, `logs/`) is CWD-independent via `app/paths.py`, and all
three CLIs were verified working from `/tmp` with `PYTHONPATH=<PROJECT_ROOT>`.
Documented in `docs/operations/local-development.md` §4.

**Step 12** schedules these CLIs and must set `PYTHONPATH` or run from the
project root. Making the project installable is a candidate follow-up.

---

## Important Decisions / Deviations

Established while finalizing the roadmap. Preserved here because losing them
would change the architecture. Detail lives in `PLAN.md`; this is a register,
not a specification.

| Decision | Rationale (short) | Detail |
|---|---|---|
| **Operational state stays separate from Chroma** | Published posts must never become evidence about the user | `PLAN.md` §6 |
| **Operational state lives in one SQLite store at `state_db/`** | A single-file store, created on first use, is the whole runtime for one user on one machine; it is gitignored but, unlike `chroma_db/`, **not rebuildable** — local publication history is authoritative | Step 1, `app/state/`, `docs/operations/security.md` |
| **Correctness lives in database constraints, not in callers** | One publish intent per run and one unresolved intent per content hash are enforced by SQLite, so a workflow cannot forget to check and a second publish is refused by the database | Step 1, `app/state/schema.py` |
| **The state store fails closed** | An unusable location raises at construction, a closed store raises on every operation, and no publication can be recorded without its write-ahead intent — so a store failure stops a publish instead of permitting one | Step 1, `app/state/store.py` |
| **`published` if and only if LinkedIn returned a post id** | The proven path reads the id from the response; a response without one is a failure or an ambiguity, never a success. Enforced by a CHECK constraint | Step 1, `app/state/schema.py` |
| **An intent and its publication resolve in one transaction** | The two can never disagree about what happened; the write-ahead intent is the only duplicate protection that exists without read-back | Step 1 (schema + store), used by Step 6 |
| **Evidence references are stored as source path + content hash** | The corpus is resynchronized every 24 h; without the hash a later audit cannot distinguish "grounded in evidence that has since changed" from "never grounded" | Step 1 (table), written by Step 6 |
| **Local publication history is authoritative** | LinkedIn read access (`r_member_social`) is restricted to approved users; there is no read-back | `PLAN.md` §5.1 |
| **Publishing history is NOT indexed into Chroma (V1)** | Avoids a generated post becoming evidence for the next one; deterministic SQLite queries answer the Agent instead | `PLAN.md` §6.1 |
| **Git detects change; it does not replace ingestion** | The existing content-hash pipeline already guarantees correctness — git only narrows the candidate set | `PLAN.md` Step 3 |
| **An explicit source registry is required** | Workspace roots contain ~35 repos, virtualenvs, and this application itself; roots are places to inspect, not sources to ingest | `PLAN.md` Step 2 |
| **The application must not ingest itself** | `~/LLMs/IBM` contains this project; its own source and runtime state are not professional evidence | `PLAN.md` Step 2 |
| **LinkedIn publishing has already been manually verified** | A real public post was published via `Auth_handling/`. This is a **pre-existing baseline**, not an implementation result of this roadmap | `PLAN.md` §4 |
| **No automatic token refresh is assumed** | The saved token has no `refresh_token`; `offline_access` alone is not proof it can work | `PLAN.md` Step 5 |
| **The Agent remains bounded** | The Agent decides topic/angle/evidence and whether to publish; it never bypasses gates, limits, or recording | `PLAN.md` §7, Step 10 |
| **Hard safety rules remain deterministic** | One post per run, evidence gates, duplicate prevention, and recording are application logic — never Agent discretion | `PLAN.md` §2, §7 |
| **Autonomous failure notification is required** | Unattended runs must reach the user by email; notification is deterministic infrastructure, not an Agent choice | `PLAN.md` Step 7 |
| **The 24h and 8h workflows remain separate** | Different periods, failure domains, and blast radii; sync must never publish, branding must never ingest | `PLAN.md` Step 11 |
| **Three workflow outcomes are distinguished** | `DO_NOT_PUBLISH` (success, no alert) · `WORKFLOW_FAILED` · `REQUIRES_HUMAN_INTERVENTION` | `PLAN.md` §2, §11 |
| **Project lifecycle is explicit** | `ACTIVE · PAUSED · COMPLETED · PLANNED`; never inferred from inactivity | `PLAN.md` Step 2 |
| **Environment is a project-local Python 3.10 `.venv`** | Matches the existing `requirements.txt`; no `uv`, Poetry, Conda, or Docker | `PLAN.md` Step 0, §7 |
| **Python 3.10 is confirmed, not assumed** | It is the floor of the pinned stack (`torch` requires `>=3.10`; `langchain`/`langchain-core` require `>=3.10.0`), the source uses nothing newer, and it is the machine's system interpreter. Resolves `PLAN.md` §12.2 item B. | `docs/operations/environment.md` §2 |
| **`app/config.py` is the authoritative configuration module** | Root `config.py` is a re-export shim with no consumers; it is retained, documented as unused, and its removal is a follow-up — not part of Step 0 | `docs/operations/local-development.md` §1 |
| **Secrets live only in `.env` or the gitignored token file** | Model ids, chunk/retrieval parameters, and paths grant no external access and stay committable in `app/config.py`; `SecretRedactionFilter` scrubs secret *values* from every log line | `docs/operations/security.md` §2, §4 |
| **Notifications use SMTP** | Provider-agnostic interface, configured for Gmail; stdlib preferred; fake transport in tests | `PLAN.md` Step 7 |
| **Infrastructure stays minimal** | LangGraph, MCP, multi-agent, queues, Redis, PostgreSQL, microservices, Kubernetes, and distributed workers are deferred with reasons | `PLAN.md` §7 |

---

## Next Step

### Step 2 — Define the Personal Knowledge Source Registry & Project Lifecycle

The next implementation task is defined in `PLAN.md` §8, Step 2.

Synchronization needs a precise, explicit definition of *what* is
synchronized. The declared workspace roots are **places to look, not sources to
ingest**: they contain ~35 repositories, virtual environments, coursework, and
`~/LLMs/IBM` — the monorepo that contains this application itself.

Constraints carried in from Steps 0–1 and the architecture:

- Step 2 must **complete the workspace inspection** before writing the registry;
  the inspection recorded in `PLAN.md` §5.3 was performed at limited depth and
  is a starting point, not a substitute. `~/ALX` (~21 entries) needs deliberate
  triage.
- The registry is **configuration** (committed, human-editable); its runtime
  state belongs in the Step 1 store. `sync_checkpoints` and `source_lifecycle`
  already exist and are waiting for it.
- **The application cannot ingest itself**, proven by test.
- Lifecycle is explicit and persisted, never inferred from inactivity; a
  `COMPLETED` source with new commits produces a review signal.
- `data/` is not restructured, and ingestion/retrieval are untouched.

---

## Maintenance Rule

Update this file **only after** an implementation step has:

1. been implemented
2. passed its focused tests
3. passed the required regression checks
4. satisfied its acceptance criteria
5. been committed

Then record, in the same pass:

```text
what changed · what was verified · important deviations · commit · next step
```

Specifically:

- Append a record to **Completed Steps**.
- Flip the step's row in **Step Progress**, and update **Current Status**.
- Replace **Current Step** and **Next Step** with the following step.
- Add any newly discovered issue to **Known Issues / Blockers**.
- Add any decision taken during the step to **Important Decisions**.

Do not update status ahead of the work. Do not mark a step `COMPLETED` because
its code was written — only because its criteria passed.

---

## Related Documentation

| Document | Role |
|---|---|
| [`../PLAN.md`](../PLAN.md) | Master implementation roadmap (authoritative) |
| [`architecture/`](architecture/) | System design — how the system is intended to work |
| [`decisions/ADRs/`](decisions/ADRs/) | Architecture decision records |
| [`retrieval/`](retrieval/) | Retrieval milestone — concepts and measured results |
| [`evaluation/`](evaluation/) | Evaluation results *(not yet written)* |
| [`operations/`](operations/) | Operational documentation — local development, environment, security (written in Step 0) |
| [`phases/`](phases/) | Foundational phase documents (phases 01–02; superseded by `PLAN.md` Steps 0–14) |
