# Phase 10 — Observability & Operational Memory

Where the system remembers what it did, and why that memory lives apart
from everything it knows. This document describes the design as built
(Steps 1, 7, 11, 12); the schema itself is specified in
[`../operations/state-model.md`](../operations/state-model.md).

---

## 1. Two memories, two authorities

| | Knowledge memory | Operational memory |
|---|---|---|
| Answers | What is known about the user | What the system has done |
| Lives in | `data/` Markdown → Chroma | SQLite (`state_db/`, gitignored, not rebuildable) |
| Authority | The corpus | The store (local publication history is authoritative — LinkedIn grants no read-back) |
| Written by | Ingestion pipeline, via sync | Workflows, publishing service, notifier, scheduler guard |

The rule is absolute in both directions: no operational record enters the
Chroma collection (a generated post must never become "evidence" for the
next one), and no knowledge about the user lives in SQLite beyond the
provenance references a publication cites.

## 2. What operational memory records

- **Runs**: every workflow execution, from start to exactly one of the three
  recorded outcomes — including runs that publish nothing and runs that
  never finish (an unfinished run is how an interrupted run is found).
- **Phase trails**: every phase each run entered, with its outcome — the
  queryable answer to "what did this run do", independent of log retention.
- **Failures**: structured rows (phase, category, retryability,
  human-intervention flag), occurrence-counted per dedupe key so recurrence
  is visible without flooding.
- **Notifications**: delivery attempts as rows separate from the failures
  they report, so a dead mailbox can never rewrite history.
- **Locks**: one row per workflow, the overlap guard the scheduler path
  takes before every run.
- **Checkpoints, lifecycles, intents, publications, credential expiry**:
  how far sync got, what each source is, what was about to be sent, what
  was sent, and when the credential dies.

## 3. How it is observed

Nothing here requires a dashboard. The store is queried directly
(procedures in [`../operations/recovery.md`](../operations/recovery.md)):
unfinished runs, recent runs with outcomes, phase trails, per-run failures,
pending ambiguities, delivery states, lock owners, checkpoints. Logs
(`logs/`) narrate; the store decides. Any disagreement between the two is
resolved in favor of the store.

## 4. Related

| Document | Role |
|---|---|
| [`../operations/state-model.md`](../operations/state-model.md) | Tables, constraints, guarantees, owners |
| [`../operations/recovery.md`](../operations/recovery.md) | Reading this memory under pressure |
| [`../architecture/data-flow.md`](../architecture/data-flow.md) | Audit trail in the end-to-end flow |
