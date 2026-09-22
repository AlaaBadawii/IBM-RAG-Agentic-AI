# Operational State Model

The authoritative schema of the runtime database (`PLAN.md` Step 14: the
state model documented as a schema). Everything below describes the **actual
implementation** in `app/state/schema.py` (schema version 4) — tables,
columns, constraints, transitions, guarantees, and which component owns each
state. No invented tables, no invented guarantees.

---

## 1. Physical properties

| Property | Value |
|---|---|
| Location | `state_db/operational_state.db` (gitignored, **not rebuildable**) |
| Engine | Single-file SQLite, WAL mode, foreign keys on |
| Timestamps | UTC ISO-8601 with microseconds and `+00:00`, lexicographically ordered |
| Migrations | Forward-only, append-only (`Migration` values in `schema.py`); applied set recorded in `schema_version`; no down path |
| Current version | 4 (v1 initial schema, v2 credential expiry, v3 project + embedding columns, v4 phase trail) |

A newer store than the code understands is refused outright; a gapped
migration ledger is refused rather than repaired. Both refusals raise
`StateStoreError`, which fails closed everywhere it can surface.

## 2. Entity map

```text
workflow_runs ──┬── publish_intents ── publications ── publication_evidence
                │        (1:1)             (1:1)
                ├── workflow_phases (1:N, the trail)
                ├── operational_failures (1:N, by run_id; plus run-detached rows)
                └── notifications (1:N, by run_id)

sync_checkpoints (per source)        source_lifecycle (per source)
locks (per workflow)                 linkedin_credential_expiry (per credential)
schema_version (ledger)
```

`run_id` on failures and notifications is nullable by design: rows written
outside any run (lock rejections, interrupted-run reports, stale-lock
recoveries) carry `run_id NULL` and therefore never leak into a run's
notification email, which is composed from run-linked rows only.

## 3. Tables

### 3.1 `workflow_runs` — owned by Step 11 workflows

One row per workflow execution, opened by `start_run`, resolved exactly once
by `finish_run`.

| Column | Meaning |
|---|---|
| `run_id` | PK, `sync-…` / `branding-…` with UTC stamp + random suffix |
| `workflow` | Free text (`sync`, `branding`); deliberately unconstrained — the vocabulary belongs to the workflow layer |
| `started_at` / `finished_at` | UTC timestamps; `finished_at` set exactly once |
| `outcome` | `DO_NOT_PUBLISH` · `WORKFLOW_FAILED` · `REQUIRES_HUMAN_INTERVENTION`, or `NULL` while running |
| `failed_phase` | Phase that failed, or `NULL` on success |

Guarantees (CHECK constraints): the outcome vocabulary; `(outcome IS NULL) =
(finished_at IS NULL)` — a run has an outcome exactly when it has finished.
An unfinished (`NULL`) run is a real, detectable state: it is how an
interrupted run is found on the next invocation (`list_unfinished_runs`).
`finish_run` resolves only an unfinished run; resolving twice is refused.

### 3.2 `workflow_phases` — owned by Step 11 workflows

Every phase a run enters leaves one row (`record_phase`), success or
failure, in entry order.

| Column | Meaning |
|---|---|
| `phase_id` | PK, random |
| `run_id` | FK → `workflow_runs` |
| `phase` | `load_registry` · `synchronize` (sync) or `context` · `decide` · `publish` (branding) |
| `started_at` / `finished_at` | Entry/completion timestamps |
| `outcome` | `ok` · `failed` · `skipped` (CHECK) |
| `error` | Failure text, if any |

Guarantee: none beyond the vocabulary — this table is a trail, not a gate.
"What did this run do?" is answered by `list_phases(run_id)`, never by logs.
A failing run's terminal row for its `failed_phase` is `failed` (Step 11
correction); an append-only trail may hold an earlier `ok` row for the same
phase, in which case the latest row is the terminal statement.

### 3.3 `sync_checkpoints` — owned by Step 3 synchronization

Per source: how far synchronization has *successfully* processed.

| Column | Meaning |
|---|---|
| `source_name` | PK |
| `last_revision` / `last_synced_at` | Last successfully processed revision + time; both `NULL` until the first success |
| `last_attempt_at` / `last_outcome` | Most recent attempt (`SUCCEEDED` · `FAILED`) |
| `updated_at` | Row write time |

Guarantees: `(last_revision IS NULL) = (last_synced_at IS NULL)` — a source
that never synced has neither. The checkpoint advances **only after** the
pipeline reports success (`record_sync_success`); a failure records the
attempt (`record_sync_failure`) and leaves the revision where it was, so the
next run re-processes the same range over idempotent content hashes.

### 3.4 `source_lifecycle` — owned by Step 2 registry model

Per source: explicit lifecycle, never inferred.

| Column | Meaning |
|---|---|
| `source_name` | PK |
| `lifecycle` | `ACTIVE` · `PAUSED` · `COMPLETED` · `PLANNED` (CHECK) |
| `note` / `updated_at` | Operator note; write time |

Lifecycle affects sync depth/priority, never visibility: a `COMPLETED`
source still has deletions and new activity detected, and new activity
raises a status-review signal (`REQUIRES_HUMAN_INTERVENTION`) instead of
being ignored.

### 3.5 `publish_intents` — owned by Step 6 publishing service

The write-ahead intent: written **before** any LinkedIn request exists. With
no LinkedIn read-back, this row is the only duplicate protection that can
prevent a call rather than record one after the fact.

| Column | Meaning |
|---|---|
| `intent_id` | PK, random |
| `run_id` | FK → `workflow_runs` |
| `state` | `intent_created` · `attempt_started` · `published` · `failed` · `unknown_requires_review` (CHECK) |
| `content` / `content_hash` | Post text + its SHA-256 (duplicated nowhere else by design) |
| `topic` / `angle` / `project` | Labels recorded with the post |
| `created_at` / `updated_at` | Write times |

State machine: `intent_created → attempt_started →` one terminal state.
Terminal states: `published` (post id returned), `failed` (definitively no
post), `unknown_requires_review` (a post may exist — never retried, person
must confirm).

Guarantees: `ux_publish_intents_run` — at most one intent per run
(`MAX_PUBLISHES_PER_RUN = 1`, enforced by SQLite, not by workflow
discipline); `ux_publish_intents_unresolved_content` — at most one
*unresolved* intent per content hash across runs. A `failed` intent drops
out of the second index (a definitive non-send must not block the content
forever); `unknown_requires_review` deliberately stays in it.

### 3.6 `publications` + `publication_evidence` — owned by Step 6

The outcome, recorded from evidence, in the same transaction as the intent
resolution — the two can never disagree.

| Column (`publications`) | Meaning |
|---|---|
| `publication_id` | PK, random |
| `intent_id` | UNIQUE FK → `publish_intents` (at most one publication per intent) |
| `run_id` | FK → `workflow_runs` |
| `outcome` | `published` · `failed` · `unknown_requires_review` (CHECK) |
| `linkedin_post_id` | Present exactly when `published` (CHECK both directions) |
| `content_hash` | Copied from the intent for duplicate checks |
| `embedding` | Packed vector of the published text (Step 6 duplicate checks) |
| `recorded_at` | Write time |

`publication_evidence(publication_id, source_path, content_hash)` records
what the post was grounded in, PK on all three columns. The post *text* is
deliberately not copied here — it lives on the intent (1:1 join), so two
copies can never disagree.

### 3.7 `operational_failures` — written by every layer, owned by none

Structured error records. Never a log line, never swallowed.

| Column | Meaning |
|---|---|
| `failure_id` | PK, random |
| `run_id` / `workflow` | Linkage (nullable `run_id` for run-detached rows: lock events, interrupted-run reports) |
| `phase` | Which phase failed — free text, owned by the failing layer |
| `error_category` | Layer-owned vocabulary, deliberately unconstrained |
| `message` | Human-readable description (secrets redacted at composition) |
| `retryable` / `requires_human_intervention` | Booleans the notifier and operators branch on |
| `dedupe_key` / `occurrence_count` | Recurring identical failures accumulate on one row; `NULL` keys never conflict, so keyless rows are always distinct |
| `first_seen_at` / `last_seen_at` | Occurrence window |

Guarantee: `ux_failures_dedupe_key` — one row per dedupe key. The first
occurrence always creates the row, so deduplication quiets repetitions
without ever hiding a new problem.

### 3.8 `notifications` — owned by Step 7 notification service

One row per delivery *attempt*, deliberately separate from the failure it
reports: a delivery failure must never replace or erase the workflow
failure.

| Column | Meaning |
|---|---|
| `notification_id` | PK, random |
| `failure_id` / `run_id` | What is being reported (nullable) |
| `recipient` / `subject` / `transport` / `smtp_config` | Where/how; config recorded as `host:port tls=mode` only — no username, password, or body |
| `delivery_state` | `pending` · `sent` · `failed` (CHECK) |
| `error_message` | Categorized delivery failure, redacted |
| `created_at` / `attempted_at` / `delivered_at` | Timing; `delivered_at` present exactly when `sent` (CHECK) |

The message body is deliberately **not** stored. A `failed` delivery leaves
the original failure, its occurrence count, and the run outcome untouched,
and is never counted as having reported the failure — the next run tries
again. Only `sent` rows suppress repeats inside the quiet window
(`SMTP_REPEAT_AFTER_HOURS`, default 24h); publications skip suppression
entirely (a post is an event, not a recurring condition).

### 3.9 `locks` — owned by Step 1 store, used by the Step 12 guard

Overlap protection, one row per workflow.

| Column | Meaning |
|---|---|
| `lock_name` | PK (`workflow:sync`, `workflow:branding`) |
| `owner` | `hostname:pid:token` — identifiable invocation |
| `acquired_at` / `heartbeat_at` / `expires_at` | Lifetime; `expires_at >= acquired_at` (CHECK) |

Guarantee: one holder per lock (PRIMARY KEY) + atomic check-and-take in a
single transaction, so two racing invocations cannot both win. Expiry alone
never grants ownership to this system's guard: an expired-but-live owner is
refused (see `docs/operations/scheduling.md` §3 and Known Issue #16).

### 3.10 `linkedin_credential_expiry` — owned by Step 5 integration

A fact read from the credential, not a claim about anything published — the
*only* thing the integration layer writes.

| Column | Meaning |
|---|---|
| `credential` | PK (credential name) |
| `expires_at` / `issued_at` | Derived absolute expiry + issuance (nullable when underivable — reported unknown, never guessed) |
| `derived_from` | `id_token_iat` (authoritative) · `file_mtime` (fallback) — CHECK |
| `source_mtime` | mtime of the file the values came from; a changed mtime means re-derive |
| `recorded_at` / `updated_at` | Write times |

Guarantee: `expires_at >= issued_at OR issued_at IS NULL` — a derivation
that contradicts itself is refused rather than stored.

### 3.11 `schema_version` — the ledger

`(version, description, applied_at)`; one row per applied migration,
ascending and contiguous. Gaps or unknown versions refuse to operate.

## 4. Ownership summary

| State | Owner | Readers |
|---|---|---|
| `workflow_runs`, `workflow_phases` | Step 11 workflows | Step 12 guard (unfinished runs), Step 7 notifier, evaluation |
| `sync_checkpoints`, `source_lifecycle` | Step 3 sync / Step 2 model | Step 4 freshness, operators |
| `publish_intents`, `publications`, `publication_evidence` | Step 6 service | Step 6 read service (Agent history), Step 11 guard |
| `operational_failures` | Failing layer | Step 7 notifier, Step 12 guard, operators |
| `notifications` | Step 7 service | Operators, noise control |
| `locks` | Step 1 store, Step 12 guard | Guard only |
| `linkedin_credential_expiry` | Step 5 integration | Step 5 client, operators |

No component writes outside its rows. In particular: the Agent writes
nothing; the integration writes only credential expiry; generated post text
never enters any knowledge store.

## 5. Related

| Document | Role |
|---|---|
| [`recovery.md`](recovery.md) | Procedures that read and act on this state |
| [`scheduling.md`](scheduling.md) | Lock lifecycle and the overlap guard |
| [`publishing.md`](publishing.md) | Publishing and credential lifecycles |
| [`../evaluation/autonomous-evaluation.md`](../evaluation/autonomous-evaluation.md) | Suite that asserts against this state |
