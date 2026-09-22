# Recovery Procedures

What to do when the unattended system stops being unattended (`PLAN.md`
Step 14). Every procedure below matches the actual state machine — what the
system recovers by itself, what it reports, and where a person is genuinely
required. The governing rule (`PLAN.md` §11): **when in doubt, the system
does less (publishes nothing) and reports more.**

All read-only inspection uses the production store. Write operations are
marked as such; anything unmarked is safe to run any time.

```bash
cd <PROJECT_ROOT>
DB="state_db/operational_state.db"
```

Manual intervention boundaries (`PLAN.md` §11) are restated per procedure:
`REQUIRES_HUMAN_INTERVENTION` means stop, persist, notify, never retry;
`WORKFLOW_FAILED` means persist, notify, exit non-zero, next tick retries.

---

## 1. Interrupted workflow

**Detect** — runs with no outcome are interrupted runs, found by query:

```bash
.venv/bin/python -c "
from app.state import StateStore
with StateStore() as s:
    for r in s.list_unfinished_runs():
        phases = [p.phase for p in s.list_phases(r.run_id)]
        print(r.run_id, r.workflow, r.started_at, phases)"
```

**What happens automatically.** The next scheduled invocation of the same
workflow reports each unfinished run (one occurrence-counted
`interrupted_run` row, no `run_id`) and proceeds with a fresh run. The old
run is left unfinished for forensics — it is never finished, failed, or
retried by recovery, so an interruption can never become a false success.

**Operator action:** usually none. If the interruption repeats every tick,
read its phase trail (`list_phases`) and failure rows — the trail shows how
far it got — and treat it as the underlying failure it is (procedures 6–7).
Never mark an unfinished run finished by hand: an outcome nobody observed
would be indistinguishable from a real one in every later audit.

## 2. Stale lock

**Detect** — a lock row whose `expires_at` is past, or repeated `lock_held`
rejections for a workflow that has no live process:

```bash
.venv/bin/python -c "
from app.state import StateStore
with StateStore() as s:
    for name in ('workflow:sync', 'workflow:branding'):
        lock = s.get_lock(name)
        print(name, lock.owner, lock.expires_at if lock else 'FREE')"
```

**What happens automatically.** The next invocation reclaims an expired lock
**only after** its owner process is shown to be gone; a live owner is
refused, never overridden. Recovery is recorded (`stale_lock_recovered`)
and logged. This covers `SIGKILL`, power loss, and store failures
mid-run — no operator step needed.

**Operator action (genuinely required only for pid reuse).** If ticks keep
being rejected while no workflow process exists, check whether the recorded
owner pid belongs to an unrelated live process (`ps -p <pid>`). If it does
— and only then — delete that workflow's `locks` row; the next tick takes
it fresh:

```bash
.venv/bin/python -c "
from app.state import StateStore
with StateStore() as s:
    import sqlite3
    conn = sqlite3.connect(str(s.path))
    conn.execute(\"DELETE FROM locks WHERE lock_name = 'workflow:branding'\")
    conn.commit()"
```

Never delete a lock held by a live workflow process — that is how two live
owners happen. See Known Issue #16.

## 3. Unresolved / ambiguous publication

**Detect:**

```bash
.venv/bin/python -c "
from app.state import StateStore
from app.state.enums import PublishState
with StateStore() as s:
    for p in s.list_publications(limit=20):
        if p.outcome is PublishState.UNKNOWN_REQUIRES_REVIEW:
            print(p.publication_id, p.run_id, p.recorded_at)"
```

**What happens automatically: nothing further.** This is deliberate. A post
may exist on LinkedIn and there is no read-back, so no automatic step can
resolve it. Every later branding run refuses to publish over the ambiguity
and escalates instead — publishing halts rather than risks a duplicate.

**Operator action (all manual):**

1. Open LinkedIn and confirm whether the post exists.
2. If it exists: treat the content as published. Do not re-run publishing
   for that content — the unresolved-intent index already blocks it.
3. If it does not exist: the words are safe for a later run only after the
   ambiguity record is addressed (see limitation below).

**Known limitation (no automatic recovery exists).** There is no operator
resolution API: an `unknown_requires_review` row keeps the pre-publish guard
engaged permanently, so publishing stays halted until such a path is built
(a future-work item, not a silent retry). Do not edit the row by hand to
unblock publishing — that would destroy the exact record the guard exists
to protect. Recorded as a Known Issue in `implementation-status.md`.

## 4. Failed notification

**Detect** — `failed` delivery rows, separate from the failures they carry:

```bash
.venv/bin/python -c "
from app.state import StateStore
from app.state.enums import DeliveryState
with StateStore() as s:
    for n in s.list_notifications(delivery_state=DeliveryState.FAILED,
                                  limit=20):
        print(n.created_at, n.run_id, n.error_message)"
```

**What happens automatically.** The original workflow failure, its
occurrence count, and the run outcome are untouched by a delivery failure,
and a `failed` delivery never counts as having reported the failure — the
next run tries again. If the cause was transient (mail server down), nothing
needs doing.

**Operator action:** fix the cause, not the row. Missing settings raise
`ConfigError` naming the variable; `authentication` means the app password;
`transport` means the network or mail server. Verify with the SMTP
variables in `.env` (see `deployment.md` §3), then wait for the next tick —
do not re-send by hand; the pending failure will notify on its own.

## 5. Expired LinkedIn credential

**Detect** — the run outcome says so (`REQUIRES_HUMAN_INTERVENTION`,
`publish` phase, expiry message), or proactively:

```bash
.venv/bin/python -c "
from app.state import StateStore
with StateStore() as s:
    for c in s.list_credential_expiries():
        print(c.credential, c.expires_at, c.derived_from)"
```

An `EXPIRING_SOON` credential still publishes and carries a warning; an
expired one fails closed before any request, with no retry.

**Operator action (the only fix):** re-authorize by hand —
`Auth_handling/linkedin_oauth_setup.py` — then confirm with
`Auth_handling/test_credentials.py` (no posting). No code change, no config
change, and never an automatic refresh: refresh was never verified for this
application and is not assumed. See `manual-linkedin.md` in
`docs/evaluation/`.

## 6. Failed scheduled workflow

**Detect** — cron output in `logs/*-cron.log` plus the non-zero exit status;
then the recorded failure:

```bash
.venv/bin/python -c "
from app.state import StateStore
with StateStore() as s:
    for r in s.list_runs(limit=5):
        print(r.run_id, r.workflow, r.outcome, r.failed_phase)"
```

**Operator action:** match `failed_phase` + `error_category` to the cause.
Transient infrastructure (`llm_unavailable`, `transport`,
`ingestion_failure`) needs nothing — the next tick retries the same range
over idempotent state. Configuration and auth failures need a person
(procedures 4–5). `failed_phase` tells you which layer to look at; the phase
trail (`list_phases`) tells you how far the run got.

## 7. Partial sync failure

**Detect** — the run fails (or escalates) naming `synchronize`, while other
sources_sync normally; per-source rows carry the category:

- transient (`git_failure`, `ingestion_failure`, `content_unreadable`):
  checkpoint left behind; next run re-processes the same range. No action.
- `source_unavailable` (missing path / not a repo) or `guard_refused`:
  `REQUIRES_HUMAN_INTERVENTION`. Fix the registry (`sources.yaml`) or
  restore the source. `COMPLETED` sources with new activity surface as
  review signals — review the activity, update lifecycle/notes, do not
  ignore it.

## 8. Quick reference

| Symptom | First query | Usually |
|---|---|---|
| Ticks rejected, no process running | `get_lock` + `ps -p` | crash residue → auto-recovers; pid reuse → procedure 2 |
| Run never finished | `list_unfinished_runs` | reported next tick; investigate trail |
| `unknown_requires_review` row | `list_publications` | procedure 3 (manual, halts publishing) |
| `failed` delivery row | `list_notifications` | fix mail cause, wait a tick |
| Auth/expired message | `list_credential_expiries` | re-authorize by hand |
| `synchronize` failed, others fine | per-source failure rows | transient → nothing; missing/guarded → registry |
| Exit `3` from cron | lock rejection row | overlap, working as designed |

## 9. Related

| Document | Role |
|---|---|
| [`state-model.md`](state-model.md) | The tables these procedures read |
| [`scheduling.md`](scheduling.md) | Lock lifecycle, exit codes, manual runs |
| [`deployment.md`](deployment.md) | Reproduction and installation |
| [`../evaluation/manual-linkedin.md`](../evaluation/manual-linkedin.md) | Explicit real-LinkedIn path |
| `PLAN.md` §11 | Manual intervention boundaries (authoritative) |
