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
    Step 13 — End-to-End Autonomous Evaluation

Status:
    NOT STARTED

Overall Progress:
    Steps 0–12 COMPLETED. The environment is reproducible, the operational state
    store exists, the source registry defines exactly which directories are
    evidence about the user, synchronization is incremental, the context layer
    turns a retrieval result into named, ranked, provenance-preserving sections,
    LinkedIn publishing is a service an unattended workflow can call, every
    publish leaves a durable trace — a write-ahead intent written before any
    request exists, an outcome recorded from evidence, three duplicate checks
    over stored history, and a recovery path that turns an interruption into an
    explicit ambiguity instead of a silent retry — a failure can reach a person
    through an SMTP notification composed from the recorded outcome, generation
    turns an assembled context into a candidate post with the labels it used and
    the model and prompt version that produced it, and verification now decides
    whether that post is true: a draft is split into numbered claims, each claim
    is checked against the evidence the draft cited and nothing else, the exact
    numbers and dates in it are matched as strings against that evidence, the
    five inferences `data/audit/README.md` forbids are enforced as rules, a
    semantic judgement is available but advisory and is consulted only after the
    deterministic checks pass, and the result is a typed structure that cannot
    be constructed as a pass while carrying a finding. Above that gate now sits
    the one bounded Agent: it chooses a topic from the context's own non-empty
    evidence sections, names the evidence by label from the list it was shown
    and from nothing else, proposes an angle, a project and — for a fresh pass —
    a retrieval strategy, drives Step 9's revision loop under Step 9's own
    stopping rule, and returns a decision. `PUBLISH` is unconstructible without
    a passing verification behind it; `DO_NOT_PUBLISH` carries a reason and is a
    success. Reasoning failure is a `DO_NOT_PUBLISH` carrying the failure for
    the workflow to notify, never a weaker post. The Agent writes nothing,
    publishes nothing, notifies no one, and has no import path to a store, a
    publisher, a transport or the corpus. And now something runs all of it:
    two separate, separately executable workflows (`python -m
    app.workflows.sync`, `python -m app.workflows.branding`) sequence the
    existing layers, record every phase transition and the final outcome on a
    workflow run, classify the outcome themselves, and notify exactly once on
    failure — with an ambiguous publication escalated to a person and never
    retried. And now something runs all of it on a schedule: the Step 11 entry
    points execute under a per-workflow overlap guard backed by the Step 1
    `locks` table — a second invocation while locked is rejected without
    running and exits `3` — a stale lock is reclaimed only after its owner
    process is shown to be gone (never on timeout alone), and unfinished runs
    are reported and left untouched. The trigger itself is cron
    (`ops/personal-branding-agent.cron`, branding every 8h, sync daily),
    which passes exit statuses straight through. Nothing in this step runs
    long-lived: Steps 13–14 have not been started.

Last Completed Step:
    Step 12 — Add External Scheduling, Locks & Recovery

Next Step:
    Step 13 — End-to-End Autonomous Evaluation
```

The roadmap was rewritten and finalized after an architecture and readiness
analysis of the repository. Steps 0–12 have since been implemented, verified,
and committed; Step 13 onwards remains untouched.

```text
Sources registered:  29          (8 ACTIVE · 20 COMPLETED · 1 PLANNED)
Declared roots:       9          (inspected, never ingested)
Not registered:      10          (with the evidence behind each decision)
Sources synchronized: 0          (the mechanism exists, and the Step 11 entry
                                   point now owns running it; no real source has
                                   been run through it yet — see Known Issue #7)
```

---

## Step Progress

Status vocabulary: `NOT STARTED` · `IN PROGRESS` · `BLOCKED` · `COMPLETED`

| Step | Name | Status |
|---|---|---|
| 0 | Restore a Reproducible, Testable Environment | COMPLETED |
| 1 | Introduce Persistent Operational State (SQLite) | COMPLETED |
| 2 | Define the Personal Knowledge Source Registry & Project Lifecycle | COMPLETED |
| 3 | Build Incremental Knowledge Synchronization | COMPLETED |
| 4 | Build the Personal Branding Context & Evidence Layer | COMPLETED |
| 5 | Harden the LinkedIn Integration for Autonomous Use | COMPLETED |
| 6 | Build Persistent Publishing, Idempotency & Recovery | COMPLETED |
| 7 | Build Operational Failure Notifications via Email | COMPLETED |
| 8 | Build Grounded Post Generation | COMPLETED |
| 9 | Build Evidence Verification & Revision Gates | COMPLETED |
| 10 | Build the Autonomous Branding Agent | COMPLETED |
| 11 | Build the 24h Knowledge-Sync and 8h Branding Workflows | COMPLETED |
| 12 | Add External Scheduling, Locks & Recovery | COMPLETED |
| 13 | End-to-End Autonomous Evaluation | NOT STARTED |
| 14 | Operational Documentation, Deployment & Final Hardening | NOT STARTED |

> Step names above are taken verbatim from `PLAN.md` §8. If a step is renamed
> there, rename it here too.

---

## Completed Steps

### Step 12 — Add External Scheduling, Locks & Recovery

Status: COMPLETED

Implemented:
- Created `app/workflows/scheduled.py` — the scheduled-invocation guard behind
  one public surface: `workflow_lock` (context manager), `acquire_workflow_lock`
  / `release_workflow_lock`, `try_acquire`, `WorkflowLocked`, `EXIT_LOCKED=3`,
  plus the `lock:` / `recovery:` phase vocabulary for guard rows.
- **Overlap protection with no scheduler involved.** `run_sync()` and
  `run_branding()` now execute under their per-workflow lock
  (`workflow:sync`, `workflow:branding`) from the Step 1 `locks` table. A
  second invocation while held records the rejection (one occurrence-counted
  row, no `run_id`, so it never leaks into a run notification), never enters
  the workflow, and raises `WorkflowLocked`, which the entry points convert to
  exit `3` — distinct from the Step 11 `0/1/2`, which are preserved untouched.
- **Stale recovery gated on liveness, never on timeout alone.** Owners are
  `hostname:pid:token`; an expired lock whose pid is still alive on this host
  is treated as held and refused, so an overrunning run can never gain a
  concurrent twin. Only an expired lock with a demonstrably dead owner is
  reclaimed, through the atomic Step 1 transaction — so two simultaneous
  recoveries cannot both win — and every recovery is recorded and logged. An
  unparseable owner is refused fail-closed. `LOCK_TTL_SECONDS` (6h) sits below
  the shortest schedule interval (8h), so a crashed holder is always
  reclaim-eligible by the next tick.
- **Interrupted runs reported, never resolved.** After acquiring, unfinished
  runs of the same workflow are reported (one occurrence-counted row each,
  left `NULL`, publish state untouched — no blind retry of an ambiguity) and
  the fresh run proceeds. An unfinished run seen while locked is the live
  holder's own run, so it is not reported.
- **Scheduler: cron.** `ops/personal-branding-agent.cron` triggers branding
  every 8h and sync daily at 02:10 via the Step 11 entry points, passing exit
  statuses straight through with no masking constructs. Chosen over a systemd
  timer: one file, no daemon-reload/lingering, no systemd-init dependency for
  fixed coarse intervals. Documented in `docs/operations/scheduling.md`
  (choice, install, exit codes, manual operation, lock clearing).
- **No long-running Python process.** Verified by scan: no loops, sleeps,
  threads, queues, or workers in `app/workflows/` — one shot per invocation.

Verified:
- 15 focused tests (`tests/test_scheduling.py`), offline with fakes and
  isolated temp state: rejection while locked (workflow never entered,
  single counted row, no run created); exit mapping `0/1/2` passthrough plus
  locked→`3`; stale recovery with the old owner named and the lock released;
  stale-but-live and unidentifiable owners refused with the lock untouched;
  two racing stale recoveries yield exactly one winner; pid probe against a
  reaped child; interrupted runs reported once across ticks, left unfinished,
  publish intent untouched; live holder's unfinished run not reported;
  guarded branding end to end; cron file invokes both modules unmasked.
- **Milestone:** two immediate invocations under contention produce exactly
  one workflow run and one recorded rejection.
- Full regression: 951 passed (936 before Step 12; the 15 new tests are the
  whole difference, and nothing existing changed its result — all 29 Step 11
  tests pass unmodified with the guard wired in).

Files: `app/workflows/scheduled.py`,
`app/workflows/{sync,branding,__init__}.py` (guard wiring + locked-exit
mapping only), `ops/personal-branding-agent.cron`,
`docs/operations/scheduling.md`, `tests/test_scheduling.py`,
`docs/implementation-status.md`.

Not implemented, deliberately: end-to-end evaluation (Step 13), deployment
(Step 14). The first real scheduled tick is still ahead (Known Issues #5,
#7, #9, #11 stand). New residual, recorded as Known Issue #16: pid reuse can
make a dead owner's lock look live, causing repeated refusals — a missed run,
never an overlap; self-heals when the pid dies.

### Step 11 — Build the 24h Knowledge-Sync and 8h Branding Workflows

Status: COMPLETED

Implemented:
- Created `app/workflows/` — four modules behind one public surface
  (`__init__.py`): `common.py` (the exit-code vocabulary `0` / `1` / `2`, the
  structured `WorkflowResult`, the `HumanIntervention` escalation, the one
  exception classifier, the phase wrapper, and the finish-and-notify-once
  helper), `sync.py` (`run_sync`, `SyncConfig`, `main`), `branding.py`
  (`run_branding`, `BrandingConfig`, `main`).
- **Two independently executable entry points.** `python -m
  app.workflows.sync` and `python -m app.workflows.branding` each run once and
  exit with the outcome's code. No scheduler, no queue, no worker, no graph
  runtime — Step 12 owns scheduling.
- **The workflow decides sequencing; the Agent decides content.** The branding
  workflow branches on the `AgentResult` value (`failed`, `is_publishable`,
  reason, draft, proposal) and never re-derives it. Generation and
  verification run inside the Agent under Step 9's stopping rule; the workflow
  passes the Agent's collaborators in and reads the result out.
- **Every phase boundary identifies its phase.** `run_phase()` records each
  transition in the new `workflow_phases` table (migration 4, with
  `StateStore.record_phase()` / `list_phases()`), and a failure additionally
  leaves an `operational_failures` row carrying the phase name plus the run's
  `failed_phase`. Sync phases: `load_registry`, `synchronize`. Branding
  phases: `context`, `decide`, `publish`.
- **Correction (review follow-up): logical failures persist their phase as
  failed.** Branches where a returned value — not an exception — means failure
  (failed sources, review signals, reasoning failures, the unresolved-ambiguity
  guard, ambiguous/failed publish reports) now call the shared
  `record_phase_failure()` before `finish()`, so the phase's terminal trail row
  is `failed` and agrees with the run outcome. Previously the trail held only
  the `ok` row `run_phase()` had written on normal return. Outcomes, exit
  codes, `failed_phase` values, and notify-exactly-once behavior are unchanged.
- **All three outcomes are recorded, never inferred.** `finish()` writes the
  outcome to `workflow_runs` and returns it in the `WorkflowResult` with its
  exit code: `DO_NOT_PUBLISH → 0`, `WORKFLOW_FAILED → 1`,
  `REQUIRES_HUMAN_INTERVENTION → 2`. The two nonzero codes are distinct so a
  scheduler can tell "it broke" from "it needs you."
- **`DO_NOT_PUBLISH` is a success with no failure notification.** A clean
  sync, an Agent decline (`NO_EVIDENCE`, `NO_VALUE`, `GENERATION_DECLINED`,
  `GATE_REJECTED`, `REVISION_EXHAUSTED`), a duplicate refusal, and a
  successful publish all terminate this way; the notifier is not even called
  for a failure report. A published post is reported once as a *publication*
  (`notify_publication`) — the one channel Step 7 built that the failure path
  cannot cover.
- **Reasoning failure is a workflow failure, not a decision.** An `AgentResult`
  carrying an `AgentFailure` ends the run as `WORKFLOW_FAILED` on phase
  `decide` with exactly one notification. `GenerationError` /
  `VerificationError` / `AgentError` propagate out of the Agent by design and
  are attributed to the phase they escaped from; a configuration failure
  (`requires_human_intervention`) escalates to a person instead.
- **An ambiguous publication is never retried.** An `unknown_requires_review`
  report, an authentication-classified result, or an unresolved earlier
  attempt (`PublishingHistory.requires_review()` non-empty — checked *before*
  any request leaves the machine) ends the run as
  `REQUIRES_HUMAN_INTERVENTION` with exactly one notification. The publish
  phase is entered at most once per run, so `0 or 1` posts holds by shape,
  backed by the Step 6 database constraint.
- **Sync never publishes; branding never ingests.** `sync.py` has no import
  path to publishing, agent, generation, or verification; `branding.py` has no
  import path to sync, ingestion, or the source registry. Asserted by
  structural scans of each module's own source, mirroring the Step 9/10
  precedent. `app/agent/` remains free of any notify import: the Agent
  exposes the failure, the workflow decides to notify.
- **Persistence is additive.** Migration 4 adds only the `workflow_phases`
  table; no Step 1 table, constraint, or existing method changed behaviour.

Verified:
- 23 focused tests (`tests/test_workflows.py`), all offline with fakes and a
  real temporary store: sync and branding complete; failure in each of the
  five phases names that phase; exit codes `0`/`1`/`2`; the structural
  boundary scans; no-opportunity success with zero notifications; human
  intervention distinct with exactly one notification (ambiguous publication,
  unresolved earlier attempt, source needing a person); workflow failure
  distinct with exactly one notification (failed source, reasoning failure,
  failed publication); persisted outcomes never inferred from exit codes;
  every phase transition recorded in order; both entry points independently
  invocable with exit-code passthrough.
- **Milestone:** sync then branding back-to-back on one store, run twice with
  deterministic fakes — four runs, all `DO_NOT_PUBLISH`, with the expected
  phase trails.
- Full regression: 930 passed (907 before Step 11; the 23 new tests are the
  whole difference, and nothing existing changed its result).

Files: `app/workflows/{__init__,common,sync,branding}.py`,
`app/state/{schema,models,store,__init__}.py` (migration 4 + phase recording
only), `tests/test_workflows.py`, `docs/implementation-status.md`.

Not implemented, deliberately: scheduling, locks and recovery (Step 12),
end-to-end evaluation (Step 13), deployment (Step 14). No real source has been
synchronized yet (Known Issue #7), no real post has been published through the
service (Known Issue #9), and the first real branding run will still report a
configuration failure on the known key mismatch (Known Issue #5) — correctly,
as `REQUIRES_HUMAN_INTERVENTION`. Nothing in Steps 0–10 changed behaviour.

### Step 10 — Build the Autonomous Branding Agent

Status: COMPLETED

Implemented:
- Created `app/agent/` — nine modules behind one public surface (`__init__.py`):
  `enums.py` (the decision, its reasons, the failure categories, and the
  `FAILURE_REASONS` set), `errors.py` (`AgentError` and its three subclasses),
  `models.py` (frozen value objects), `prompt.py` (deterministic prompt assembly
  and the answer parser), `reasoning.py` (the reasoning protocol), `llm.py`
  (`LlmContentReasoner`), `history.py` (the read-only history boundary),
  `agent.py` (`BrandingAgent`, the one entry point).
- **Exactly one agent, and no framework.** `BrandingAgent` is the only agent in
  the package; there is no planner/critic pair, no sub-agent, no graph
  framework, no MCP, and no second turn anywhere. `ContentReasoner.reason()` is
  asked **once per run** and there is no mechanism by which it could be asked
  twice — the bounded part of a run is the revision loop *below* the decision,
  over drafts. A test computes the set of agent classes in the package and
  asserts it has exactly one member.
- **`DO_NOT_PUBLISH` is a first-class success and is reachable from every
  branch.** It is `AgentDecision.DO_NOT_PUBLISH`, it always carries a
  `NoPublishReason`, and the reasons that are *failures* are a separate,
  explicitly enumerated set (`FAILURE_REASONS` = `{REASONING_FAILED,
  INVALID_PROPOSAL}`) — so "we decided not to" and "reasoning broke" can never
  be confused for one another. Six non-failure routes reach it: `NO_EVIDENCE`
  (decided before the model is asked), `NO_VALUE` (the reasoner declined),
  `GENERATION_DECLINED` (the writer declined), `GATE_REJECTED` (Step 9 refused
  the draft) and `REVISION_EXHAUSTED` (the budget ran out). An
  `AgentResult.__post_init__` invariant makes a `DO_NOT_PUBLISH` with no reason
  unconstructible — an outcome with no reason is indistinguishable from a bug.
- **Evidence selection is confined to what retrieval returned, structurally.**
  `evidence_options(context)` numbers the context's *own* `evidence_items()` as
  `E1…En`, and `_proposal_from()` resolves the reasoner's labels against exactly
  that list. A label that does not resolve is `EvidenceSelectionError` —
  **refused, never dropped** — and the answer is built from the context's own
  items in the **context's** order (the same rule
  `app.generation.prompt.selected_evidence` applies), so a repeated label is one
  item and the prompt's labels do not depend on the order the model listed them
  in. There is nowhere for an invented source, chunk id, or label to be stored:
  `ReasoningAnswer` holds labels and nothing resolved, and a test asserts its
  exact field set. The reasoner is offered no corpus handle, and the import scan
  proves it has no path to one.
- **The Agent cannot write state, and publishing history is read through the
  Step 6 read service.** There is no store handle, session, publisher, notifier,
  transport or clock anywhere in the package, and no import path to any of them
  — asserted by parsing every module in `app/agent/` and failing on `sqlite3`,
  `chroma`, `app.state`, `app.publishing.service`,
  `app.publishing.duplicates`, `app.notify`, `app.sync`, `app.retrieval`,
  `app.ingestion`, `app.integrations` or `app.sources`. The positive half is
  asserted too: every `app.*` import in the package is on an explicit allow-list,
  so a new one is a deliberate act. A second test greps the source for write
  verbs (`create_publish_intent`, `record_publication`, `start_run`, `insert`,
  `execute(`, `commit(`) so a write added later fails a test rather than needing
  one to notice.
- **The history boundary is a narrow read protocol, satisfied by the real
  service.** `PublicationHistoryReader` declares five read methods
  (`recent_publications`, `requires_review`, `recent_topics`,
  `recent_projects`, `recent_evidence`) and `PublishingHistory` satisfies it
  structurally, with no import of `app.publishing`'s service module. The digest
  is read **once per run** (`run()` reads it, then passes it down) so the
  history a proposal was reasoned from and the history its writing constraints
  came from are the same value by construction rather than by two queries that
  happened to agree. `history=None` yields `HistoryDigest.empty()` — a first
  run, never an error, and never a reason to refuse the first post.
- **`PUBLISH` is unconstructible without a passing verification.**
  `AgentResult.__post_init__` refuses a `PUBLISH` with no `verification`, with a
  verification that is not publishable, with no proposal, or carrying a
  no-publish reason or a failure. Not "should not" — cannot. So the one lie an
  agent could tell, reporting a publication the gate never granted, is a
  `ValueError` at construction rather than a post.
- **The gates stay authoritative and are not duplicated.** Step 8's
  `PostGenerator.generate()` and Step 9's `EvidenceVerifier.verify()` are called
  **as-is**; not one of their checks is restated, relaxed or reimplemented. The
  loop's bound is `revision_decision(result, attempts_made,
  limit=self._revision_limit)` — Step 9's function, which the Agent calls rather
  than redefines — so `REVISE` is returned only while the budget is unspent and
  the loop runs at most `revision_limit + 1` times whatever the model does. A
  `REVISE` re-drives the generator with Step 9's own `revision_notes()` as
  writing constraints, which is what makes the second attempt a bounded
  operation rather than a guess. An explicit guard raises `AgentError` if the
  loop outran its bound, because a stopping rule that stopped being one is not a
  decision.
- **Bounded reasoning terminates with a structured result.** Every path through
  `run()` returns exactly one `AgentResult` — no unbounded retry, no open-ended
  autonomy, no path that loops without a spent budget. `GenerationError` and
  `VerificationError` are deliberately **not** caught: a phase that failed is
  the workflow's to record and Step 7's to notify, and collapsing it into
  `DO_NOT_PUBLISH` would report a broken run as a decision.
- **Reasoning failure is a `DO_NOT_PUBLISH`, never a weaker post.**
  `PLAN.md` Step 10's Failure/recovery is implemented literally: every reasoning
  failure — an unreachable model, an answer that is not the required shape, an
  evidence identifier that does not resolve — becomes a `DO_NOT_PUBLISH`
  carrying an `AgentFailure(category, detail)`, and the Agent sends nothing
  itself. `AgentResult.failed` is kept distinct from `not is_publishable` on
  purpose, so the workflow knows a decision not to publish is a success the user
  must not be emailed about.
- **The answer is parsed strictly, and the failure is classified rather than
  inferred from prose.** `parse_reasoning_answer()` extracts one JSON object
  (forgiving about code fences, strict about shape) and raises
  `ReasoningUnavailable` for a non-object, a missing boolean `publish`, or a
  non-list `evidence`. `reasoning.py` declares `ContentReasoner` as a
  `runtime_checkable` protocol — a fake with `name`, `prompt_version` and
  `reason()` is a reasoner, which is why every test runs offline.
  `LlmContentReasoner` builds the `ChatOpenAI` client lazily, so importing the
  package needs no credential, and collapses every client-build, invoke and
  parse failure into `ReasoningUnavailable`.
- **Retrieval strategy selection is supported only to the extent Step 10 asks
  for it, and no retrieval was redesigned.** `PLAN.md` notes that
  `RetrievalEngine` accepts a strategy but nothing chooses one. The Agent does
  not retrieve and cannot — `app.retrieval` is on the forbidden list. What it
  produces is a **recommendation**: the strategy for a fresh pass at the topic
  it chose, drawn from the vocabulary the caller allowed (`strategies=`). Empty
  vocabulary means *no choice to make*, and the proposal keeps the strategy the
  context was assembled with — a real strategy that demonstrably found this
  evidence, not a default invented here. A strategy outside the allowed set is
  refused like any other unresolvable name.
- **The prompt's parts are fields, and the prohibitions are generated from the
  list a test checks.** `ReasoningPrompt` carries named blocks
  (`opportunities_block`, `evidence_block`, `history_block`,
  `strategies_block`) with the rules as the system message, and the instruction
  sentence is built from `PROHIBITED_CLAIMS` — imported from
  `app.generation.prompt` rather than restated, so the two layers cannot drift
  into disagreeing about what a post may never invent.
- **`to_record()` produces the recordable form and nothing writes it.**
  JSON-compatible, no clock, no environment, no secret and no evidence text: the
  decision and its reason, the proposal's topic/angle/project/strategy and its
  evidence by provenance, the failure when there is one, and Step 9's own record
  once a draft got that far. Where it is written stays Step 11's.

Verified:
- 12 focused guarantees, each asserted against the public surface rather than
  against internals: `DO_NOT_PUBLISH` is reachable; `DO_NOT_PUBLISH` is
  respected (the caller's publish path is never entered); exactly one agent
  exists; the Agent cannot publish directly; the Agent cannot write state;
  publishing history is reached only through its read service; evidence
  selection is limited to retrieved/context evidence; unsupported evidence
  identifiers are rejected; the deterministic gates remain authoritative;
  reasoning failure yields `DO_NOT_PUBLISH`; a fake LLM produces reproducible
  decisions; and the bounded revision loop terminates.
- **Milestone:** one full simulated run with fakes — context → Agent decision →
  generation proposal → verification → final proposal/outcome — executed
  **twice**, asserting the two results are equal. The real workflow is not
  invoked.

Tests: 75 new (`tests/test_agent.py`, 52; `tests/test_agent_boundaries.py`, 23).
The first covers each of the twelve guarantees plus the milestone, driven by
`FakeReasoner`, `FakeHistory`, `FakeJudge`, `FakeLLM` and `FakeGenerator` over
contexts built from literal chunks; the second asserts what the package is
structurally unable to do (the forbidden-import scan, the positive allow-list,
the write-verb scan, the public surface, the read-only history surface, the
protocol's narrowness, and that the Agent holds no state between runs). No
network, no real LLM, no LinkedIn, no real publishing. Full regression: 907
passed.

Files: `app/agent/{__init__,agent,enums,errors,history,llm,models,prompt,reasoning}.py`,
`tests/test_agent.py`, `tests/test_agent_boundaries.py`,
`docs/implementation-status.md`.

Not implemented, deliberately: the workflows and their run records (Step 11),
scheduling, locks and recovery (Step 12), end-to-end evaluation (Step 13),
deployment (Step 14), persisting an `AgentResult` (Step 11 — see Known Issue
#14), and any notification on a reasoning failure (the Agent exposes
`AgentFailure`; Step 7's notifier is called by the workflow). No module in
`app/ingestion/`, `app/retrieval/`, `app/sync/`, `app/notify/` or
`app/integrations/` was modified, and nothing in Steps 0–9 was changed.

### Step 9 — Build Evidence Verification & Revision Gates

Status: COMPLETED

Implemented:
- Created `app/verification/` — nine modules behind one public surface
  (`__init__.py`): `enums.py` (five `str` enums), `errors.py`
  (`VerificationError`, `SupportJudgeUnavailable`), `models.py` (frozen value
  objects), `claims.py` (splitting and references), `policy.py` (the
  deterministic checks and the severity table), `support.py` (the judge
  protocol), `judge.py` (`LlmSupportJudge`), `verifier.py`
  (`EvidenceVerifier`, `verify`), `revision.py` (the stopping rule).
- **`verify(post, context, *, judge=None) -> VerificationResult` is the whole
  interface**, and it is a *function*, as `PLAN.md` Step 9 specifies ("not a
  pipeline stage — a function called by both the decision path and the revision
  loop"). `EvidenceVerifier` exists for a caller that wants to hold a judge
  across calls; it holds nothing else.
- **A draft is split into numbered claims, deterministically.** A claim is a
  sentence — split on sentence punctuation and newlines, list markers stripped,
  indexes assigned in order. Every non-empty sentence becomes a claim, so
  nothing escapes the gate; classifying whether a sentence "really makes a
  claim" would be the semantic judgement this layer is not allowed to fake.
- **Every claim is checked on its own and carries its own verdict.** `PASS`
  requires every claim supported; a single unsupported sentence produces
  `REVISION_REQUIRED` naming the claim number and the reason, and
  `ClaimVerification.supporting` records the evidence that resolved for that
  sentence. `PLAN.md` Step 9 asks for claim-level results; a single boolean
  cannot tell Step 10's loop what to change, and cannot tell an audit which
  sentence was the problem.
- **The deterministic checks are the gates, and severity is data.**
  `VIOLATION_SEVERITY` declares, once per kind, whether a finding is about the
  *wording* (`REVISABLE`) or about the *evidence or provenance* (`REJECT`), and
  `severity_for()` is total over the enum with no default — a future check
  cannot be added without someone deciding whether it gates. `REVISION_REQUIRED`
  and `REJECTED` are then derived, not chosen at each call site.
- **The verifier cannot invent evidence, structurally.** It holds no store
  handle, imports no retrieval, ingestion, publishing or notify module (asserted
  by an AST scan over every module in the package), and resolves the draft's
  citations against the supplied context by `(source, chunk_id)`. A citation the
  context does not hold, and a label the context never offered, are findings —
  not lookups that might succeed. Nothing is retrieved, so there is nothing for
  a check to reach into.
- **The exact-reference check is string matching, and its limit is written
  down.** Numbers, percentages, dates, versions and quantities are extracted by
  pattern, normalised (case, spaces, commas) and matched against the cited
  evidence's text — `40 %` matches `40%`, and a plain reference is not allowed
  to match across a word boundary. A figure in no cited evidence at all is
  `UNSUPPORTED_REFERENCE` (reject); a figure the supplied evidence *does* carry
  but the draft did not cite is `UNCITED_REFERENCE` (revise) — the two need
  different repairs and only one of them is repairable. Paraphrase is not
  detected here, and the module says so rather than implying otherwise.
- **`data/audit/README.md` §3 is operationalized, not paraphrased.**
  `FORBIDDEN_INFERENCES` holds the five *weaker source → stronger claim* rules,
  each with the audit line it came from quoted verbatim: coursework→professional
  experience, local project→production, configuration→deployment, course
  completion→mastery, portfolio entry→employment. Each rule fires only for a
  claim that *is* attributed to evidence (an unattributed claim is
  `NO_CITATION`'s business) and only when nothing behind it qualifies as strong.
  The sixth audit line — *never invent dates, metrics, technologies,
  responsibilities, or outcomes* — is not an inference from a source, and is
  enforced by the reference check plus the advisory judge instead.
- **The evidence state is checked as declared, with the corpus's own
  vocabulary.** `EVIDENCE_STATE_TOO_WEAK` fires for evidence declaring
  `UNVERIFIED` or `STALE` (nothing can rest on either), and for `ASPIRATIONAL`
  or `LEARNING` **unless the claim makes the same admission** — the corpus
  defines those states as legitimate, and "I'm learning X" supported by evidence
  that says exactly that is not the upgrade the audit forbids. Undeclared
  (`None`) evidence is usable and keeps its absent state.
- **Guidance is never evidence.** Step 4 keeps positioning, vision and writing
  style in separate fields; a claim whose vocabulary comes from guidance and
  from nowhere else is `GUIDANCE_AS_EVIDENCE` — revisable, because the sentence
  can be grounded or dropped, but never a pass, and never a citation.
- **The advisory judge is advisory in the code, not just in the prose.**
  `SupportJudge` is a structural protocol (a fake with `name`, `prompt_version`
  and `judge()` is a judge); it is consulted only when the deterministic checks
  found nothing *and* the claim asserts something *and* evidence resolved for
  it; its objection is recorded as `ADVISORY_UNSUPPORTED` with `advisory=True`
  and only ever routes to revision. It answers by **claim number**, and
  `map_verdicts()` refuses an answer about a claim that was not asked about, or
  two answers about one claim — a misnumbered answer is a defect
  (`VerificationError`, `JUDGE_FAILURE`), not something to silently drop.
- **Failing closed is separated from being unavailable.**
  `SupportJudgeUnavailable` — no client, no credential, no answer, an answer
  that is not the required shape — sets `degraded=True`, records it, and lets
  the deterministic gates stand. Any *other* exception from a judge is a
  `VerificationError`: a judge that crashed while judging may have had an
  objection. A context that reports `SUFFICIENT` evidence while holding none is
  also a `VerificationError` (`CONTEXT_UNUSABLE`) rather than a verdict.
- **A passing result cannot carry a finding.** `VerificationResult.__post_init__`
  refuses to construct `PASS` with any violation or any unsupported claim,
  refuses `REJECTED` without an unrepairable finding, and refuses
  `REVISION_REQUIRED` that carries one. The invariants are in the type, so a
  caller that reads only `outcome` cannot be misled by a result that disagrees
  with its own findings.
- **`to_record()` produces the persistable form and nothing writes it.**
  JSON-compatible, no clock, no environment, no secret, no evidence text: the
  outcome, every finding, each claim with its verdict and its supporting
  evidence by provenance, and the judge and prompt version behind the advisory
  half. Where it is written is Step 11's (see Known Issue #14).
- **The revision loop is not implemented; its stopping rule is.**
  `revision_decision(result, attempts_made, *, limit=MAX_REVISION_ATTEMPTS)` is
  total over outcomes and counts, returns `REVISE` only while the budget is
  unspent, and `EXHAUSTED` terminally — so no caller that obeys it can loop
  forever, and `PLAN.md`'s "REJECT after the limit is a correct outcome" is a
  value rather than a convention. `EXHAUSTED` is reported separately from
  `REJECT`: "this could never pass" and "we stopped trying" are different facts
  about a run.

Tests: 132 new (`tests/test_verification_rules.py`, 79;
`tests/test_verification_verifier.py`, 53). The rules file covers claim
splitting, reference extraction and normalisation, the severity table, each
deterministic check, each of the five forbidden inferences (firing on a weak
fixture *and* not firing on evidence that carries the claim), and the revision
gate's termination. The verifier file covers the eleven properties the step was
briefed with: a supported claim passes, an unsupported one fails, claims are
evaluated independently, provenance survives to the record, positioning cannot
satisfy evidence, insufficient evidence is an explicit result, a judge failure
fails closed, revision and rejection are distinguishable, the fake judge runs
fully offline (including the real judge with the credential removed), and
generated text is never returned as evidence. Every test is deterministic and
offline; no model, no network, no LinkedIn call. Full regression: 832 passed.

Files: `app/verification/{__init__,claims,enums,errors,judge,models,policy,revision,support,verifier}.py`,
`tests/test_verification_rules.py`, `tests/test_verification_verifier.py`,
`docs/implementation-status.md`.

Not implemented, deliberately: the revision loop and its attempts counter
(Step 10), the workflow's use of the outcome (Step 10), writing the record to
the operational store (Step 11 — see Known Issue #14), and any caller at all.
Nothing in Steps 0–8 was modified.

### Step 8 — Build Grounded Post Generation

Status: COMPLETED

Implemented:
- Created `app/generation/` — six modules behind one public surface
  (`__init__.py`): `enums.py` (`GenerationOutcome`, `DeclineReason`,
  `GenerationFailureCategory`), `errors.py` (`GenerationError`), `models.py`
  (frozen value objects), `prompt.py` (deterministic assembly, `PROMPT_VERSION`,
  `PROHIBITED_CLAIMS`), `generator.py` (`PostGenerator`,
  `parse_generation_output`).
- **`PostGenerator.generate(request) -> GenerationResult` is the whole
  interface.** One assembled context in; a draft with its metadata, or a
  decline, out. No store, no transport, no Agent, no second entry point — which
  is what lets a test drive a generation without the retrieval or publishing
  layers being alive (`PLAN.md` Step 8).
- **The prompt's parts are fields, not one string.** `GenerationPrompt` holds
  `task_block` · `evidence_block` · `guidance_block` · `constraints_block`
  separately and renders them under their own headers, with the rules as the
  *system* message and the material as the user one. `PLAN.md` Step 8 forbids one
  thing above all — a concatenated chunk dump — and this is the shape that makes
  the prohibition checkable: no test asserts on a prompt's wording, only on which
  block holds what.
- **Step 4's evidence/guidance separation is spent here.** The evidence block is
  built from `context.evidence_items()` and the guidance block from
  `context.guidance_items()`, with nothing crossing between them; each guidance
  item keeps its section name and its source. Merging them would undo the
  context layer for the one consumer where the difference decides whether a
  manner of speaking becomes a claimed achievement.
- **The prohibitions are constant, and generated from one list.**
  `PROHIBITED_CLAIMS` is the single source of the enumerated rule — never invent
  projects, achievements, technologies, metrics, dates, certificates,
  experiences or claims the evidence does not support — so the sentence a model
  reads and the list a test checks cannot drift apart. The instructions also
  forbid presenting guidance as evidence, describing coursework as professional
  experience, describing a practice project as a production system, and citing a
  label that was not supplied.
- **Assembly is deterministic and total.** Blocks come from ordered tuples,
  labels are assigned by position, and nothing reads a clock, a random source,
  the environment or the retrieval order — asserted by rebuilding the prompt
  from the same documents in reversed order. A context with no evidence yields a
  prompt with an empty evidence block rather than an exception, which is what
  makes the empty case testable at all.
- **Evidence selection is bounded by the context it came from.**
  `request.evidence = None` means *all* of the context's evidence (not none);
  an explicit subset is returned in the context's own order, deduplicated by
  identity, and an item the context does not hold raises `ValueError`. Selection
  is Step 10's job; material the assembly layer never placed is not this layer's
  to write from, and refusing loudly is the difference between a bad choice and
  an invention.
- **A decline is decided before the model is called.** No evidence in the
  assembled context → `DECLINED` / `INSUFFICIENT_EVIDENCE`, with **no request
  made** and `latency_ms` left `None`. Asking a model to write from no evidence
  is asking it to invent, so `PLAN.md` Step 8's "receive an insufficient-evidence
  signal and decline rather than fabricate" is answered deterministically and
  for free — and a plausible-looking duration on a result that never left the
  machine would be a fabricated measurement in an audit record.
- **A decline is a result; a failure is an exception; there is no third thing.**
  The model may also decline (`MODEL_DECLINED`, with its reason carried
  verbatim). An unreachable model, a missing credential or an answer that is not
  the required shape raises `GenerationError` with a
  `GenerationFailureCategory` — `LLM_UNAVAILABLE`, `CONFIGURATION`
  (`requires_human_intervention` is true for that one only) or
  `INVALID_RESPONSE`. **No degraded post exists**: no placeholder, no
  truncation, no "best effort" text — `PLAN.md` Step 8 is explicit that
  generation, unlike retrieval, cannot usefully fall back, and unverified text
  about a real person reaching the publish path indistinguishable from a draft
  is the failure this refusal prevents.
- **A declining result lands on `DO_NOT_PUBLISH`, which is waived.** Step 7
  sends no email for a normal outcome, so a correct "nothing worth saying"
  produces no alert; only a genuine generation failure is `WORKFLOW_FAILED`.
  Raising on a decline would turn the system's best behaviour into an incident.
- **Citations are resolved, never trusted.** The model answers with the labels
  (`E1`, `E2`) the prompt sent; `_resolve()` looks each one up in the prompt's
  own citation list. A resolved label becomes a citation with its source path,
  chunk id and declared evidence state; an unresolved one is reported in
  `GeneratedPost.unresolved_labels` rather than dropped, because a model citing a
  source it was never given is a fact Step 9 has to be able to see. "A draft
  cites only sources present in that set" is therefore structural — there is no
  code path from an invented label to a citation.
- **Parsing is strict about the payload and lenient about the wrapper.** A
  ```json fence or prose either side of the object is stripped, because that
  would otherwise fail generations that are perfectly usable; the payload itself
  must still be the required object, and an answer that is neither a post nor a
  decline is `INVALID_RESPONSE` rather than a post extracted from prose.
- **Metadata travels with the draft.** `GenerationMetadata` carries the model id,
  the prompt version, the parameters, the evidence and guidance item counts, the
  labels the prompt listed, and the measured latency. All of it is ordinary
  configuration or something measured here; the credential is never read into the
  object at all.
- **Configuration is the repository's existing boundary and nothing new.**
  `config.MODEL_ID`, `config.GENERATION_PARAMS`,
  `config.OPENROUTER_BASE_URL` and `config.require_openrouter_key()`, following
  `app/retrieval/multi_query.py`. `ChatOpenAI` is imported lazily *inside* the
  real-client path, so importing the generation layer — which the test suite does
  constantly — costs nothing and needs no credential.
- **A failed call is redacted with the shared list.** The provider's error text
  is external input and is passed through `redact()` before it is kept, the same
  single list (`known_secrets()`) the log filter and `app/notify` use.
- **The layer cannot reach anything it must not.** An AST scan parses every
  module in `app/generation/` and fails on an import of `chroma`, `sqlite3`,
  `smtplib`, `requests`, `app.state`, `app.publishing`, `app.notify`,
  `app.retrieval` or `app.ingestion`. Generation writes no state, publishes
  nothing, sends nothing and never queries the vector store as a property of the
  code rather than as a rule someone has to remember.

Verified:
- `tests/test_generation_prompt.py` (34 tests) — assembly only, no model: which
  block holds what, the per-term prohibitions, determinism under reversed input
  order, the empty-evidence case, selection rules, and a real-corpus test that
  reads `data/writing_style/alaa_writing_style.md`, puts it through the layer and
  asserts its text reaches the guidance block while the constant instructions do
  not contain it.
- `tests/test_generation_generator.py` (39 tests) — the service contract: what
  the model is handed, the structured result and its metadata, citation
  resolution and invented labels, declines with and without a call, each failure
  category, and the import scan.
- **No test opens a socket, reads a credential or calls a model.** The model is
  an injected object with an `invoke()` method; one test drives the whole path
  with `OPENROUTER_API_KEY` patched to `None` to prove the suite is offline by
  construction rather than by luck.
- Acceptance criteria, one by one: generation consumes assembled context, not raw
  chunks (the evidence block is built from `context.evidence_items()`, and the
  model is asserted to receive the context's own text, source and chunk id);
  output is structured and carries model/prompt metadata; insufficient evidence
  produces a declining outcome with no call made, not a fabricated post; the
  tests run fully offline with a fake LLM; style and positioning come from the
  knowledge files through the context layer, not from hardcoded prompt text.
- Milestone: a draft generated from a known evidence set cites only sources
  present in that set — a label that was never sent (`E9`) resolves to nothing
  and is reported as unresolved.
- Full suite: **700 passed** (`627` before Step 8; the 73 new tests are the whole
  difference, and nothing existing changed its result).

Deviations:
- **No LCEL chain, deliberately.** `PLAN.md` Step 8 says "LCEL chain, consistent
  with the existing stack", and `docs/architecture/data-flow.md` describes
  `prompt | llm | parser`. This is implemented instead as a typed
  `GenerationPrompt` rendered to two plain `{"role", "content"}` messages and
  invoked through the repository's existing injectable-client seam
  (`llm.invoke(messages)`), with `langchain_openai.ChatOpenAI` on the real path
  only. The reasons: the interface Step 8 needs is *typed blocks*, which is a
  value object rather than a `Runnable` pipeline; `ChatOpenAI.invoke()` accepts
  exactly these dicts, so the real path is the same OpenRouter client
  `app/retrieval/multi_query.py` already uses; and a fake with one method is then
  sufficient to test the whole contract offline. The cost is that a future step
  wanting LangChain-level composition (streaming, callbacks, retries) will have
  to wrap this rather than extend a chain. A one-line correction to
  `data-flow.md` records the deviation where the claim was made.
- **Nothing calls the generator yet.** Step 8's obligation is that a candidate
  post is *producible* from an assembled context with its metadata; which
  workflow calls `PostGenerator`, and what it does with a decline, is Step 10
  (the Agent) and Step 11 (the workflows). Step 7 added an interface with no
  caller and Step 8 adds a second, so the two meet at the same place. Recorded as
  Known Issue #13.
- **The real OpenRouter path has never been exercised.** Every test injects a
  fake, so the first real call is still ahead, and it will fail immediately on
  Known Issue #5 — an OpenAI-family key sent to the OpenRouter endpoint — as a
  `CONFIGURATION` generation failure naming the variable to set. That is the
  designed behaviour for an unconfigured model, and it is deliberately not
  papered over with a fallback, a stub, or an invented credential.
- **The prohibitions are instructions, not checks.** The prompt forbids
  unsupported claims and the code makes an invented *citation* impossible, but
  nothing here inspects the draft's sentences. Whether a claim is supported by
  the evidence is Step 9's question, and a check invented here would be a second
  verifier free to disagree with the real one. What Step 8 guarantees is narrower
  and honest: the model was given the evidence, told what it may not claim, and
  its own list of what it used can only name sources it was actually given.

---

### Step 7 — Build Operational Failure Notifications via Email

Status: COMPLETED

Implemented:
- Created `app/notify/` — seven modules beside the workflows (not inside them):
  `enums.py` (`NotificationDecision`, `WaiverReason`,
  `NotificationFailureCategory`), `errors.py`
  (`NotificationDeliveryError`, `NotificationConfigurationError`), `config.py`
  (`SMTPConfig`, `smtp_config()`, `require_smtp()`, `missing_settings()`),
  `models.py` (`NotificationMessage`, `NotificationReport`), `messages.py`
  (composition), `transport.py` (`EmailTransport` protocol + `SMTPTransport`),
  `service.py` (`NotificationService`).
- **The decision is deterministic infrastructure.** `NotificationService`
  exposes exactly two entry points: `notify_run(run_id)` for the workflow
  wrapper (the run's recorded outcome is the input) and `notify_failure(failure)`
  for a phase (the recorded failure is the input). Neither asks the Agent, and
  neither re-derives severity: `WORKFLOW_FAILED` vs
  `REQUIRES_HUMAN_INTERVENTION` is read off `requires_human_intervention` and
  the run outcome Step 1 constrains.
- **A normal outcome is waived, never emailed.** `DO_NOT_PUBLISH` and an
  unfinished run return `NotificationDecision.WAIVED` with
  `WaiverReason.NORMAL_OUTCOME` and touch neither the transport nor the store.
  A `DO_NOT_PUBLISH` run that got past a recorded phase failure is still waived:
  the run outcome is the recorded fact, not the presence of a failure row.
- **The transport is a protocol, and the only implementation is stdlib.**
  `EmailTransport` (`name` · `recipient` · `describe` · `send`) is the whole
  contract, so a fake and `SMTPTransport` are interchangeable. `SMTPTransport`
  uses `smtplib` with `timeout=` on every connection, STARTTLS or implicit TLS
  per configuration, and `login()` only when a username is configured. No new
  dependency: `smtplib` is stdlib (`PLAN.md` §12.1 decision 3).
- **Configuration is entirely environmental.** `app/config.py` gained
  `SMTP_HOST · SMTP_PORT · SMTP_SENDER · SMTP_RECIPIENT · SMTP_USERNAME ·
  SMTP_PASSWORD · SMTP_TLS · SMTP_TIMEOUT_SECONDS · SMTP_REPEAT_AFTER_HOURS`,
  all with empty or neutral defaults, and `.env.example` documents them. The
  addresses (`PLAN.md` §12.2 open item C) are the user's, so nothing in the
  repository invents one; an unknown `SMTP_TLS` value is a `ConfigError` at
  import, not a silently unencrypted connection at send time.
- **The distinction between the two failures is the data model.**
  `notifications.delivery_state` records the delivery; `operational_failures`
  keeps the failure. A delivery failure writes only the notification row, with
  `error_message` and a category — `configuration` (fix the variables),
  `authentication` (fix the app password), `transport` (the network or the mail
  server). The failing phase's row, the run's outcome and `occurrence_count` are
  untouched by it, and a `FAILED` delivery is never counted as having reported
  the failure, so the next run tries again.
- **Redaction is one list, not two.** `app/logging_config.py` now exposes
  `known_secrets()` (with `SMTP_PASSWORD` added to `SECRET_ENV_VARS`) and
  `redact()`; the logging filter is one consumer of that list and `app/notify`
  is another. Composed subjects and bodies, the recorded `error_message`, and
  the reason string logged on a delivery failure all pass through it — the last
  one matters because the text comes from a mail server, which is external
  input. `SMTPConfig.password` is `repr=False`, and the recorded
  `notifications.smtp_config` is `host:port tls=mode` only: no username, no
  password, no message body anywhere in the table.
- **Noise control uses the store, not a second store.** A repeat of a failure
  already reported inside `SMTP_REPEAT_AFTER_HOURS` (default 24h) is waived with
  `WaiverReason.REPEAT_SUPPRESSED`; only `sent` rows count, so a delivery that
  failed does not suppress the next attempt. The first occurrence has no prior
  row, so it cannot be suppressed — the property `PLAN.md` insists on, enforced
  by the shape of the check rather than by a flag. The lookup needed one
  additive read: `StateStore.list_notifications(..., failure_id=None)` (no
  schema change).
- **The store is optional for exactly one reason.** The state store is itself a
  phase that must be able to report (`PLAN.md` Step 7, reachability table), so
  `NotificationService(store=None)` still composes and sends, and its report
  says `recorded is False` instead of pretending the delivery was written down.
  Everything that *reads* — `notify_run` — requires the store and raises
  `StateStoreError` without it.
- **The notification layer cannot reach the knowledge or publishing layers**,
  and the publishing layer cannot send mail: both directions are asserted by
  AST import scans (mirroring the Step 6 scan over `app/publishing/`), so
  "SMTP is not imported into `app/publishing/`" is a property of the code rather
  than a rule someone has to remember.

Verified:
- `tests/test_notify_service.py` (56 tests) and `tests/test_notify_transport.py`
  (17 tests) — decision, composition, delivery records, delivery-failure
  categories, noise control, redaction, layer isolation, and the SMTP
  connection itself against a recording fake of `smtplib`.
- `tests/test_logging.py` (1 new test) and `tests/test_config.py` (4 new tests).
- **No test opens a socket or reads a credential.** The only SMTP code under
  test is `SMTPTransport` with `smtplib.SMTP`/`SMTP_SSL` replaced by recording
  fakes; every other test uses `CapturingTransport`.
- Acceptance criteria, one by one: a failed unattended run produces exactly one
  message through the fake transport and exactly one stored row; a
  `DO_NOT_PUBLISH` run produces none; every phase in the reachability table can
  report a failure (parametrized over all sixteen phase names, including
  `state_store`); no secret appears in a message, a subject, a delivery record
  or a logged reason; a transport failure leaves the original failure, its
  `occurrence_count` and the run outcome intact and is separately observable;
  a missing setting raises a `ConfigError` naming the variable and opens no
  connection; duplicate suppression never hides a first occurrence and does not
  suppress the next attempt after a failed delivery.
- Full suite: **614 passed** (`536` before Step 7; the 78 new tests are the
  whole difference, and nothing existing changed its result).

Deviations:
- **Nothing calls the notifier yet, and that is deliberate.** Step 7's
  obligation is that any outcome a workflow records is *reportable*; which
  workflow calls `notify_run`, and whether it calls `recover_run()` first, is
  Step 11's orchestration decision. `PLAN.md` Step 7 was explicit that the
  scheduled runs are not wired here, and this record keeps that visible rather
  than implying an alert would arrive today. Recorded as Known Issue #10.
- **No email has ever actually been sent.** `smtplib` is exercised only against
  a fake that records what it was asked to do. The first real delivery is a
  deliberate manual act, like the first real publish (Known Issue #9), and
  `SMTP_*` is unset in `.env` today — so a failure right now is recorded as a
  `configuration` delivery failure, which is the designed behaviour for an
  unconfigured notifier and not a silent no-op. Recorded as Known Issue #11.
- **No write-ahead `pending` row.** The delivery row is written once, after the
  attempt, with its final state. Step 6 wrote the publish intent *before* the
  call because a duplicate post is unrecoverable; an unsent email is not — the
  failure it reported is already durable, and a crash mid-send leaves no false
  claim behind. `update_notification_delivery()` therefore remains unused, as
  the seam for a provider with a genuinely asynchronous send.
- **A failure that a run recovered from still leaves an alertable row.** A
  phase can record a failure and the run still terminate `DO_NOT_PUBLISH`; the
  run is then waived, but the failure row itself is notifiable if a caller asks
  for it by `notify_failure`. That is intended — the run-level decision and the
  failure-level decision are different questions — but it does mean a phase that
  records transient failures it handles will accumulate rows that only a
  deliberate `notify_failure` call would report.

Follow-up, added after the step was reviewed — **one mailbox, two kinds of
message**:

- **Every notification now carries the same subject, `"Branding Agent"`**, and
  what a message is *about* moved onto the message itself as a
  `NotificationKind` (`ISSUE` / `PUBLICATION`) rather than being encoded in the
  subject line. The user wanted one mailbox to receive both the system's
  problems and the posts it publishes, and one predictable subject is what makes
  that routable. The cost is accepted deliberately: the subject no longer says
  which kind a message is, so the body has to be opened to find out.
- **The body now leads with the thing itself.** An issue email quotes the
  recorded failure message first and verbatim — the same text that used to sit
  at the bottom under `Explanation:` — before any of its metadata; a run email
  with several failures attributes each description to its phase. A published
  post's body *is* the post content, with the post id and link underneath.
- **`notify_publication(post)` is the third entry point**, and the one the
  failure path structurally cannot cover: a successful publish terminates
  `DO_NOT_PUBLISH`, which is waived as a normal outcome, so nothing else would
  ever tell the user what went out under their name. The post arrives as a
  `PublishedPost` value rather than being looked up, because `app/notify/` may
  not import `app/publishing/` — the import scan still passes.
- **A publication has no noise control, deliberately.** The repeat window exists
  to stop a recurring *condition* from flooding the mailbox; a post is an event
  with a beginning and an end. `_deliver(..., key=None)` skips the suppression
  check, so two posts published in a row are two things to read.
- **A post is reported, not learned from.** The content goes into an email and
  the delivery into the `notifications` table (`failure_id` NULL, `run_id`
  optional); it is never indexed, never written into the knowledge base, and
  never becomes context for the next post. Asserted by a test that walks every
  field of the delivery row and fails if the post text appears in any of them.
- **`SMTPConfig` test hermeticity was fixed in the same commit.** The Step 7
  configuration tests asserted the *code's* defaults while reading the
  developer's local `.env`, so they began failing the moment real SMTP settings
  were added — a defect in the tests, not in the code, and one that would have
  failed on the Step 7 commit too. They now clear the `SMTP_*` variables before
  reloading, so the claim is about the code.

---

### Step 6 — Build Persistent Publishing, Idempotency & Recovery

Status: COMPLETED

Implemented:
- Created `app/publishing/` — seven modules behind one public surface
  (`__init__.py`): `enums.py` (`PublishDecision`, `DuplicateKind`,
  `InterruptionKind`), `models.py` (frozen value objects and `evidence_ref()`),
  `vectors.py` (the embedding ↔ BLOB helpers), `duplicates.py` (the three
  checks), `history.py` (the read service) and `service.py`
  (`PublishingService`).
- `PublishingService.publish(request, run_id) -> PublishReport` is the only
  path from a generated post to a request. It owns every publish state
  transition and enforces them **in this order**: run the duplicate checks →
  write the intent → mark the attempt started → call the transport → record the
  outcome. Nothing above it touches `StateStore`, and the LinkedIn integration
  below it still knows nothing about runs, intents, or idempotency.
- **The intent is durable before the request exists.** `create_publish_intent`
  commits before the transport is called; the test asserts it from *inside* the
  fake transport, which is the only place where "before" is observable.
- **`MAX_PUBLISHES_PER_RUN = 1` is still enforced by the database, not by
  Python.** `ux_publish_intents_run` refuses a second intent for a run, so a
  workflow cannot forget to check and a second attempt is rejected by SQLite
  before any request is built. The constant exists so the code that depends on
  the rule can say so; it is documentation, not a check.
- **An attempt is marked before it is sent**, which is what makes the two
  interruptions distinguishable afterwards: an intent still at `intent_created`
  means no request left the machine, and one at `attempt_started` with no
  publication means one may have.
- **The outcome is recorded from evidence, never assumed.**
  `state_for_result()` maps a post id to `published`, `UNKNOWN` to
  `unknown_requires_review`, and everything else to `failed`. A claimed success
  with **no post id** is recorded as `unknown_requires_review` rather than
  `published`: the store would refuse it as a publication anyway (its CHECK
  constraint requires an id), and "accepted, with nothing to point at" is
  precisely the ambiguity the state exists for.
- **An ambiguity is never retried.** `recover_run()` resolves the two
  interruption kinds in opposite directions, on purpose: `attempt_started` →
  `unknown_requires_review` (a post may exist; a person must confirm — retrying
  is how the duplicate happens), and `intent_created` → `failed` (nothing was
  sent, so the words are free for a later run). Recovery is idempotent —
  resolved intents are terminal and are not returned again — and scoped to one
  run.
- **A store failure stops the publish.** `StateStoreError` propagates out of
  `publish()`; it is never converted into a result. A refusal, a failure and an
  ambiguity are all *reports*, because a workflow branches on them — but a run
  that cannot record what it observed must not go on to act.
- **Three duplicate checks over three kinds of data, never merged** (`PLAN.md`
  Step 6 requires the distinction):
  1. **exact** — the content hash, against `find_intent_by_content_hash()`
     (the query that mirrors the store's unique index). A definitive failure
     releases the text; an unresolved attempt blocks it, because a hash match
     cannot prove the words never went out.
  2. **near** — cosine similarity against the stored embedding of recently
     *published* posts, using the same embedding machinery as retrieval. The
     candidate's vector is stored with its publication
     (`publications.embedding`), so history is never re-embedded and an old
     post's similarity cannot drift with the embedder of the day.
  3. **overuse** — topic, project, and per-evidence-reference counts over a
     window, read from the stored references. Evidence is counted by
     `(source_path, content_hash)`, never by path alone: the corpus is
     resynchronized every 24 h, and counting by path would report a source as
     overused when the post would be the first to cite what is now there.
  A report says which check found what (`DuplicateKind`); on an exact match the
  other two are not run, and a request that could never be sent is not asked to
  produce them.
- **The duplicate policy fails closed.** A configured embedder that raises makes
  the near-duplicate check *unchecked*, and an unchecked required check refuses
  the publish: publishing unchecked is unrecoverable, whereas a refusal is not.
  `DuplicateReport` therefore keeps `unchecked` separate from `findings` —
  "nothing matched" and "nothing was compared" must never look alike — and
  `must_not_publish` covers both.
- **The publishing-history read service is SQLite-only, deterministic, and
  read-only** (`PublishingHistory`): recent publications, recent topics, recent
  projects, evidence used, unresolved intents and what requires review. Every
  row is attributable to a stored publication (`publication_ids` travels with
  every count), an empty history returns empty rather than raising, and the
  published *text is never returned by any of it* — the prose is absent from
  every type the service hands out. That is what makes `PLAN.md` §6.1 structural
  instead of behavioural.
- **The layer cannot reach the knowledge base, and that is asserted
  structurally.** A test parses every module in `app/publishing/` and fails if
  any of them imports `chroma`, `langchain`, `app.retrieval` or `app.ingestion`
  — there is no code path that could index a publication. A behavioural test
  could only show that it did not happen in the cases it tried.
- **Evidence references are `source path + content hash`.** `evidence_ref()`
  splits the context layer's `<content_hash>:<chunk index>` provenance and
  refuses a reference with no hash — without it, a later audit cannot
  distinguish "grounded in evidence that has since changed" from "never
  grounded", which is the one question the reference exists to answer.
- **The Step 1 seams are minimal and use the existing migration mechanism.**
  Schema migration v3 adds exactly two columns — `publish_intents.project` and
  `publications.embedding` — and the store gained the queries the service
  needs (`find_intent_by_content_hash()`, `list_unresolved_intents()`,
  `list_publication_records()` plus the `PublicationRecord` value object). No
  new persistence abstraction, no new database, no new vector store.
- **No exactly-once claim is made anywhere.** What the system has is an at-most-
  one-publication-attempt-per-run guarantee, a durable intent, an explicit
  ambiguous state, and a recovery path that fails closed. Exactly-once delivery
  to LinkedIn is not achievable without read-back (`PLAN.md` §5.1) and is not
  promised — in the code, in a message, or in this record.

Verified:
- 67 focused tests across three files, all offline: fake transports, temporary
  state databases, and the deterministic token-bucket embedder from
  `tests/conftest.py`. No network, no credentials, no real publish, no LLM.
- Acceptance: the intent is durable **before** the request — asserted from
  inside the transport, and separately between the intent and the
  `attempt_started` mark.
- Acceptance: one publication per run — the second intent of a run is rejected
  **by the database**, and the test asserts the SQLite error rather than a
  Python guard. A later run may still publish different content.
- Acceptance: exact duplicate rejection (refused before any request is made,
  with nothing written for the refusal), near-duplicate detection (a reworded
  post, similarity asserted), and topic / project / evidence overuse. The
  project case is built from posts sharing no vocabulary at all, so a merged
  "similarity" verdict could not have produced it.
- Acceptance: a timeout and a transport failure after the request was sent
  both record `UNKNOWN_REQUIRES_REVIEW`; a classified failure records `FAILED`;
  a success records the LinkedIn post id.
- Acceptance: `UNKNOWN` is never retried — a later run attempting the same text
  is refused as an exact duplicate, and `recover_run()` resolves nothing but
  the state.
- Acceptance: a crash **after** the external call but before the local
  recording leaves a recoverable ambiguity, not a failure. Simulated by
  closing the store from inside the transport after a successful post: the
  reopened store shows the intent at `attempt_started`, and recovery resolves
  it to `UNKNOWN_REQUIRES_REVIEW` and blocks. The mirror case — a crash before
  the attempt started — is recorded as `FAILED` and releases the content.
- Acceptance: history queries return only stored records, every row traces back
  to a stored publication, an empty history returns empty, and no history type
  carries the generated text.
- Acceptance: every evidence reference contains a content hash, and the history
  reports evidence by path **and** hash.
- Acceptance: publishing history never enters Chroma — asserted by the import
  scan over the whole package.
- Recovery is idempotent and run-scoped, and the state survives a full process
  restart (reopened store, same rows, same decisions).
- Full regression: **533 passed**, 1 pre-existing warning (torch CUDA), 100.9 s.
  The pre-Step-6 baseline was 466 passed; the 67 Step 6 tests are the whole
  difference, and nothing existing changed its result.

Deviations:
- **`project` is a stored label on the intent, not derived from evidence
  paths.** Deriving it would mean guessing which directory a path belongs to,
  which is the opposite of the deterministic behaviour this step is required to
  have. It is recorded symmetric with `topic` and `angle`, and it is what makes
  project overuse detectable from state rather than inferred from text.
- **The published text is not copied onto `publications`.** It lives on the
  intent, and `publications.intent_id` is UNIQUE, so the join is 1:1 and a
  second copy could only drift. Combined with the history service never
  returning generated text, "a generated post is never evidence about the user"
  is a property of the types, not of a rule someone has to remember.
- **Near-duplicate detection is inert until an embedder is supplied.** The
  check is part of the policy only when the service is constructed with one;
  Step 11 wires the real embedder, and Step 6 must not reach into retrieval to
  get it. Recorded as Known Issue #8 so it cannot be mistaken for active
  protection in the meantime.
- **The service returns a report for everything LinkedIn did and raises only
  for the store.** A refusal, a failure, an ambiguity and a success are normal
  outcomes a workflow branches on; a store failure is the one thing a caller
  must not continue past.
- **One real publish is still outstanding, and this step did not perform it.**
  The wrapped path is exercised end to end against fakes only. The single real
  publish through the service remains a deliberate manual act (see the Step 5
  record and Issue #9).
- **Deviation, added after the step was reviewed — a 5xx from the post endpoint
  is `UNKNOWN`, not `FAILED`.** Step 6 was implemented against the Step 5 result
  as it then stood, where every received response that was not a publication
  came back `FAILED`. A review of the boundary found that is wrong for the one
  request that can create a post: a 5xx means LinkedIn received the request and
  its own handling failed, so whether a post exists cannot be established from
  here, and there is no read-back to ask (§5.1). Recorded as `FAILED`, such an
  attempt drops out of `ux_publish_intents_unresolved_content`, a later run
  stops finding it by content hash, and the same words go out twice — the
  duplicate this step exists to prevent. `publisher._http_failure` now takes a
  required `outcome` and the post call site passes `UNKNOWN` for `status >= 500`
  while the identity call site keeps passing `FAILED` (no post request has been
  made at that point, whatever the status). The 5xx *classification* is
  unchanged — still `TRANSPORT` and still `retryable`, which is advice about the
  failure rather than a statement about the post — and `retryable` never
  mattered here because nothing in Step 6 retries. The state machine, the
  duplicate checks, and the schema are untouched; `PublicationOutcome`,
  `PublishState.UNKNOWN_REQUIRES_REVIEW` and recovery's two directions already
  expressed this case, and only the boundary was failing to use them.

---

### Step 5 — Harden the LinkedIn Integration for Autonomous Use

Status: COMPLETED

Implemented:
- Created `app/integrations/linkedin/` — six modules behind one public surface
  (`app/integrations/linkedin/__init__.py`): `enums.py` (`LinkedInErrorCategory`,
  `PublicationOutcome`, `CredentialStatus`), `models.py` (frozen value objects),
  `errors.py`, `classification.py` (status/transport → category, and local
  commentary validation), `credentials.py` (the credential lifecycle),
  `client.py` (the HTTP boundary: `LinkedInClient`, payload, URN and post-id
  extraction) and `publisher.py`.
- `publish_to_linkedin(post_text, *, store=None, client=None, token_path=None,
  now=None) -> PublicationResult` is the whole entry point. It never prints,
  never prompts, and **raises only `StateStoreError`** — and only before any
  request is made. Every other failure, including a total absence of
  credentials, comes back as a classified result.
- **The proven publish path is retained, not rewritten.** The endpoint
  (`POST /rest/posts`), the payload, the `x-restli-id` header the post id is
  read from, and `GET /v2/userinfo` → `urn:li:person:{sub}` are the values that
  were already verified against the real API; `app/integrations/linkedin/`
  wraps them. `Auth_handling/test_post.py` remains the manual verification
  tool and was not converted into the service.
- **Every request is bounded.** `LINKEDIN_TIMEOUT_SECONDS` (default 30.0)
  reaches `requests` on every call, including the identity lookup and the token
  refresh. `LinkedInClient` rejects a non-positive timeout with `ValueError` at
  construction, so "no timeout" is unrepresentable rather than merely unused.
- **Failures are classified, never inferred from a message.**
  `classify_status()` maps 401 → `AUTHENTICATION`, 403 → `PERMISSION`, other
  4xx → `VALIDATION`, 429 → `RATE_LIMIT`, ≥500 → `TRANSPORT`, everything else →
  `UNKNOWN`; `classify_transport_error()` separates a connect-time failure
  (nothing was sent) from a failure after the request left. `retryable` is
  advice about the failure, not permission to retry — this layer never retries
  anything, and the policy belongs to Step 6.
- **The ambiguous outcome exists and is reachable.** `PLAN.md` §5.1: LinkedIn
  can publish but cannot be read back, so local state is authoritative and an
  attempt whose fate is unknown must be expressible rather than guessed. A 201
  with no `x-restli-id`, and any transport failure after the request was sent,
  return `PublicationOutcome.UNKNOWN` with `retryable=False`. A connect-time
  failure returns `FAILED` with `retryable=True`, because nothing was sent.
- **One persistence surface was added, and it is not about publishing.**
  Schema migration v2 creates `linkedin_credential_expiry` — the expiry read
  from the stored credential, the issuance time it was derived from, and which
  evidence produced it (`id_token_iat` or `file_mtime`, CHECK-constrained). It
  is the only write the integration makes; no publication, intent, run or
  failure row is written by this step. It exists because the credential carries
  a *duration* (`expires_in`), never an absolute expiry, so the expiry must be
  derived — and a credential that dies between two runs has to be detectable by
  the run that comes after.
- **The credential lifecycle warns before it fails.** Status is `VALID`,
  `EXPIRING_SOON` (inside `LINKEDIN_EXPIRY_WARNING_DAYS`, default 14), `EXPIRED`,
  `MISSING` or `UNREADABLE`. Expiring still publishes, and the warning is
  carried on the success result too — a warning that only appears on the run
  that has already stopped working is not a warning. Expired, missing and
  unreadable all fail closed with `requires_human_intervention=True` and
  `retryable=False`, and the message names `linkedin_oauth_setup.py`: this is a
  `REQUIRES_HUMAN_INTERVENTION` termination, not `WORKFLOW_FAILED`.
- **An unknown expiry is reported as unknown.** The derivation is
  `id_token.iat` where the credential carries a decodable one, otherwise the
  file's mtime (the exchange that issues the token is what writes the file),
  otherwise nothing — the expiry is reported absent, never inferred from
  something else.
- **Automatic refresh is not assumed, and is not required.** A refresh is
  attempted only when the credential is *already expired* and carries a
  `refresh_token` and the application credentials are configured; a valid or
  merely expiring credential is never refreshed. A rejected or timed-out
  refresh stays an authentication failure, is not retried, and leaves the
  on-disk credential untouched. The real token has no `refresh_token` at all,
  so the working path is detection → clear auth state → a person re-runs the
  OAuth script. The refresh path is exercised only against a fake transport.
- **The API version is configuration.** `LINKEDIN_API_VERSION` (default
  `202607`) is validated as `YYYYMM` at import, sent as `LinkedIn-Version`, and
  recorded on every `PublicationResult` — because a versioned API fails for
  reasons that have nothing to do with the post.
- **Secrets cannot reach a log or a result.** `load_dotenv` is by path, not by
  CWD, in all three `Auth_handling/` scripts and in `app/config.py`;
  `SecretRedactionFilter` now also reads the token file, so the token written
  to disk *after* `.env` was last edited is redacted too; `LinkedInCredential`
  excludes its token fields from `repr`; and result messages and response
  bodies pass through `redact()` before they are stored.
- **The CWD-dependence defect is fixed at the source.** `app/paths.py` now
  defines `ENV_FILE` and `LINKEDIN_TOKEN_FILE` once, and all three
  `Auth_handling/` scripts resolve the token file relative to their own
  location. `linkedin_oauth_setup.py` — the script that *creates* the token and
  the one that previously wrote it where the readers would never look — was
  reconciled with the two that had already been corrected. See Known Issue #3.

Verified:
- Acceptance: a successful publish returns the LinkedIn post id, and the
  request that produced it is asserted field by field (method, URL, author,
  commentary, `LinkedIn-Version`, timeout).
- Acceptance: missing, expired and unreadable credentials fail clearly and
  safely — each returns a classified authentication failure with a human-
  intervention flag, and **no request is made**.
- Acceptance: no token appears in any log line, error, result message, `repr`,
  or response body. Asserted with a response body that deliberately echoes the
  token back.
- Acceptance: the service works from any working directory. Asserted by
  `monkeypatch.chdir()` plus the fact that the token path, the `.env` path and
  the API version all resolve from the project root.
- Acceptance: every error category is exercised through the real classification
  table, from simulated LinkedIn responses and simulated transport failures —
  no test touches the network, needs a real credential, or publishes anything.
- The publish path cannot prompt or print, checked at source level across every
  module in the package — an unattended workflow that blocks on `input()` is the
  failure this step exists to remove.
- Publishing writes nothing but the credential expiry: after a successful
  publish, `list_publications()`, `list_publish_intents()`, `list_runs()` and
  `list_failures()` are all empty. Step 6 owns publication records.
- A store failure stops the publish before any request (fail-closed, `PLAN.md`
  §11), and `StateStoreError` is never swallowed into a result.
- The three `Auth_handling/` scripts resolve the same token file as
  `app/paths.py` — asserted by parsing each script and comparing the assignment
  expression, so the drift cannot silently return. Separately asserted: each
  script passes a path to `load_dotenv`, and the token file is gitignored.
- A live read-only smoke check of `check_credential()` against the real token
  file confirmed the derivation end to end — `id_token.iat` `2026-08-03`,
  `expires_in` `5183999`, expiry ≈ `2026-10-02`, reported `EXPIRING_SOON` at
  ~11 days out. Nothing was published and no secret was printed.

Tests:
- New: `tests/test_linkedin_client.py` (33), `tests/test_linkedin_credentials.py`
  (32), `tests/test_linkedin_publisher.py` (35) — 100 tests, all offline, using
  a fake transport and a token file written under `tmp_path`.
- Extended: `tests/test_logging.py` (+2 tests for token-file redaction and for a
  missing or broken token file never breaking logging).
- Adjusted: `tests/test_state_schema.py::test_gap_in_the_migration_ledger_is_refused`
  used a literal `version=2` for its probe, which the new migration 2 made
  collide. The probe is now numbered from `SCHEMA_VERSION`; the property under
  test — that a gap in the ledger is refused — is unchanged.
- Focused: `128 passed in 1.63s` across the three new modules plus the two
  touched regression modules.
- Regression: **466 passed, 1 warning in 124.32s** (baseline 364; +102 tests;
  the warning is the pre-existing CUDA/torch driver notice).

Commit:
- `Step 5: harden LinkedIn integration for autonomous use` — the commit
  carrying this record. The subject is used instead of a hash because the hash
  cannot contain itself; find it with `git log --oneline --grep="^Step 5:"`.

Important notes:
- **Deviation — one new table was added, in `app/state/`.** Step 5's own scope
  says the integration stores nothing, and Step 6 owns persistence. Both hold
  for *publishing*: no publication, intent, run or failure is written here. But
  the credential's expiry is a fact about the world that must outlive the
  process that derived it, and there is nowhere else durable for it. The single
  table `linkedin_credential_expiry` records what was read from the credential
  and how — never what the system did. This is the one place Step 5 reaches
  outside `app/integrations/` and `Auth_handling/`.
- **Deviation — `Auth_handling/test_post.py` keeps its own publish flow.** It
  could have been rewritten to call the service. It was not, because the
  instruction for this step was to preserve the two pre-existing uncommitted
  edits in that file and because a manual tool with a person at the keyboard is
  what the file is for. Its docstring now says which path an unattended
  workflow uses. What was fixed in it: the missing timeout on both requests,
  and `load_dotenv()` by path.
- **Deviation — refresh is attempted only when already expired.** A
  pre-emptive refresh of a `refresh_token` login is normally safe, but this
  refresh path has never been verified against LinkedIn (the real credential
  has no refresh token), and trading a working credential for an unverified
  call is the wrong direction. A valid credential is never refreshed.
- **A refresh is not retried, and a mid-publish 401 is not refreshed.**
  A 401 from the publish endpoint means the token was rejected; whether a
  refresh would help is Step 6's question, and a second credential call inside
  a publish would make the publish path harder to reason about. The result is
  classified and returned.
- **Known limitation — the plan's milestone item was not executed.** `PLAN.md`
  Step 5's acceptance criterion "a real post published through the service
  returns its LinkedIn post id" is a manual, non-interactive real publish, and
  implementing this step was explicitly not to publish anything. The path is
  unchanged from the one already proven by hand (`PLAN.md` §4), and the
  automated assertion covers everything except the round trip itself. The
  round trip still has to be confirmed by hand before Step 6 relies on it.
- **Known limitation — the API version will expire.** `202607` is a literal
  that LinkedIn will retire on its own schedule; it is configuration precisely
  so that the fix is an `.env` edit rather than a code change, and it is
  recorded per attempt so the failure can be attributed. A `404` is classified
  `UNKNOWN`/human precisely because a retired version is one of the things it
  can mean.
- **`app/ingestion/`, `app/retrieval/`, `app/sources/`, `app/sync/` and
  `app/context/` were not modified.** `app/state/` gained one migration, one
  model, one enum and three store methods; `app/logging_config.py`,
  `app/config.py` and `app/paths.py` gained the entries above.
- **Nothing was published, no real credential was used, and no source was
  synchronized** while implementing this step. Known Issue #7 remains open.

### Step 4 — Build the Personal Branding Context & Evidence Layer

Status: COMPLETED

Implemented:
- Created `app/context/` — four modules behind one narrow public surface
  (`app/context/__init__.py`): `enums.py` (`EvidenceStatus`, `FreshnessState`),
  `taxonomy.py` (which section an item belongs to, and how sections and states
  rank), `models.py` (frozen result dataclasses), `builder.py` (the single entry
  point), and `__init__.py`.
- `build_context(result: RetrievalResult, store: StateStore | None = None) ->
  PersonalBrandingContext` is the whole API. It performs no retrieval of its
  own, and `retrieve_knowledge` is still the only thing that queries Chroma.
- **Sections are the corpus's own categories**, plus one for the `@source/…`
  population and one catch-all — not a new taxonomy invented here. Nine evidence
  sections (`repository_evidence`, `evidence`, `completed_projects`,
  `in_progress_projects`, `certificates`, `in_progress_courses`,
  `stories_lessons`, `audit`, `unclassified`) and three guidance sections
  (`vision_goals`, `public_positioning`, `writing_style`).
- **Provenance is structural, not conventional.** `ContextItem` is built by
  `from_document()` and carries `source`, `chunk_id` and `evidence_state`; there
  is no constructor path that produces an item without them. Retrieval `rank`
  and `score` are carried too, as provenance.
- **Ordering is deterministic and derived from the corpus.** Items in a section
  sort by `(evidence state, source, chunk id)`. Retrieval `rank`/`score` are
  deliberately **not** ordering keys — ordering by them would make a context a
  function of the strategy that produced it.
- **Evidence and guidance are separate fields**, joined only by the convenience
  accessors `evidence_items()` and `guidance_items()`. Positioning, voice and
  vision are not ranked as weak evidence; they are removed from the evidence
  field entirely.
- **Coverage is reported, including emptiness.** `SectionCoverage` (item count,
  evidence states present, unclassified count, `is_empty`) per section, plus a
  context-level `ContextCoverage` over both populations.
- **Insufficiency is a first-class outcome.** `EvidenceStatus.INSUFFICIENT` is
  set when no evidence section holds an item; guidance alone does not resolve
  it. It is a distinguishable field on the result, not an empty list a caller
  might read as success.
- **Freshness reads `sync_checkpoints` — the Option B decision.** One
  `SourceState` per population: the hand-written `data/` corpus is reported
  `tracked=False, UNKNOWN` with a note explaining that synchronization tracks
  registered sources only; a source with no checkpoint is `UNKNOWN`, a
  succeeded one is `SYNCHRONIZED`, and one whose latest attempt failed is
  `FAILED` while still exposing its last successful `last_synced_at` and
  `last_revision`.
- Added `source_name_from_key()` to `app/sync/namespace.py` — the one seam
  Step 4 required elsewhere (see *Important notes*).

Verified:
- Acceptance: all six criteria pass (checklist below).
- **The taxonomy cannot drift from the corpus.** Tests read the real `data/`
  directory tree and compare it against `EVIDENCE_SECTIONS`, and read
  `app/ingestion/metadata.py`'s `EVIDENCE_STATES` to assert every declared state
  is ranked. Adding a `data/` category or an evidence state without ranking it
  fails the suite rather than silently landing in `unclassified`.
- **Two corpus populations are separated by the namespace, not by heuristics.**
  A document under `@source/<name>/…` is filed as repository evidence by virtue
  of the namespace alone; the test asserts it could not be filed anywhere else.
- **Input order does not affect placement.** A test re-ranks the same documents
  and asserts identical section assignment and ordering — the property that
  makes the output deterministic rather than merely stable in practice.
- **Duplicates collapse by `chunk_id`**, so overlapping retrieval strategies
  (hybrid, reranked) cannot inflate a section's coverage.
- **The two failure semantics are proven, not asserted.** No documents yields an
  explicit INSUFFICIENT context; a failing collection behind the real
  `RetrievalEngine` propagates its exception instead of being converted into an
  evidence-free context, and a failing state store propagates too rather than
  degrading to "unknown freshness".
- **No timestamp is invented.** A test asserts the freshness result carries only
  values that came from a checkpoint row — no clock read, no file mtime, no
  inference from retrieval frequency.
- Milestone (`PLAN.md` §8, Step 4): a context object for a known topic contains
  the expected evidence with correct provenance, asserted against a real
  ingestion of `data/` into a temporary Chroma collection.

Tests:
- `tests/test_context.py` (25) and `tests/test_sync_namespace.py` (6) — **31 new
  tests**. Every Chroma collection, state store and corpus copy in them is
  created under `tmp_path`; none reads or writes the user's `chroma_db/` or
  `state_db/`.
- Regression: `.venv/bin/python -m pytest tests/ -q` → **364 passed**
  (333 baseline + 31 new), zero collection errors, zero failures. No existing
  test was modified, weakened, or skipped — `app/ingestion/`, `app/retrieval/`,
  `app/sources/` and `app/state/` were not touched at all, and their test
  modules are unchanged.
- `PYTHONNOUSERSITE=1` was used throughout.

Commit:
- `Step 4: build personal branding context and evidence layer` — the commit
  carrying this record. The subject is used instead of a hash because the hash
  cannot contain itself; find it with `git log --oneline --grep="^Step 4:"`.

Acceptance criteria:
- [x] Context is assembled into named sections, not one concatenated blob.
- [x] Every item retains source, chunk id, and evidence state.
- [x] Ordering is deterministic and follows the documented evidence hierarchy.
- [x] Coverage is reported per section, including empty ones.
- [x] Insufficient evidence is a distinguishable, first-class outcome.
- [x] Evidence and positioning/style remain separate fields.
- [x] Focused Step 4 tests pass (31).
- [x] The retrieval regression passes, and retrieval results are unchanged.
- [x] The full suite passes (364).
- [x] This document is updated truthfully, including the deviations below.
- [x] Step 4 is one coherent commit.
- [x] Steps 5–14 have not been started.

Important notes:
- **Freshness is derived from `sync_checkpoints`, not written during ingestion.**
  `PLAN.md` §8 offers both and requires the choice to be recorded. The
  derivation wins because `docs/implementation-status.md` already said so in
  Step 3's hand-off — *"a context layer that needs to know how fresh a source's
  evidence is should read it rather than re-derive it"* — and because a new
  metadata field would have meant re-ingesting the entire corpus to populate it,
  which is a runtime data operation rather than a step. Consequence: freshness
  is a property of a **source**, not of a document, so the hand-written `data/`
  corpus has no freshness at all. It is reported as untracked rather than
  guessed at, because synchronization owns registered sources and no checkpoint
  describes it or ever will.
- **The three documented evidence hierarchies disagree, and the disagreement is
  resolved in the open rather than silently.** `data/evidence/README.md`,
  `data/audit/README.md` §2, and `docs/architecture/rag-architecture.md` give
  three different orderings. `app/context/taxonomy.py` follows the two corpus
  documents and records every rank's basis in the code; the three decisions —
  audit conclusions rank **last** (not fourth), completed outranks in-progress,
  and positioning is **removed from the ranking rather than ranked fifth** — are
  argued in `docs/architecture/rag-architecture.md` §The hierarchy as
  implemented (Step 4). That section is the record of the deviation; this entry
  is the pointer to it.
- **`repository_evidence` is a section Step 4 added, not one the corpus
  defines.** The corpus is hand-written Markdown; the `@source/<name>/…`
  population is 29 repositories. They are not the same kind of evidence — the
  first is a curated claim about the user, the second is the user's actual work
  — and the corpus has no category for the second because the corpus predates
  it. Ranking it first follows `data/evidence/README.md`'s own first principle
  (primary evidence over description).
- **Two state ranks are additions the corpus does not state.** A document with
  no declared `evidence_state` sorts after every declared state but **before**
  `STALE` (unknown is weaker than a positive claim, but stronger than a
  known-invalid one), and `STALE` sorts last. "Is it declared?" and "does it
  rank above unclassified?" are deliberately different questions: `is_declared_state()`
  is membership of the vocabulary, and `STALE` is declared while ranking last.
- **Ordering ignores retrieval rank and score on purpose.** Both are carried on
  every item, but using them as sort keys would make the assembled context a
  function of which strategy ran — the same corpus would produce a different
  context under `vector` than under `reranked`, and Step 9's verification would
  be checking against an artifact of retrieval rather than of the evidence.
- **An item belongs to exactly one section, and guidance is matched twice.**
  Classification checks `category` first and falls back to `document_type`, so a
  positioning document filed under an unexpected category is still recognised as
  guidance. A test pins both paths.
- **`build_context` catches nothing.** A retrieval failure is not converted into
  an insufficient-evidence context; the two are different facts and only one of
  them means "the user has nothing to say about this". Silently degrading would
  turn an infrastructure outage into a reason not to publish.
- **One seam outside `app/context/` was required: `source_name_from_key()`.**
  The context layer has to know which registered source a `@source/…` key
  belongs to, and the only other way to get it was to re-spell the namespace
  prefix and separator inside `app/context/` — a second copy of a correctness
  device, free to drift from the original. The function was added to
  `app/sync/namespace.py` beside the `is_source_key`/`source_key` pair it
  inverts, it is total (returns `None` rather than raising, because it runs over
  metadata that came from a retrieval result), and it changes no existing
  behaviour. `tests/test_sync_namespace.py` pins both the new accessor and the
  published guarantees Step 2 and Step 3 already relied on. Nothing else in
  `app/sync/`, `app/ingestion/`, `app/retrieval/`, `app/sources/` or
  `app/state/` was modified.
- **No new persistence, and no schema change.** `data/` is not restructured, no
  `PersonalProfile` abstraction replaces it, and no metadata field was added to
  ingestion. Step 4 reads existing rows and returns a value object.
- **Nothing was published, no LinkedIn code was touched, and synchronization
  was not run.** Known Issue #7 remains open: no real source has a checkpoint
  row, so in the real workspace every registered source currently reports
  `UNKNOWN` freshness — which is the honest answer, and the reason the
  untracked/unknown distinction was built rather than assumed away.

### Step 3 — Build Incremental Knowledge Synchronization

Status: COMPLETED

Implemented:
- Created `app/sync/` — eight modules behind one narrow public surface
  (`app/sync/__init__.py`): `enums.py` (`ChangeType`, `RevisionKind`,
  `SyncStatus`, `SyncErrorCategory`), `namespace.py` (how a source file is
  named in Chroma), `models.py` (`ChangedPath`, `SourceSyncResult`,
  `SyncRunResult`), `revision.py` (what revision a source is at, and what
  changed), `relevance.py` (the relevance policy and the rename policy),
  `candidates.py` (changed paths → files to index, keys to remove),
  `synchronizer.py` (orchestration, checkpoints, failure isolation), and
  `__init__.py`.
- **The pipeline is called, never reimplemented.** `app/ingestion/pipeline.py`
  gained one seam — a candidate mode — and one indexing loop. Corpus mode
  (`candidates is None`) is byte-for-byte its former behaviour. There is still
  exactly one place where a file becomes vectors, one place that hashes, and
  one stale-removal mechanism.
- **Revision resolution** (`revision.py`): a git source resolves to a commit
  via `rev-parse --verify --quiet <ref>^{commit}`; a filesystem source, or a
  git repository with **no commits** (the registry contains one:
  `exit-project-studyflow`), resolves to a content digest — a sha256 over
  `(relative path, sha256(file bytes))` for every admitted file. The digest
  includes the path, deliberately: without history, a file renamed with
  unchanged bytes must still register as a change.
- **Change detection** uses git's own `diff --name-status -M -z` with
  `core.quotepath=false`, so added / modified / deleted / renamed / copied all
  come from the version control system rather than from filename heuristics.
  The `-z` token stream is parsed strictly: a truncated stream is an error, not
  a smaller change set.
- **Relevance** reuses Step 2's matcher and its deny-wins rule verbatim
  (`decide()` names the vetoing exclusion and its stated reason). Every changed
  path carries its verdict into the result, including the ones rejected.
  No LLM is involved anywhere in relevance.
- **Checkpoints** live in the Step 1 store, in `sync_checkpoints`, and only
  `record_sync_success` ever sets `last_revision`. A revision with no relevant
  paths still advances the checkpoint (the revision *was* processed; leaving it
  would re-diff the same commit for ever), while a **failed** source never
  advances — the next run retries exactly the range that failed.
- **Source keys are namespaced** as `@source/<name>/<relative path>`. The
  corpus and 29 sources share one collection, and the namespace is what makes a
  scoped stale-removal sweep unable to reach another source's — or the corpus's
  — keys.
- Added `SyncError`, `SourceUnavailableError` and `GitError` to
  `app/errors.py`; `load_all(strict=True)` to `app/ingestion/loader.py` (a
  candidate set is a *claim about what changed*, and quietly indexing part of
  one would let a checkpoint advance past a file that never reached the index).

Verified:
- Acceptance: all 20 criteria pass (checklist below).
- **Milestone (`PLAN.md` §18): two consecutive synchronizations of an unchanged
  source leave Chroma byte-identical.** Proven twice — as a test over a
  temporary repository, and again outside the suite by hashing every stored row
  (id, document, metadata, vector) with the **real** `all-MiniLM-L6-v2`
  embeddings: `b7ee94ee…` across three consecutive syncs, `46b8f232…` after a
  real change settled, with the checkpoint unmoved on each no-change run. The
  comparison is over stored content, not log output.
- **Nothing is embedded or written when nothing changed.** A no-change sync
  performs no pipeline call, no Chroma read, and no state write at all — not
  even a fresh timestamp, which is asserted against the checkpoint row.
- The ingestion regression is genuinely untouched: `app/ingestion/` still
  produces the same ids, metadata, chunking and stale-removal behaviour for
  `data/`, and the pre-existing test modules for ingestion and retrieval were
  not modified — only `tests/conftest.py`, additively.
- **Self-ingestion protection holds at three layers**, proven against the live
  monorepo shape (a source at an ancestor of this application): the registry's
  load-time probes, the structural guard during the walk (a symlinked path into
  the application is refused *while descending*, so `.venv/` and `chroma_db/`
  cost nothing), and `assert_path_admissible` again at the moment a candidate
  is built.
- Failure isolation: one source's ingestion failure, unavailable path, guard
  refusal, or unrecognised exception is recorded structurally
  (`phase='sync'`, a typed `error_category`, `retryable`,
  `requires_human_intervention`, one row per source per category counting
  occurrences) and the run continues to the next source.
- Recovery: an interrupted run leaves the checkpoint behind, and the retry
  produces a collection **byte-identical to a clean first-time synchronization**
  of the same final state — compared, not asserted.

Tests:
- `tests/test_sync_revision.py` (26), `tests/test_sync_relevance.py` (21),
  `tests/test_sync_pipeline.py` (21), `tests/test_sync_synchronizer.py` (26),
  `tests/test_sync_integration.py` (13) — **107 new tests**. Every git
  repository, Chroma collection and state store in them is created under
  `tmp_path`; none reads the user's workspace.
- Regression: `.venv/bin/python -m pytest tests/ -q` → **333 passed** (226
  baseline + 107 new), zero collection errors, zero failures. No existing test
  was modified, weakened, or skipped: `tests/conftest.py` gained 152 lines of
  purely additive fixtures (a temporary-git-repo factory, a source factory, a
  temporary state store and Chroma collection, a recording stand-in for the
  pipeline) with no line removed, and the four pre-existing test modules for
  ingestion and retrieval are untouched.
- `PYTHONNOUSERSITE=1` was used throughout.

Commit:
- `Step 3: add incremental knowledge synchronization` — the commit carrying
  this record. The subject is used instead of a hash because the hash cannot
  contain itself; find it with `git log --oneline --grep="^Step 3:"`.

Acceptance criteria:
- [x] A sync on an unchanged source performs no embedding work and no Chroma
      writes — and writes nothing to the checkpoint either.
- [x] The first sync of a source with no checkpoint ingests its full admitted
      inventory.
- [x] Changed files are detected, and only they are submitted.
- [x] A deleted file's content leaves Chroma through the pipeline's own
      removal path — there is no second deletion mechanism.
- [x] Renames are handled by the tested policy below, verified against the
      collection rather than against the plan.
- [x] A checkpoint advances only after a fully successful synchronization.
- [x] An interrupted run is safe to re-run, and converges on the state a clean
      run would have produced.
- [x] A git failure for one source does not block the others.
- [x] A `COMPLETED` source with new relevant commits is detected, flagged in
      the result, and still ingested in full.
- [x] Relevance rules are enforced with Step 2's matcher, exclude always
      winning over include.
- [x] The existing pipeline remains the indexing implementation.
- [x] No second ingestion pipeline exists.
- [x] Self-ingestion protection is intact, at all three layers.
- [x] Focused Step 3 tests pass (107).
- [x] The ingestion regression passes.
- [x] The full suite passes (333).
- [x] The milestone proves no Chroma mutation across consecutive syncs.
- [x] This document is updated truthfully, including the deviations below.
- [x] Step 3 is one coherent commit.
- [x] Step 4 has not been started.

Important notes:
- **The rename policy purges the old path on *every* rename, including an
  exact one.** `PLAN.md` §8 warns against a blind delete-then-add because ids
  are content-addressed and an identical-content rename can reuse them. The
  policy implemented is: purging the old key happens **first**, then the new key
  claims the same ids — which leaves the chunk count unchanged and the content
  retrievable under the new path. Skipping the purge for an exact rename would
  leave correctness resting on Chroma accepting an `add` over an existing id,
  which was verified to work but is an undocumented convenience. Git's
  similarity score is still read and reported (`ChangedPath.is_exact_rename`),
  and a test asserts on it, but nothing acts on it. This is a deliberate
  deviation from the wording in `PLAN.md` §8, in the direction of not depending
  on unspecified behaviour.
- **Every removal precedes every addition — a rule the scope sweep had to
  learn.** The pipeline's `purge` was already ordered that way; the *scoped
  sweep* was not, and an integration test caught the consequence: a full resync
  submits a renamed file under a new key holding the old key's content address,
  so a sweep running after indexing deleted the chunks the new key had just
  claimed, and that cycle then advanced a checkpoint — recording the loss as
  success. The sweep now runs before indexing. This was found by a test, not by
  reasoning, and it is pinned by a regression test.
- **Two admitted files with identical content cannot both be indexed.** They
  share one content address, and Chroma 1.5.9 does not reject a duplicate id —
  it silently overwrites. Left alone, which file the index attributes the
  content to would depend on which run happened last, so the two would trade
  places on every full rescan. The first candidate submitted keeps the address
  (sorted path order, on the full resync where collisions actually arise), the
  second is skipped, counted (`files_skipped_duplicate_content`) and reported
  with both keys. `PLAN.md` does not mention this case; it is a property of
  content-addressed ids meeting a real workspace rather than a curated corpus.
  Corpus mode is unaffected and keeps the behaviour it has always had.
- **The completed-project review flag is reported, not persisted.**
  `sync_checkpoints.last_outcome` is CHECK-constrained to `SUCCEEDED`/`FAILED`
  by Step 1, so persisting a third state would need a schema migration, which is
  outside Step 3's boundary. The flag is therefore observable in the result
  (`review_signal`, `plan.disposition == REVIEW_REQUIRED`) and, for failures,
  in `operational_failures.requires_human_intervention`. Synchronization never
  writes `source_lifecycle`, and a test asserts that.
- **The review signal fires on changes since the last processed revision, never
  on a first sync.** Otherwise the ~20 `COMPLETED` sources would raise a signal
  storm the first time they were ever synchronized, which is how a review gate
  stops being a gate. "A `COMPLETED` source with new relevant commits is
  flagged" holds exactly.
- **The scoped sweep is enabled only for a full resync.** A sweep's keep-set is
  a source's entire inventory, so passing it for a diff would delete every file
  the revision did not happen to touch. One consequence is worth stating: editing
  the registry to *narrow* a source's includes does not retract already-indexed
  content until that source next does a full resync (first sync, rewritten
  history, or a content-digest source whose digest changed).
- **The failure path is itself raise-proof.** An unrecognised exception is
  recorded as `UNEXPECTED` rather than escaping, and building a failure result
  no longer depends on the source's declaration being interpretable — a source
  declaring a lifecycle outside the four known values is reported as requiring
  review instead of aborting the run over the other 28. (Through the registry
  that cannot happen: the loader refuses the value at load time.)
- **`app/ingestion/` was modified in two places, and only where a seam was
  required**: candidate mode in `pipeline.py`, and `strict` loading in
  `loader.py`. No chunking, hashing, embedding, metadata or stale-removal logic
  was changed, and the corpus path was proven unchanged by its existing tests.
  One additive change is worth naming precisely rather than calling "no change":
  `run_ingestion()`'s stats dict gained `files_skipped_duplicate_content`, which
  is always present and always `0` in corpus mode. The indexing behaviour and
  the printed CLI report are unchanged.
- **Nothing was scheduled, notified, or given a CLI.** Step 3 is a library;
  Step 11 owns entry points and Step 12 owns scheduling. `sync_all()` iterates a
  registry and nothing else — there is no directory walk, so an unregistered
  repository cannot become synchronization input, which is a structural
  guarantee rather than a filtering one.
- **The corpus has not been resynchronized.** Step 3 delivers the mechanism;
  running it against the 29 real sources is a runtime operation that writes to
  the real `chroma_db/`, and it was not performed as part of this step. See
  Known Issue #7.

### Step 2 — Define the Personal Knowledge Source Registry & Project Lifecycle

Status: COMPLETED

Implemented:
- Completed the workspace inspection **before** writing the registry, at full
  depth, across all roots plus `~/DataBases` (found by following the corpus's
  own source references; it is in no root `PLAN.md` declares). Every candidate
  was characterised by exact path, repository-ness, commit count, authorship,
  dominant content type, and classification. Recorded in
  `docs/architecture/source-registry.md`.
- Wrote `sources.yaml` — the committed registry: **29 sources**, **9 declared
  workspace roots**, **10 `not_registered` entries**, and 3 named include
  profiles. Every `local_path` was verified to exist; every `ref` was verified
  to resolve; every `repo_identity` was checked against the real git remote and
  sanitized.
- Created `app/sources/` — six modules with one narrow public surface:
  `enums.py` (`SourceType`, `SyncDisposition`, `SyncPriority`), `patterns.py`
  (the matcher), `guard.py` (the self-ingestion guard), `models.py`
  (`SourceDefinition`, `ExcludeRule`, `Registry`, `NotRegisteredEntry`),
  `lifecycle.py` (`SyncPlan`, `StatusReviewSignal`), and `registry.py` (loading,
  parsing, validation, tree scanning).
- **Inclusion model:** include is a floor, exclude is a veto, and the veto
  always wins (deny-wins, not last-rule-wins). Directory patterns reach the
  files beneath them and respect component boundaries (`Agent/` does not match
  `AgentX/`). Character classes are rejected rather than approximated, because
  an approximated exclusion is one that excludes nothing and reports nothing.
- **Self-ingestion guard, two layers:** `is_protected()` answers structurally
  for any path without consulting the registry and resolves symlinks first;
  registry validation checks a set of concrete protected probe paths (`.env`,
  the token file, `chroma_db/`, `state_db/`, `app/`, `PLAN.md`, `sources.yaml`,
  and `data/` — the corpus is a digest of the sources and must not become its
  own evidence) and fails the load if any pattern admits one.
- **Lifecycle model:** `ACTIVE · PAUSED · COMPLETED · PLANNED`, reused from
  `app.state.enums.LifecycleState` rather than redefined, so the declaration
  vocabulary and the transition vocabulary cannot drift apart. `SyncDisposition`
  has **no `skip` member** and every `SyncPlan` carries `ingest=True`, making
  "ignore forever" unrepresentable rather than merely discouraged.
- Added `RegistryError` to `app/errors.py`; `SOURCES_FILE` to `app/paths.py`;
  pinned `PyYAML` in `requirements.txt` (it was installed only as a transitive
  dependency of the LangChain stack, so the registry could have stopped loading
  if that stack dropped it).

Verified:
- Acceptance: all nine criteria pass, each checked programmatically against the
  committed registry (see *Acceptance criteria* below).
- **The application cannot ingest itself**, proven by running the real
  `sources.yaml` patterns against the guard's probes: no source admits any path
  inside the application.
- **Missing or invalid input is always reported, never skipped.** 16 distinct
  refusal cases are tested: nonexistent path, declared type not matching reality
  in both directions, missing `repo_identity`, missing `ref`, revision fields on
  a filesystem source, empty include, an exclusion with no reason, a malformed
  pattern, an unknown lifecycle value, duplicate names, a plain declared root
  taken as a source, an unaccounted-for nested repository, an unexcluded
  virtualenv, a `not_registered` path that is also a source, and a credential in
  a `repo_identity`.
- **The registry's own enumerations are grounded, not asserted.** Every count in
  `sources.yaml` was read from git: commit counts for all 25 git sources, and
  authorship for the disputed ones — `AirBnB_clone_v4` 1 of 235 the user's,
  `AirBnB_clone_v3` 17 of 147, `_AirBnB_clone_v2` 34 of 129, `simple_shell` 53
  of 101, `Style_Finder` 0 of 4. Two asserted refs were **wrong and corrected**
  during verification (`alx-system-engineering-devops` and
  `alx-higher_level_programming` are on `master`, not `main`).
- The excludes are proven rather than assumed: a plain `find` reports 36,082
  `.py` files under `~/LLMs/IBM`; the same walk through the registry's own
  matcher reports 93.
- Milestone: registering a real repository and resolving its HEAD works — all
  25 git sources load, validate, and resolve their declared ref from the
  real filesystem.
- No recursive root scanning exists anywhere: the only directory walk in `app/`
  is the pre-existing one over `data/` in `app/ingestion/loader.py`. The
  tree scan in `app/sources/registry.py` walks a *named source* under its own
  excludes, to prove nothing is unaccounted for inside it — it never discovers
  sources.

Tests:
- `tests/test_sources_registry.py` — **76 new tests**: pattern admission and its
  boundaries, the self-ingestion guard (including a symlink that would otherwise
  launder access), the committed registry itself, every validation refusal,
  lifecycle dispositions, credential sanitization, virtualenv detection, and
  nested-repository scanning.
- Regression: `.venv/bin/python -m pytest -q` → **226 passed** (150 before this
  step + 76 new), zero collection errors, zero failures. `app/ingestion/` and
  `app/retrieval/` are byte-for-byte untouched, as are their four test modules.
  No existing test was modified, weakened, or skipped.
- `PYTHONNOUSERSITE=1` was used throughout.

Commit:
- `Step 2: define the personal knowledge source registry` — the commit carrying
  this record. The subject is used instead of a hash because the hash cannot
  contain itself; find it with `git log --oneline --grep="^Step 2:"`.

Acceptance criteria:
- [x] Declared roots are treated as places to inspect, never as sources to
      ingest — enforced by validation and proven by test.
- [x] The workspace inspection is completed and its results recorded before the
      registry was written (`docs/architecture/source-registry.md`).
- [x] The registry names exact sources; no recursive root scanning occurs
      anywhere in the codebase.
- [x] **The application cannot ingest itself**, proven by test against the real
      `sources.yaml`.
- [x] A missing or invalid path is reported, never silently skipped — 16
      refusal cases tested.
- [x] Both git-backed and filesystem-backed sources are supported, including a
      repository with zero commits (`exit-project-studyflow`) and plain
      directories (`kubernetes-lab`, `fastapi-shipment-api`, …).
- [x] Include/exclude rules are explicit per source, each exclusion carrying a
      reason.
- [x] Lifecycle is explicit, persisted, and never inferred from inactivity.
- [x] A `COMPLETED` source with new commits produces a review signal.

Important notes:
- **`PAUSED` is registered by no source.** The lifecycle vocabulary has four
  members because the corpus uses all four, but the inspection found no project
  the user has paused. `PAUSED` remaining unused is a finding, not an omission —
  and it stays distinct from *absent*, because "paused" and "never heard of it"
  are different claims.
- **One rule in `PLAN.md` was sharpened by the workspace, in the permissive
  direction.** "A declared root is never a source" cannot hold as written:
  `~/LLMs/IBM`, `~/LLMs/AI_Agents` and `~/Portfolio` are each both a declared
  root and a single git repository, and a repository is one revision history —
  exactly what a source is. The rule enforced is therefore that a **filesystem**
  source may never be a declared root, which is the actual hazard (sweeping a
  loose directory). A git source that is not really a repository is caught by a
  separate check, so the two rules compose rather than overlap.
- **`~/DataBases` is a root the roadmap does not declare.** It was added because
  the corpus asserts MongoDB/PyMongo evidence and cites a path outside every
  declared root. Adding a root is a user-facing decision, so `~/DSA-Python-LeetCode-130`
  — a real 7-commit repository found during the inspection — was recorded in
  `not_registered` instead of silently adopted.
- **14 repositories carry a live token in their local git remote URL.** This
  makes `sanitize_repo_url()` a requirement rather than a precaution: the
  registry is committed, remotes are not. No token value appears in
  `sources.yaml`, and validation fails the load if one would.
- **Two repositories are on `master`, not `main`.** Both were found by
  verification after being written as `main` by assumption — which is precisely
  the failure mode the "inspect, do not invent" instruction exists to prevent.
- **Virtualenvs are detected structurally**, by `pyvenv.cfg`, not by name: this
  workspace holds `.venv`, `venv`, `my_env` and `fastapi_venv` across **17
  environments totalling ~17 GB**.
- One dead function (`find_nested_repositories`) was removed rather than left as
  unused public API; `scan_source_tree` is the single entry point and is what
  validation calls.

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
Step 11 — Build the 24h Knowledge-Sync and 8h Branding Workflows
Status: NOT STARTED
```

The full specification — reason, scope, implementation approach, tests, failure
handling, and acceptance criteria — is in `PLAN.md` §8, Step 11. It is not
duplicated here.

What Step 10 leaves on the table for it:

- **There is now a caller, and it returns a value rather than acting.**
  `BrandingAgent.run(context)` returns exactly one `AgentResult` on every path:
  `is_publishable`, or `DO_NOT_PUBLISH` with a `NoPublishReason`, or
  `DO_NOT_PUBLISH` with an `AgentFailure`. The workflow's job is to branch on
  that value, not to re-derive it.
- **The three workflow outcomes already have their discriminators.**
  `AgentResult.failed` is true only when the *reasoning* failed, and is
  deliberately distinct from `not is_publishable` — so `DO_NOT_PUBLISH` (a
  success, exit 0, no notification), `WORKFLOW_FAILED` (a reasoning failure, or
  a `GenerationError`/`VerificationError` that this layer does not catch and
  does not swallow) and `REQUIRES_HUMAN_INTERVENTION` (`HistoryDigest.
  unresolved_ambiguity`, `RecoveryReport.blocked`) are all already answerable
  from the objects the layers below return.
- **Recording is deliberately not done, and `to_record()` is the seam.**
  `AgentResult.to_record()` is JSON-compatible, carries no clock and no
  environment, and embeds Step 9's own verification record. `PLAN.md` Step 10
  keeps the write above this layer — *"or the system could forget to record"* —
  so the workflow writes it, through the store, into a schema that does not have
  the column yet (Known Issue #14).
- **Notification is exposed, not sent.** A reasoning failure arrives as an
  `AgentFailure(category, detail)` and nothing in `app/agent/` imports
  `app.notify` or `smtplib`. `PLAN.md` Step 11 owns the classification of the
  outcome and the decision to notify, and Step 7's `NotificationService` is
  already built and uncalled (Known Issues #10 and #11).
- **One publication per run is a property, not a check the workflow has to
  remember.** `AgentResult` carries a single optional `proposal` and a single
  optional `draft`, the loop returns at the first passing verification, and the
  Agent holds no publisher at all — so `MAX_PUBLISHES_PER_RUN` is backed by the
  shape of the result *and* by the database's `ux_publish_intents_run` (Step 6).
  `PLAN.md` Step 11 still asks the workflow to enforce `0 or 1`, which is the
  third layer of the same guarantee rather than a duplicate of it.
- **The retrieval strategy is a recommendation the workflow has to act on.**
  `AgentProposal.strategy` names the strategy for a *fresh* pass at the chosen
  topic, drawn from the vocabulary the caller passed as `strategies=`. The Agent
  cannot retrieve, so nothing has yet made a second pass at the topic — that is
  the workflow's call, and passing `strategies=STRATEGIES` is what makes the
  choice meaningful.
- **Nothing here is wired, and nothing is scheduled.** Step 10 delivered a
  library: no CLI, no entry point, no run record, no lock. The real model call
  is still ahead of the project (Known Issue #5), so the first real branding run
  will report a configuration failure rather than a post, and Step 11 must not
  be the step where that mismatch is worked around in code.

---

## Known Issues / Blockers

Verified conditions that block or complicate implementation. Issues #1 and #3
were resolved (in Steps 0 and 5) and are kept for the record; the rest are open.

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

The Step 2 inspection confirmed the drift and extended it — `~/LLMs/AI-Agents`
(for `AI_Agents`), `~/Quizey_V2` (for `~/Quizey/Quizey_V2`), `~/FastAPI/app`
(for `~/FastAPI/course_practical_app`), and two paths that are simply gone
(`~/DevOps/Packt-DevOps-Bootcamp`, `~/LLMs/llm-env`). The full comparison is in
`docs/architecture/source-registry.md`.

Step 2 made these paths **declared and checkable** rather than prose. Step 3
built the mechanism that resynchronizes them, and verified it end to end
against temporary repositories — but **the real corpus is still stale**, because
synchronizing 29 real sources is a runtime operation, not an implementation
step. See Issue #7. The corpus still carries the stale revisions.

### 3. ~~Uncommitted working-tree changes exist in `Auth_handling/`~~ — RESOLVED in Step 5

`Auth_handling/test_credentials.py` and `Auth_handling/test_post.py` carried
**uncommitted** edits that resolve the token file relative to `__file__`.
`linkedin_oauth_setup.py` — the script that *creates* the token — still used a
CWD-relative literal path, so it wrote the token where the two readers would not
look.

**Resolved** by Step 5. All three scripts now resolve the token file relative to
their own location, `app/paths.py` defines that file once for the application,
and an AST-based test fails if any of the three drifts again. The two
pre-existing edits were preserved byte-for-byte and are now committed as part of
Step 5.

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

Not caused by Step 0 and not a Step 0 blocker. It was recorded as a blocker for
**Step 8** (grounded post generation), which genuinely requires an LLM. Fix is a
configuration change — put a valid OpenRouter key in `.env` — not a code change.

**Still open after Step 8, and Step 8 was built without touching it.** Generation
uses the existing boundary exactly as it stands — `config.require_openrouter_key()`
and `config.OPENROUTER_BASE_URL`, the same client `app/retrieval/multi_query.py`
builds — and no credential was invented, substituted, defaulted around, or
written into the repository. What Step 8 adds is the *reporting*: a missing key
raises `GenerationError` with
`GenerationFailureCategory.CONFIGURATION` and `requires_human_intervention` true,
naming `OPENAI_API_KEY` as the variable to set, because a wrong credential is
something a retry cannot fix and a person can. The first real generation
therefore fails loudly and correctly instead of producing a post. See also
Known Issue #13.

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

### 7. Synchronization has never been run against the real 29 sources

Step 3 implements and verifies incremental synchronization, but the first real
pass has **not** been performed. Every test — including the milestone — runs
against temporary repositories under `tmp_path` by requirement, and no
registered source has a checkpoint row yet.

This is deliberate, not an omission. A real pass writes to the user's own
`chroma_db/` and inserts rows into `state_db/`, which is a runtime data
operation rather than an implementation step; and `PLAN.md` Step 3 scopes out
entry points and scheduling. The three things a first real pass will need, none
of which exist yet:

1. **An entry point.** `sync_all()` is a library function with no CLI
   (`PLAN.md` Step 11 owns workflow entry points).
2. **Acceptance of the first-pass cost.** With no checkpoints, the first pass is
   a full resync of 29 sources — the one pass whose cost is proportional to the
   whole workspace rather than to what changed. Step 2 measured the shape of
   that workspace (36,082 `.py` files under `~/LLMs/IBM` before excludes,
   93 through the registry's matcher, 17 virtualenvs, ~17 GB).
3. **A decision about `data/`'s stale revisions (Issue #2).** Synchronizing the
   sources does not by itself rewrite the hand-written corpus documents that
   cite dead paths and stale revisions; those are `data/` files, and how the
   corpus reconciles with its sources is a question for the Context layer.

Until then, `chroma_db/` holds the corpus as it was ingested in Step 0.

### 8. Near-duplicate detection is implemented but not yet active

Step 6 builds the near-duplicate check and tests it, but the check only runs
when a `PublishingService` is constructed with an embedder. No entry point
supplies one yet: the real embedder belongs to the retrieval stack, and Step 6
is forbidden from reaching into it (`PLAN.md` §6.1 — the publishing layer must
not touch the knowledge layer at all, which is asserted by a test).

Consequence: until Step 11 wires the embedder into the workflow that calls the
service, a real run enforces the **exact** and **overuse** checks only. Those
two are the ones that read stored state; the near check is the one that needs a
model. The check is not silently skipped — a detector without an embedder
reports `can_detect_near_duplicates == False` and does not claim a comparison it
did not make — and an embedder that *is* configured and then fails refuses the
publish rather than proceeding unchecked.

### 9. The real publish through the service has never been performed

The wrapped publish path has been verified against the real API exactly once
**before** this roadmap, through `Auth_handling/` (Step 5 baseline). Since
then it has been exercised only against fake transports, because no
implementation step may publish: Step 6's acceptance criteria require fakes and
forbid a real post.

So `publish_to_linkedin()` and the whole Step 6 state machine have never
completed a real round trip together. The first real publish through
`PublishingService` — the one that would leave a genuine `publications` row and
a genuine `linkedin_post_id` — is a deliberate manual act, and it is the first
thing worth doing before Step 10 hands publishing to an autonomous Agent.

---

### 10. ~~Nothing calls the notification service yet~~ — RESOLVED in Step 11

Step 7 built the alerting path and proved it works end to end through a fake
transport, but no workflow invoked it. Step 11 wires it: both workflows call
`notify_run()` exactly once on `WORKFLOW_FAILED` and on
`REQUIRES_HUMAN_INTERVENTION`, and never on `DO_NOT_PUBLISH`; the branding
workflow additionally calls `notify_publication()` exactly once for a post
that went out (the one report the failure path cannot cover, since a publish
terminates `DO_NOT_PUBLISH`). A phase failure inside the Agent is wrapped by
`run_phase()` so it notifies regardless. What remains is Known Issue #11: no
email has ever actually been sent.

---

### 11. No email has ever actually been sent

`SMTPTransport` is exercised only against a fake that replaces `smtplib`'s
client classes, and every other test uses a capturing fake. No message has left
this machine, and the real path — a Gmail app password, STARTTLS on 587, a
sender that matches the account — has never run.

The configuration half is now in place: the required settings (`PLAN.md` §12.2
open item C) are present in the local `.env`, so the notifier is no longer
recorded as an `configuration` delivery failure by default. What remains is the
first real delivery, which is a deliberate manual act — the same shape as the
first real publish (Known Issue #9). Until it is taken, "notifications work"
rests on fakes in both directions.

*(This entry read "`SMTP_*` is unset in `.env`" until the settings were added;
the status document is corrected rather than left asserting a condition that is
no longer true.)*

---

### 12. A credential that expires between runs is still only discovered at publish time

Step 5 created `linkedin_credential_expiry` and wrote it on every attempt, and
Step 6 carries the integration's warning on a report that **succeeded** —
`PublishReport.expiry_warning` reaches a caller for *this* call. The cross-run
half is still missing: nothing reads the recorded expiry, so a credential that
dies while no run is executing is discovered by the next publish rather than
before it — which is the one place a warning arrives too late to be useful.

Step 6 recorded this as outside its contract and left it where it found it; this
entry was carried in the Step 7 handoff notes and is preserved here rather than
dropped when those notes were replaced. It is a Step 11 concern (a workflow that
checks before it publishes), not a Step 7 or Step 8 one, and it is written down
so it is not mistaken for done.

---

### 13. No real model call has been made, by the generator or by the Agent

**Partly resolved in Steps 10 and 11.** `app/generation/` now has its first caller:
`BrandingAgent.run()` builds a `GenerationRequest` from a resolved proposal and
calls `PostGenerator.generate()`, and on a `REVISE` verdict it re-drives it with
Step 9's `revision_notes()` as writing constraints. `app/agent/llm.py` adds a
second real client (`LlmContentReasoner`, the Agent's OpenRouter-backed reasoner).
`PLAN.md` Step 10's decision path and Step 9's revision loop both exist now.
Step 11 adds the workflow that invokes `BrandingAgent.run()`, branches on its
`DO_NOT_PUBLISH`, and publishes at most one verified post — so the call chain
from entry point to model is complete in structure.

What remains: **nothing has still ever been generated for real, and no real
model call of any kind has been made.** Which workflow invokes
`BrandingAgent.run()`, what it does with a `DO_NOT_PUBLISH`, and when it runs at
all are Step 11's — the same shape as the notification service (Known Issue #10)
and the publishing service (Known Issue #9). Recorded so that "generation
exists" is not read as "a post can be produced today".

The second half is Known Issue #5 meeting two producers. Every Step 8, 9 and 10
test injects a fake model, so neither real OpenRouter client has ever been
constructed against a real endpoint — and the first genuine call will fail with a
`CONFIGURATION` failure naming the variable to fix, because the key currently in
`.env` belongs to the OpenAI platform rather than to OpenRouter. That outcome is
the designed one for an unconfigured model: the failure is categorized, it says
what a person has to do, and nothing is invented to cover it. Correcting the key
is a configuration change in `.env` — never a code change, and never something
this repository invents a value for.

---

### 14. Verification results are produced but not yet persisted

`PLAN.md` Step 9 lists, under Data/state, that **outcomes are persisted with the
publication record**. The verification layer produces exactly that record —
`VerificationResult.to_record()` returns plain JSON-compatible values with the
outcome, every finding, the cited evidence by provenance, the unresolved labels
and the judge that produced the advisory half — and **nothing writes it**.

Two separate gaps, both recorded rather than papered over:

- **The write path does not exist.** `app/state/schema.py` has no column for a
  verification record and no verification table, so persisting one would mean a
  schema migration *plus* a change to `app/publishing/` — and Step 9's brief
  puts both out of bounds ("do not modify … publishing … unless a minimal seam
  is strictly necessary"). Adding a nullable column the only writer never
  populates would be a seam that carries no data. The persistence belongs to
  Step 11, which is the step that writes publication records; `to_record()` is
  the seam it will consume, which is why the shape is defined and tested here.
- **Nothing calls the verifier at all.** Same shape as Known Issues #9, #10, #12
  and #13: the layer exists, is exercised by its own tests, and has no caller.
  Wiring it into the decision path and the revision loop is Step 10 (the Agent)
  and Step 11 (the workflows).

Updated in Step 10: **the verifier now has its first caller.**
`BrandingAgent.run()` calls `EvidenceVerifier.verify()` on every draft it
produces, and the resulting `VerificationResult` — the one that granted a
`PUBLISH`, or the one that refused it — is carried on `AgentResult.verification`
and embedded in `AgentResult.to_record()` under the `"verification"` key. So
there are now two records waiting for a writer, and they nest: the Agent's
outcome and, inside it, Step 9's verification. **Still nothing writes either.**
The gap above is unchanged and is now entirely Step 11's.

Updated in Step 11: **partly resolved, by a deliberate narrowing.** The
workflow persists every fact `PLAN.md` Step 11 asks for — the run outcome on
`workflow_runs`, every phase transition in the new `workflow_phases` table,
the structured failure with its phase, and (via the Step 6 service) the
write-ahead intent, the publication and its evidence references. The full
nested JSON (`AgentResult.to_record()` with the verification inside) is
carried on the returned `WorkflowResult.detail`, not in a new column: a
column no query reads would be dead schema, and every queryable fact the
record contains already lives in a table. If Step 13's evaluation needs the
claim-level record after the fact, that is the step that reads it, and the
column belongs to that step.

Recorded so that "the verifier passes" is not read as "verification has been
persisted for a post that was published" — no post has been verified, because no
post has been generated for real (Known Issue #13).

---

### 15. No linter is configured, so the new packages were not lint-checked

Discovered in Step 10 while looking for one. There is no `ruff`, `flake8`,
`pyflakes` or `pylint` in the project-local `.venv`, no `[tool.ruff]` or
`[flake8]` section in `pyproject.toml` (there is no `pyproject.toml`),
`setup.cfg` or `Makefile`, and no lint step anywhere in the repository. So
"the code is clean" rests entirely on the test suite and on review.

This is recorded rather than quietly worked around: adding a linter would be a
change to the build and its dependencies, which is not a Step 10 seam. It is not
a blocker — the focused and regression suites are the actual gate, and every
Step 10 module was read against the house style — but the exact class of defect a
linter catches (an unused import, a shadowed name, an unreachable branch) is
currently caught only if a test happens to exercise it. One real instance was
found and fixed by hand in Step 10: an unused module-level constant left behind
in `tests/test_agent.py`.

A follow-up decision is needed on whether a linter belongs in this repository at
all, and if so which one and at what step. It is not assigned to Step 11.

---

### 16. A recycled pid can make a stale lock look live

Step 12 reclaims an expired lock only after its owner pid is shown to be
gone. If that pid has been recycled by an unrelated long-lived process, the
liveness probe reports alive and invocations keep being rejected with the
lock untouched.

The failure direction is conservative: a missed run, never two live owners.
It self-heals when the squatting pid dies, the rejection rows name the pid
so an operator can verify it is unrelated, and deleting that workflow's
`locks` row clears it (documented in `docs/operations/scheduling.md` §5).
No code change is planned: distinguishing reuse from life would require
start-time tracking the store does not keep, and the current behavior is the
safe default.

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
| **Git detects change; it does not replace ingestion** | The existing content-hash pipeline already guarantees correctness — git only narrows the candidate set. **Implemented** as a candidate mode on the one pipeline, not a second indexer | `PLAN.md` Step 3, `app/ingestion/pipeline.py` |
| **Source-derived keys are namespaced `@source/<name>/…`** | The corpus and 29 sources share one Chroma collection. The namespace is what makes a scoped stale-removal sweep unable to reach another source's keys — or the corpus's — so it is a correctness device, not a naming convention | Step 3, `app/sync/namespace.py` |
| **Every removal precedes every addition** | Ids are content-addressed, so a file whose bytes did not change keeps the same ids at a new path. Deleting after adding would remove the chunks the new path had just claimed. The `purge` path was always ordered this way; the scoped sweep was **not**, and an integration test caught it deleting content on a rename and then advancing a checkpoint over the loss | Step 3, `app/ingestion/pipeline.py` |
| **An exact rename is purged like any other rename** | Correctness could rest on Chroma accepting an `add` over an existing id (it does, verified) or on the documented ordering (purge first, then the new key claims the ids). The second survives a change in the first. Git's similarity score is reported and asserted on, never acted on | Step 3, `app/sync/relevance.py` |
| **Two files with identical content cannot both be indexed** | They share one content address and Chroma 1.5.9 silently overwrites a duplicate id rather than rejecting it, so which file the index credits would depend on run order. The first in sorted path order keeps it; the second is skipped, counted and reported | Step 3, `app/ingestion/pipeline.py` |
| **A source's checkpoint advances only on full success** | Only `record_sync_success` sets `last_revision`, so a non-null revision always means "fully processed". A failed source keeps its old revision and the next run retries exactly that range — safe because ingesting the same content twice reaches the same state | Step 3, `app/sync/synchronizer.py` |
| **A new revision with nothing relevant in it still advances the checkpoint** | The revision *was* processed, and its outcome was "nothing here is evidence". Leaving it behind would re-diff the same irrelevant commit on every future run, for ever | Step 3, `app/sync/synchronizer.py` |
| **A no-change sync writes nothing at all** | Not the checkpoint, not even a timestamp. An untouched source must not look busy, and an artificial write is the first thing that makes an idempotency claim untestable | Step 3, `tests/test_sync_synchronizer.py` |
| **Review signals fire on changes since the last processed revision** | A first sync establishes a baseline; firing there would raise a signal storm across ~20 `COMPLETED` sources the first time they were synchronized, which is how a review gate stops being a gate | Step 3, `app/sync/synchronizer.py` |
| **The completed-project flag is reported, not persisted** | `sync_checkpoints.last_outcome` is CHECK-constrained to `SUCCEEDED`/`FAILED`; a third state needs a Step 1 migration, which is outside Step 3's boundary. The flag lives in the result, and in `operational_failures` for failures. Synchronization never writes `source_lifecycle` | Step 3, `app/sync/synchronizer.py` |
| **The scoped sweep runs only for a full resync** | A sweep's keep-set is a source's whole inventory, so passing it for a diff would delete every file the revision did not touch. Consequence: narrowing a source's includes does not retract indexed content until the next full resync | Step 3, `app/sync/synchronizer.py` |
| **The failure path is raise-proof** | A failure path that can itself raise turns one broken source into an aborted run over 28. An unrecognised exception becomes `UNEXPECTED`, and an uninterpretable lifecycle declaration is reported as requiring review rather than propagating | Step 3, `app/sync/synchronizer.py` |
| **Freshness is read from `sync_checkpoints`, never re-derived** | `PLAN.md` offered a new ingestion metadata field or derivation from the checkpoint. Derivation wins: no re-ingestion of the corpus is required to populate it, and freshness is already recorded by the layer that owns it. Consequence: freshness is a property of a **source**, so the hand-written `data/` corpus has none and is reported untracked rather than guessed at | ADR-006, Step 4, `app/context/builder.py` |
| **The evidence hierarchy follows the corpus documents, and the disagreement between them is recorded** | `data/evidence/README.md`, `data/audit/README.md` §2 and `rag-architecture.md` give three orderings that do not agree. The implementation follows the two corpus documents and carries each rank's basis in code; the resolutions are argued in `rag-architecture.md` rather than left implicit | ADR-007, Step 4, `app/context/taxonomy.py` |
| **Audit conclusions rank last, not fourth** | Ranking a summary above the material it summarises would let the audit outrank its own evidence, and `data/audit/README.md` §2 states the audit *"must never become the source of truth for personal facts"*. This is the one place the corpus's own hierarchy documents contradict each other | Step 4, `app/context/taxonomy.py` |
| **Positioning, voice and vision are removed from the evidence field, not ranked as weak evidence** | `data/audit/README.md` §13 assigns them the communication rules, and `data/vision_goals/my_vision.md` instructs the Agent to use it for positioning decisions. They are not weak support for a claim — they are not support — so a separate field is what makes it impossible to read *"preferred writing style"* as *"evidence that I built X"* | ADR-007, Step 4, `app/context/models.py` |
| **Sections are the corpus's own categories, not a taxonomy invented for the context layer** | The corpus is hand-written and its directory hierarchy is already semantic; re-deriving categories would create a second vocabulary free to drift from the first. The one added section, `repository_evidence`, exists because the `@source/…` population is 29 real repositories with no corpus category to hold them. A test reads `data/` and fails if the two drift | Step 4, `app/context/taxonomy.py`, `tests/test_context.py` |
| **Ordering ignores retrieval rank and score** | Ordering by them would make the assembled context a function of which strategy ran — the same corpus would produce a different context under `vector` than under `reranked`, and Step 9's verification would then be checking an artifact of retrieval rather than of the evidence. Both are still carried, as provenance | Step 4, `app/context/models.py` |
| **Insufficiency is a field, not an empty list** | An empty result list is the only "nothing found" indication retrieval offers, and downstream code can read it as success. `EvidenceStatus.INSUFFICIENT` is the single most important output for Step 9's gates, so it is explicit and distinguishable — and guidance alone does not resolve it | Step 4, `app/context/models.py` |
| **`build_context` catches nothing, and performs no retrieval** | Retrieval failure and "no evidence exists" are different facts, and only one of them means the user has nothing to say. Converting an outage into an insufficient context would turn infrastructure failure into a reason not to publish; the exception propagates and fails the run | Step 4, `app/context/builder.py` |
| **A retrieval-result input is a value, not a query** | `build_context` takes a `RetrievalResult`, so retrieval stays the only thing that queries Chroma and the context layer cannot quietly become a second retrieval path | Step 4, `app/context/builder.py` |
| **The one seam outside `app/context/` is an accessor, not a copy of the namespace** | The context layer needs to know which source a `@source/…` key belongs to. Re-spelling the prefix and separator here would create a second copy of a correctness device, free to drift. `source_name_from_key()` sits beside the functions it inverts, is total, and changes no existing behaviour | Step 4, `app/sync/namespace.py` |
| **No new persistence and no schema change** | The layer reads existing rows and returns a value object. `data/` is not restructured, no `PersonalProfile` abstraction replaces it, and no ingestion metadata field was added | Step 4, `app/context/` |
| **An explicit source registry is required** | Workspace roots contain ~28 repos, 17 virtualenvs (~17 GB), and this application itself; roots are places to inspect, not sources to ingest. **Implemented** as `sources.yaml`: 29 sources, 9 roots, 10 `not_registered`, 3 include profiles | `PLAN.md` Step 2, `docs/architecture/source-registry.md` |
| **The application must not ingest itself** | `~/LLMs/IBM` contains this project, so its own source, runtime state, `data/` corpus and token file are not professional evidence. Guarded twice — structurally by `is_protected()`, and at load time against concrete probe paths | Step 2, `app/sources/guard.py` |
| **Exclusion wins over inclusion** | Deny-wins rather than last-rule-wins, so the outcome depends on which rules exist rather than on the order they were written in. An exclusion without a stated reason is refused at load time — an unexplained rule cannot be reviewed, so it never gets removed | Step 2, `app/sources/patterns.py` |
| **Lifecycle can never change visibility** | `SyncDisposition` has no `skip` member and every `SyncPlan` carries `ingest=True`, so "ignore forever" is unrepresentable rather than discouraged. `COMPLETED` + new commits → ingested in full **and** surfaced as `REQUIRES_HUMAN_INTERVENTION` | Step 2, `app/sources/enums.py`, `lifecycle.py` |
| **The registry refuses to load rather than drop an entry** | A source silently missing produces no error and no signal — just a knowledge base that quietly stops covering part of the user's work. Validation collects every problem and refuses the whole file | Step 2, `app/sources/registry.py` |
| **Virtualenvs are detected structurally, not by name** | The workspace contains `.venv`, `venv`, `my_env` and `fastapi_venv`; a name list would miss whichever name comes next, and a missed virtualenv is hundreds of MB of library code in a corpus of the user's own work | Step 2, `pyvenv.cfg` detection |
| **A repository rooted at a declared root is one source** | `~/LLMs/IBM`, `~/LLMs/AI_Agents` and `~/Portfolio` are each both a root and a single revision history. The rule enforced is that a *filesystem* source may never be a declared root — sweeping a loose directory is the actual hazard | Step 2, `_check_declared_roots` |
| **`repo_identity` is sanitized, never copied verbatim** | 14 inspected repositories embed a live token in their local git remote; the registry is committed and remotes are not | Step 2, `sanitize_repo_url()` |
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
| **At most one publication attempt per run — never "exactly once"** | LinkedIn offers no read-back, so exactly-once delivery is unverifiable by construction and promising it would be false. What the system actually has: a durable intent, a database-enforced one-attempt limit, an explicit ambiguous state, and a recovery path that fails closed. The claim is refused in the code, in messages, and in this register | Step 6, `app/publishing/service.py` |
| **The three duplicate checks stay three, over three kinds of data** | Exact reads a content hash, near reads a stored embedding, overuse reads stored topic/project/evidence references. Merging them into one similarity score would make the project case — same project, no shared vocabulary — undetectable, which is precisely the repetition a person notices | `PLAN.md` Step 6, `app/publishing/duplicates.py` |
| **A duplicate check that could not run refuses the publish** | The failure this step exists to prevent is a repeated post, which cannot be undone; a refused publish can be retried by a person. `DuplicateReport` therefore keeps `unchecked` apart from `findings` — "nothing matched" and "nothing was compared" must never look alike | Step 6, `app/publishing/models.py` |
| **`project` is a stored label, not derived from evidence paths** | Deriving it would mean guessing which directory a path belongs to — the opposite of a deterministic history. It is recorded symmetric with `topic`/`angle`, which is what makes project overuse answerable from state rather than inferred from text | Step 6, migration v3 |
| **The published text is not copied onto `publications`** | The text lives on the intent and `publications.intent_id` is UNIQUE, so the join is 1:1 and a second copy could only drift. With the history service returning no generated text at all, "a generated post is never evidence about the user" becomes a property of the types instead of a rule to remember | Step 6, §6.1 |
| **A publication stores the embedding of what was published** | Re-embedding stored history on every check would make an old post's similarity depend on the embedder of the day, so "already said this" would drift without anything being published. One vector, written at the one moment text and outcome are known together | Step 6, `publications.embedding` |
| **Recovery resolves the two interruptions in opposite directions** | `attempt_started` → `unknown_requires_review` (a post may exist; never retried), `intent_created` → `failed` (nothing left the machine, so the words are free). One direction would either duplicate a post or strand usable content | Step 6, `recover_run()` |
| **Publishing reports; only the store raises** | A refusal, a failure, an ambiguity and a success are normal outcomes a workflow branches on — and Step 7 has to notify on them. A store failure is the one thing a caller must not continue past, so it stays an exception | Step 6, `app/publishing/service.py` |
| **The publishing layer is structurally unable to reach the knowledge base** | The separation is asserted by parsing every module in `app/publishing/` and failing on an import of `chroma`, `langchain`, `app.retrieval` or `app.ingestion`. A behavioural test could only show that no test looked | Step 6, `tests/test_publishing_history.py` |
| **Near-duplicate detection is inert until an embedder is supplied** | The publishing layer may not reach into retrieval for one, so the check is part of the policy only when a service is constructed with it. Fail-closed when configured and broken; honestly absent when not configured — never silently skipped | Step 6, Known Issue #8 |
| **Notifications use SMTP** | Provider-agnostic interface, configured for Gmail; stdlib preferred; fake transport in tests | `PLAN.md` Step 7 |
| **Infrastructure stays minimal** | LangGraph, MCP, multi-agent, queues, Redis, PostgreSQL, microservices, Kubernetes, and distributed workers are deferred with reasons | `PLAN.md` §7 |
| **The integration's interface is a result, never a print or a prompt** | An unattended workflow cannot read stdout and cannot answer a question. The step removes the interactive confirmation and makes the classified result the contract; a source-level test fails if `print(` or `input(` reappears anywhere in the package | Step 5, `app/integrations/linkedin/publisher.py` |
| **An ambiguous publish is an outcome, not a failure** | LinkedIn can publish but cannot be read back, so when a 201 arrives without a post id — or the request was sent and the answer never came — the system must be able to say "a post may exist" rather than choosing between a false success and an invitation to duplicate | `PLAN.md` §5.1, Step 5, `app/integrations/linkedin/enums.py` |
| **`retryable` is advice about the failure, not permission to retry** | Whether a retry is safe also depends on whether the previous attempt could have reached LinkedIn, which is a different field. The integration never retries anything itself; the policy is Step 6's | Step 5, `app/integrations/linkedin/classification.py` |
| **Failures are classified from the status and the transport event, never from message text** | A message is prose that changes without notice; the status code and the exception type are the interface. A connect-time failure is provably "nothing sent" and is retryable; a failure after the request left is not | Step 5, `app/integrations/linkedin/classification.py` |
| **The credential expiry is derived and stored with the evidence that produced it** | The credential carries a duration (`expires_in`), never an absolute date, so the expiry must be derived — and a derivation is worth exactly as much as what it came from. The row records `id_token_iat` or `file_mtime`, and an expiry that cannot be derived is reported absent rather than guessed | Step 5, `app/state/schema.py`, `app/integrations/linkedin/credentials.py` |
| **A warning that only appears on the run that has stopped working is not a warning** | `EXPIRING_SOON` publishes normally and the warning is carried on the successful result too; the point is to reach a person while the system still works, and the only remedy is re-running the OAuth script by hand | `PLAN.md` Step 5, `app/integrations/linkedin/credentials.py` |
| **Refresh is attempted only when the credential is already expired** | The refresh path has never been verified against LinkedIn and the real credential has no `refresh_token`, so pre-emptive refreshing would trade a working credential for an unverified call. A rejected or timed-out refresh is not retried and leaves the on-disk credential untouched | `PLAN.md` §5.2, Step 5 |
| **The API version is configuration, not a literal in a header** | LinkedIn retires versions on a rolling cadence, so a working integration stops working with no code change on our side. It is validated as `YYYYMM` at import and recorded on every attempt, so a failure can be attributed to the version that produced it | Step 5, `app/config.py` |
| **A request with no timeout is unrepresentable** | An unattended workflow blocked on a socket is indistinguishable from a crashed one, except that it holds the run lock (Step 12). The client refuses a non-positive timeout at construction, so "no timeout" cannot be configured | Step 5, `app/integrations/linkedin/client.py` |
| **The credential path is defined once, and the definition is tested** | The defect this step exists to fix was a token written in one directory and looked for in another. `app/paths.py` owns the canonical path and an AST-based test fails if any `Auth_handling/` script drifts from it | Step 5, `app/paths.py`, `tests/test_linkedin_credentials.py` |
| **Step 5 adds exactly one table, and it records a fact rather than an action** | Step 5 stores nothing about publishing — that is Step 6's authority. `linkedin_credential_expiry` exists because a credential that dies between two runs has to be detectable by the run that comes after, and there is nowhere else durable for it | Step 5, `app/state/schema.py` |
| **Nobody chooses to notify; the outcome decides** | `NotificationService` has exactly two entry points — `notify_run(run_id)` and `notify_failure(failure)` — and neither asks the Agent anything. `PLAN.md` is explicit that a phase failing inside the Agent still notifies because the workflow wraps it, so notification is infrastructure with a deterministic trigger, not a judgement call a model can be wrong about | Step 7, `app/notify/service.py` |
| **Severity is read, never re-derived** | `WORKFLOW_FAILED` and `REQUIRES_HUMAN_INTERVENTION` already exist on the layers below as `requires_human_intervention` and `RecoveryReport.blocked`. The message layer reuses that vocabulary instead of inventing a second severity enum, so the two can never drift apart into a system that files an ambiguity as an ordinary failure | Step 7, `app/notify/enums.py`, `app/notify/messages.py` |
| **The store is optional so that the store can be the thing that failed** | A store failure is the one error Step 6 deliberately lets escape, and `PLAN.md` lists the state store itself as a phase that must be able to notify. `notify_failure()` therefore works with no store at all and reports `recorded is False`; only `notify_run()` requires one, because a run id is meaningless without a store to look it up in | Step 7, `app/notify/service.py` |
| **A delivery failure is a separate row from the failure it reports** | The `notifications` table records the attempt, not the incident: `delivery_state` is `pending`/`sent`/`failed`, and a failed delivery leaves the `operational_failures` row and the run's outcome exactly as they were. An undelivered alert must not be able to make a failed run look handled, and a sent alert must not be able to make it look successful | Step 7, `app/state/schema.py` (Step 1 table), `app/notify/service.py` |
| **One redaction list, consumed by the log filter and the notifier both** | `SMTP_PASSWORD` joins the secret environment list, and `known_secrets()`/`redact()` became the single definition both the logging filter and `app/notify` call. A second list would be a second thing to forget, and the transport scrubs its own exception text before the service scrubs the result, so neither the log nor the delivery record can carry the password | Step 7, `app/logging_config.py`, `app/notify/transport.py`, `app/notify/service.py` |
| **Only a `sent` row suppresses the next alert, and a first occurrence is never suppressed** | Rate limiting reads `notifications` filtered by `failure_id` **and** `delivery_state='sent'` — a failed delivery must not silence the retry that follows it, which would turn a broken mail server into a silent outage. There is no prior row on a first occurrence, so the first one always sends | Step 7, `app/notify/service.py`, `app/state/store.py` |
| **The quiet window is a read filter, not a schema change** | `list_notifications()` gained an optional `failure_id`, following Step 6's precedent of adding store read methods rather than tables. Suppression is derived from the rows that exist, so nothing has to be migrated and a `sent` row stays a pure record of what happened | Step 7, `app/state/store.py` |
| **The layer separation is asserted in both directions, structurally** | An AST scan fails if `app/notify/` imports `chroma`, `langchain`, `app.retrieval`, `app.ingestion` or `app.publishing`, and a second scan fails if `app/publishing/` imports `smtplib` or `app.notify`. A behavioural test could only show that no test looked; this makes the notification transport structurally unreachable from the publishing layer | Step 7, `tests/test_notify_service.py` |
| **An unsent email is not a safety hazard, so there is no write-ahead row** | Step 6 writes a `pending` intent *before* the request because an unrecorded post is a duplicate risk. An unrecorded email risks a repeated email, which the noise control already bounds — so the delivery row is written once, after the attempt, carrying its final state | Step 7, `app/notify/service.py` |
| **The prompt's parts are fields, so they cannot be merged** | Evidence and communication guidance reach the model as separate labelled sections, with the rules as the system message and the material as the user one. A model told *"write without marketing language"* in the same block as *"I built X"* has no way to know that one is a manner of speaking and the other a fact it may claim — so the separation is a value with named fields, not a formatting choice | Step 8, `app/generation/models.py`, `prompt.py` |
| **The prohibitions are generated from the list a test checks** | `PROHIBITED_CLAIMS` names the categories a post may never invent, and the instruction sentence is built from it. A hand-written sentence would be a second copy free to fall out of step with the test that is supposed to be enforcing it | Step 8, `app/generation/prompt.py` |
| **An invented citation is impossible, not merely discouraged** | The model answers with the labels the prompt sent; resolution is a lookup in that list, so a label that was never supplied has no citation to become. It is reported in `unresolved_labels` rather than dropped, because a draft citing a source it was never given is a fact Step 9 has to see. "Cites only sources present in that set" is a property of the code path, not of the model's compliance | Step 8, `app/generation/generator.py` |
| **Insufficient evidence is decided by the system, before the model is asked** | A context with no evidence cannot ground a post, and asking a model anyway is asking it to invent. The check is deterministic, makes no request, and leaves `latency_ms` `None` — a plausible duration on a call that never happened would be a fabricated measurement in an audit record | Step 8, `app/generation/generator.py` |
| **A decline is a normal outcome; a failure is an exception; there is no third thing** | A decline is the system working — it ends the run on `DO_NOT_PUBLISH`, which Step 7 waives, so a correct "nothing worth saying" produces no alert. A failure raises `GenerationError` with a category, so it ends the run as `WORKFLOW_FAILED` and notifies. Raising on a decline would turn the best behaviour into an incident; returning a result on a failure would let a nonexistent post look like a weak one | Step 8, `app/generation/errors.py` |
| **There is no degraded post** | Unlike retrieval — which may fall back to the original query — generation cannot usefully fall back. `PLAN.md` Step 8 says so explicitly, and the hazard is concrete: unverified text about a real person reaching the publish path indistinguishable from a draft. No placeholder, no truncation, no best-effort text | Step 8, `app/generation/generator.py` |
| **No LCEL chain, deliberately** | The interface this step needs is typed *blocks*, which is a value object rather than a pipeline; `ChatOpenAI.invoke()` accepts plain role/content dicts, so the real path is the same OpenRouter client the repository already uses; and a fake with one method then tests the whole contract offline. The cost — no LangChain-level composition (streaming, callbacks, retries) without wrapping this — is accepted and recorded in the Step 8 deviations | Step 8, `app/generation/generator.py` |
| **The generator cannot reach the store, the publisher, the notifier or the knowledge layers** | Asserted by parsing every module in `app/generation/`. Generation writes no state (`PLAN.md` Step 8: persistence happens at the publish step), which is what makes the failure path reachable while the store is the thing that is broken — the same reason `notify_failure()` needs no store | Step 8, `tests/test_generation_generator.py` |
| **A claim is a sentence, and every sentence is a claim** | Classifying which sentences "really make a claim" is the semantic judgement this layer may not fake, and a sentence that was skipped is a sentence nothing downstream can check. Splitting is deterministic, indexes are assigned in order, and the *classification that matters* — is it supported? — is made per claim against evidence | Step 9, `app/verification/claims.py` |
| **Severity is a declared table, not a judgement at the call site** | `PLAN.md` does not draw the line between "revise" and "reject"; the implementation draws it at *"can rewriting this draft against this same evidence make it publishable?"* — wording findings revise, evidence and provenance findings reject. Declared once per kind, total over the enum, no default, so a new check cannot be added without deciding whether it gates | Step 9, `app/verification/policy.py` |
| **A passing result cannot carry a finding** | The invariants live in `VerificationResult.__post_init__`, so `PASS` with a violation, `REJECTED` without an unrepairable one, and `REVISION_REQUIRED` carrying one are all unconstructible. A caller that reads only `outcome` cannot be misled by a result that disagrees with its own findings, and a bug in the verifier is an exception rather than a post that publishes itself | Step 9, `app/verification/models.py` |
| **A claim whose evidence is unused is told apart from a claim that has none** | `UNCITED_REFERENCE` (the figure is in the supplied evidence, uncited — cite it or drop it) and `UNSUPPORTED_REFERENCE` (the figure is nowhere — fabricated) need different repairs, and only one of them is repairable. A single kind would have had to pick one severity for both, which would either burn revision attempts on the unfixable or let a fabrication through as rewritable | Step 9, `app/verification/policy.py` |
| **The forbidden inferences are quoted, not paraphrased** | Each rule in `FORBIDDEN_INFERENCES` carries the `data/audit/README.md` §3 line it came from verbatim, so the rule can be checked against the policy it operationalizes without leaving the code. The sixth line of that list — *never invent dates, metrics, technologies, responsibilities, or outcomes* — is not an inference from a source and is enforced by the reference check plus the judge | Step 9, `app/verification/policy.py` |
| **Configuration is never evidence of a deployment, structurally** | The deployment rule can be satisfied by evidence's *text* only when its *source path* is not a configuration file. Text alone could not draw that line — a `deployment.yaml` would pass by mentioning the word — so the audit's "configuration alone" is enforced as a property of the provenance rather than of the prose | Step 9, `app/verification/policy.py` |
| **A declared-weak evidence state is respected, and admitted by the claim** | `LEARNING` and `ASPIRATIONAL` are legitimate states in `data/evidence/README.md`, not findings: "I'm learning X" resting on evidence that says exactly that is not the upgrade the audit forbids. `UNVERIFIED` and `STALE` admit no such hedge — there is no fact underneath them to word. "Course" is deliberately *not* hedge vocabulary, because mentioning a course is a claim about what was done | Step 9, `app/verification/policy.py` |
| **The advisory judge answers by claim number, and a wrong number fails closed** | A number either names a claim that was sent or does not; a quotation cannot be checked without trusting the quotation. An answer about a claim that was not asked about, or two answers about one claim, is a `VerificationError` rather than something silently dropped — otherwise a misnumbered objection disappears | Step 9, `app/verification/support.py` |
| **Unavailable is not the same as failing** | `PLAN.md` allows the run to continue on the deterministic gates when LLM-assist is missing, and requires the degraded mode to be recorded. `SupportJudgeUnavailable` sets `degraded=True`; any *other* judge exception is a `VerificationError`, because a judge that crashed while judging may have had an objection. The judge implementation owns the classification, so a bug in the layer above it cannot be mistaken for an absent model | Step 9, `app/verification/errors.py`, `judge.py` |
| **The revision bound lives with the decision, and the loop does not exist yet** | `PLAN.md` requires the revision loop to be bounded and terminating and assigns the loop itself to Step 10. `revision_decision()` is total, injectable, and returns `REVISE` only while the budget is unspent — so no caller that obeys it can loop forever, and `EXHAUSTED` is reported separately from `REJECT` because "we stopped trying" and "this could never pass" are different facts about a run | Step 9, `app/verification/revision.py` |
| **One rule stated twice, with the copies asserted equal** | The lexical-overlap check needs *content* terms, and importing `app/retrieval`'s BM25 tokenizer would make verification depend on the retrieval stack — the boundary the package's import scan asserts. The three-line tokenizer is restated in `app/verification/claims.py`, and a test asserts the two agree, so the shared rule stays shared and the dependency does not exist | Step 9, `app/verification/claims.py`, `tests/test_verification_rules.py` |
| **A verification is not a pipeline stage** | `verify()` is a function, as `PLAN.md` says, and the verifier holds a judge and nothing else — no store, no clock, no source path, no retrieval handle. "The verifier cannot invent evidence" is therefore a property of what it is able to do rather than a promise it keeps | Step 9, `app/verification/verifier.py` |
| **Evidence is selected by label, because a label cannot be invented** | The reasoner answers with `E1…En` against the list this run built, and a label either resolves or does not exist — there is no path by which a source path, a chunk id or a claim can arrive from the model. The same device Step 8 used for citations, applied to the choice of what to write about | Step 10, `app/agent/prompt.py`, `agent.py` |
| **A model's words become a fact in exactly one function** | `ReasoningAnswer` is deliberately *raw* — a topic string, labels, prose — and `_proposal_from()` is the only code that reads it, resolving each field against what the run actually offered and refusing (never trimming) what does not resolve. Keeping the raw answer and the resolved proposal as separate types is what makes "the Agent cannot invent a source" checkable rather than merely intended | Step 10, `app/agent/models.py`, `agent.py` |
| **A `PUBLISH` is unconstructible without a passing verification** | Same instrument as `VerificationResult.__post_init__`: the invariant lives in `AgentResult.__post_init__`, so the one lie an agent could tell — reporting a publication the gate never granted — is a `ValueError` at construction instead of a post on LinkedIn. "The Agent proposes; the workflow disposes" is enforced by the type rather than by discipline | Step 10, `app/agent/models.py` |
| **A decision not to publish is a success, and a failure is an enumerated set** | `FAILURE_REASONS = {REASONING_FAILED, INVALID_PROPOSAL}` is explicit and two members long, so "we decided not to" and "reasoning broke" can never be confused for one another, and `AgentResult.failed` is kept distinct from `not is_publishable` so a workflow does not email a person about a correct decision. Adding a failure reason later is a deliberate edit to that set, not a side effect | Step 10, `app/agent/enums.py`, `models.py` |
| **A reasoning failure is a result; a phase failure is an exception** | `PLAN.md` Step 10 requires reasoning failure → `DO_NOT_PUBLISH` plus a notification, and forbids a weaker fallback. It says nothing of the sort about a phase that could not complete, so `GenerationError` and `VerificationError` propagate untouched: collapsing "the gate could not decide" into `DO_NOT_PUBLISH` would report a broken run as a decision, and the workflow is the layer that names the failed phase | Step 10, `app/agent/agent.py` |
| **The revision bound is called, not reimplemented** | `PLAN.md` assigns the loop to Step 10 and the stopping rule to Step 9, so the Agent calls `revision_decision(result, attempts_made, limit=…)` and adds only a guard that *raises* if the loop outran the bound it was given. Reimplementing the rule here would have made two definitions free to disagree about when to stop, which is the one thing a bounded loop cannot afford | Step 10, `app/agent/agent.py` |
| **A revision is driven by the verdict, not by a fresh opinion** | A `REVISE` re-drives the generator with Step 9's own `revision_notes()` as `PublishingConstraints.notes`, so the second attempt is a bounded operation over what the gate said was wrong. The Agent forms no view of its own about the draft — that would be a second, unverified opinion about text nothing had checked | Step 10, `app/agent/agent.py` |
| **The Agent is told about its history; it does not read it** | `HistoryDigest` is a plain value built by the caller from Step 6's read service. The service is not passed into the reasoning layer, because what crosses that boundary should be exactly what a model needs and nothing else about the store should travel with it — the same argument that keeps `PublishingConstraints` a value | Step 10, `app/agent/models.py`, `history.py` |
| **The history boundary is a narrow protocol the real service satisfies structurally** | `PublicationHistoryReader` declares five read methods and `PublishingHistory` satisfies it without the Agent importing `app.publishing.history` at all. Widening that protocol is how a read-only boundary stops being one, so its exact method set is asserted by test | Step 10, `app/agent/history.py`, `tests/test_agent_boundaries.py` |
| **The Agent does not restate `MAX_PUBLISHES_PER_RUN`** | `PLAN.md` Step 10 forbids duplicating the gates inside the Agent, and the post limit is already enforced by `ux_publish_intents_run`. The guarantee is made **structural** instead: one optional proposal, one optional draft, a loop that returns at the first passing verification, and no publisher anywhere in the package. A copied constant would have been a second definition of a limit the database already owns | Step 10, `app/agent/models.py`, `agent.py` |
| **Retrieval strategy selection is a recommendation drawn from a vocabulary the caller allows** | `PLAN.md` notes that `RetrievalEngine` accepts a strategy but nothing chooses one. The Agent cannot retrieve and does not, so what it produces is the strategy for a *fresh* pass at the topic it chose — and an empty vocabulary means "no choice to make", leaving the proposal with the strategy the context was assembled with, which is one that demonstrably found this evidence. Nothing in `app/retrieval/` was touched | Step 10, `app/agent/agent.py`, `models.py` |
| **The Agent's boundary is asserted in both directions** | Forbidden imports (`sqlite3`, `chroma`, `app.state`, the publishing *service*, `app.notify`, `app.retrieval`, `app.ingestion`, `app.sync`, `app.integrations`, `app.sources`) plus an explicit allow-list of every `app.*` module it may reach, plus a source scan for write verbs. Step 6, 8 and 9 each asserted one direction; asserting the allowed set too is what makes a new import a deliberate act rather than something that slips in beside a change | Step 10, `tests/test_agent_boundaries.py` |
| **The prompt's prohibitions are imported, not restated** | The Agent's instruction sentence is generated from `PROHIBITED_CLAIMS`, imported from `app.generation.prompt`. A second hand-written copy would be free to fall out of step with the list the generator's own test checks — and the two layers would then disagree about what a post may never invent | Step 10, `app/agent/prompt.py` |
| **The Agent stops at the value, and that is where Step 11 begins** | `AgentResult.to_record()` produces JSON-compatible values with no clock and no environment, and nothing writes them. `PLAN.md` Step 10 keeps the write above this layer — "or the system could *forget* to record" — so the run record, the publication and the verification are all persisted by the workflow, into a schema that does not have their columns yet (Known Issue #14) | Step 10, `app/agent/models.py` |
| **Phase transitions are a table, not a log convention** | `workflow_runs` holds the outcome and the failed phase; `workflow_phases` holds every transition (migration 4, additive — no Step 1 table touched). "What did this run do?" is therefore a query (`list_phases`), and a success leaves the same trail as a failure. The alternative — inferring the trail from log lines — would have made the audit depend on log retention | Step 11, `app/state/schema.py`, `store.py`, `app/workflows/common.py` |
| **Exit codes are 0 / 1 / 2, owned once** | `DO_NOT_PUBLISH → 0`, `WORKFLOW_FAILED → 1`, `REQUIRES_HUMAN_INTERVENTION → 2`, in one shared mapping both entry points use. The two nonzero codes are distinct so a scheduler — and Step 12 — can tell "it broke" from "it needs you" without reading the database | Step 11, `app/workflows/common.py` |
| **A published post is reported, not celebrated by the failure path** | A publish terminates `DO_NOT_PUBLISH`, which the failure notifier waives by design — so the workflow calls `notify_publication()` exactly once for a post that went out. Without it, the one thing the user most needs to see (what went out under their name) would be the one thing nothing reports | Step 11, `app/workflows/branding.py` |
| **The ambiguity check runs before the network, not after** | `PublishingHistory.requires_review()` is read before the publish phase is entered: an earlier attempt still awaiting review refuses the new publish and escalates, so no request can leave the machine over an unresolved outcome. Checking after the call would already have risked the duplicate | Step 11, `app/workflows/branding.py` |
| **Cron triggers; the application never schedules** | One user, one machine, fixed 8h/24h intervals: a two-line crontab instead of timer units plus daemon-reload plus lingering, and no dependency on a running systemd init. Exit statuses pass straight through with no masking; `0/1/2` keep their Step 11 meanings and `3` means "did not run". Revisit for systemd if sub-minute granularity, dependencies, or journal integration become requirements | Step 12, `ops/personal-branding-agent.cron`, `docs/operations/scheduling.md` |
| **A timeout never grants a lock to a second live process** | Step 1 reclaims on expiry alone, which would silently twin an overrunning run. Owners are therefore `hostname:pid:token` and an expired-but-live owner is refused, not reclaimed; only a demonstrably dead owner is taken, through the atomic transaction, so two simultaneous recoveries cannot both win. The failure direction on doubt (unparseable owner, pid reuse) is always refusal — a missed run, never an overlap | Step 12, `app/workflows/scheduled.py` |
| **Recovery reports; it never resolves** | Unfinished runs are occurrence-counted and left `NULL` — finishing one here would invent an outcome nobody observed — and publish state is never touched, so recovery cannot retry an ambiguity. An unfinished run seen while locked is the live holder's own, so it is not reported at all | Step 12, `app/workflows/scheduled.py` |

---

## Next Step

### Step 13 — End-to-End Autonomous Evaluation

The next implementation task is defined in `PLAN.md` §8, Step 13.

Step 12 closed the unattended-execution gap: both workflows run on a cron
schedule under a per-workflow overlap guard, stale locks recover after a
liveness check, and interrupted runs are reported without being resolved.
What does not exist is any proof that the *system* behaves correctly when
things go wrong: unit tests cover components, but no deterministic
full-workflow scenarios exist for the failure catalogue `PLAN.md` Step 13
lists (changed/deleted sources, duplicate and weak-evidence candidates,
generation and verification failures, LinkedIn timeouts, ambiguous
publication, expired tokens, notification delivery failure, interrupted-run
recovery, self-ingestion attempts).

Constraints carried in from Step 12:

- **Scenarios assert recorded outcomes, not completion.** The three run
  outcomes, the phase trail, and the lock/recovery rows are all queryable
  from an isolated test store — evaluation reads them, never log strings.
- **The ambiguous-publication scenario is the most important test in the
  suite**: it must prove a second post can never go out, using the Step 6
  constraint plus the Step 11 pre-publish guard.
- **Fakes only, isolated state.** LinkedIn, the LLM, and email stay faked;
  the real LinkedIn path stays manual and explicitly invoked. Never the
  production database.
- **Still open, and still not this step's to close:** Known Issues #5 (key
  mismatch), #7 (no real sync pass), #8 (near-duplicate embedder), #9 (no
  real publish), #11 (no real email), #12 (expiry pre-check), #15 (linter),
  #16 (pid-reuse false-live).


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
