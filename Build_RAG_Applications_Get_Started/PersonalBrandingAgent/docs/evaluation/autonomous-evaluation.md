# Autonomous Evaluation

Workflow-level evaluation for the unattended system (`PLAN.md` §8, Step 13).
Unit tests prove components; this suite proves the *system* behaves correctly
when things go wrong — the common case for an unattended process.

---

## 1. How to run

```bash
cd <PROJECT_ROOT>
PYTHONNOUSERSITE=1 .venv/bin/python -m pytest tests/test_autonomous_evaluation.py -q
```

Everything runs offline with fakes and isolated temporary state: a temporary
SQLite store, a temporary Chroma collection with deterministic fake
embeddings, throwaway git repositories, a scripted reasoner/LLM/judge, a fake
LinkedIn transport (or a fake HTTP layer under the real
`publish_to_linkedin`, so the genuine Step 5 classification runs), and a fake
email transport. A socket-blocking fixture fails any test that attempts a
real network call. The production database is never touched.

The milestone test runs the full 18-scenario set twice from clean state and
asserts identical outcome vectors — reproducibility is asserted, not assumed.

## 2. Scenario catalogue

Each scenario drives a real workflow boundary and asserts its **recorded**
outcome and persistent state.

| # | Scenario | Recorded outcome | What the state proves |
|---|---|---|---|
| 1 | no-change sync | `DO_NOT_PUBLISH` | second pass writes nothing; checkpoint steady |
| 2 | changed Git source | `DO_NOT_PUBLISH` | new content ingested; checkpoint == HEAD |
| 3 | completed project with new commit | `REQUIRES_HUMAN_INTERVENTION` | review signaled **and** the content still ingested |
| 4 | deleted file | `DO_NOT_PUBLISH` | vectors purged; survivor kept; checkpoint advanced |
| 5 | normal publication | `DO_NOT_PUBLISH` | one intent, one `published` publication with post id + evidence refs; exactly one LinkedIn call; one publication email, zero failure emails |
| 6 | no publication opportunity | `DO_NOT_PUBLISH` | zero LinkedIn calls, zero emails, zero publications |
| 7 | duplicate candidate | `DO_NOT_PUBLISH` | refusal before any request; publication count stays 1 |
| 8 | weak evidence | `DO_NOT_PUBLISH` (`gate_rejected`) | learning-state evidence cannot carry a mastery claim |
| 9 | generation failure | `WORKFLOW_FAILED` (`decide`, `llm_unavailable`) | nothing published; exactly one notification |
| 10 | verification failure | `WORKFLOW_FAILED` (`decide`) | crashing judge fails the gate closed; nothing published |
| 11 | LinkedIn timeout | `REQUIRES_HUMAN_INTERVENTION` (`publish`) | read timeout recorded `unknown_requires_review`; exactly one HTTP attempt |
| 12 | ambiguous publication | `REQUIRES_HUMAN_INTERVENTION` ×2 | one external attempt total; second run blocked by the guard with no `publish` work |
| 13 | token expired | `REQUIRES_HUMAN_INTERVENTION` (`publish`) | zero HTTP calls; `failed` publication; expiry message recorded |
| 14 | notification delivery failure | `WORKFLOW_FAILED` | run outcome intact; delivery recorded `failed` separately |
| 15 | duplicate scheduled invocation | lockout + `DO_NOT_PUBLISH` | exactly one run; one counted rejection; lockout exits `3` |
| 16 | recovery after interrupted run | `DO_NOT_PUBLISH` (fresh run) | stale lock reclaimed and recorded; old run stays unfinished; stranded intent untouched |
| 17 | self-ingestion attempt | `REQUIRES_HUMAN_INTERVENTION` | application directory refused; collection stays empty |
| 18 | unregistered source path missing | `REQUIRES_HUMAN_INTERVENTION` | missing path reported, never skipped |

Expected outcomes live in the suite as `EXPECTED_OUTCOMES`; the milestone
asserts the full vector, twice.

## 3. Reading a result

- A scenario failure names a *recorded* fact that disagrees (outcome, phase
  trail, intent/publication row, notification row, fake call count) — never a
  log line. Start from the assertion: it points at the contract that moved.
- `unknown_requires_review` rows are questions, not failures. They clear only
  by a person confirming the post, never by re-running.
- The evaluation never invents policy: every expected outcome follows the
  Step 6–12 contracts. If a scenario expectation ever stops matching the
  code, determine first whether the contract moved — do not weaken the test.

## 4. Related

| Document | Role |
|---|---|
| [`manual-linkedin.md`](manual-linkedin.md) | The deliberate real-LinkedIn path (explicit, never automated) |
| [`../retrieval/`](../retrieval/) | Retrieval-level evaluation (gold set, Hit@K, MRR) |
| [`../operations/scheduling.md`](../operations/scheduling.md) | How the evaluated entry points run unattended |
