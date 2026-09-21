# Personal Branding Agent — Master Roadmap

**Status:** Rewritten for the autonomous-system target.
**Supersedes:** the previous "RAG application / phases 1–10" roadmap.
**Baseline:** grounded in an inspection of the repository as it exists today, not
in the previous plan's intentions.

---

## 1. Project Goal

Build an **autonomous personal-branding system** whose decisions and generated
content are grounded in a RAG system over a personal knowledge base (`data/`),
that can synchronize its own knowledge from Git sources, decide on its own
whether publishing is worthwhile, publish to LinkedIn through a hardened
service, and keep an auditable record of every decision, action, and failure.

The system must no longer depend on a human asking "create a LinkedIn post."

**The Agent is one bounded reasoning component inside a deterministic,
observable workflow. It is not the system.**

---

## 2. Target System Behavior

Two independent schedules with different periods and different failure domains.

### Every 24 hours — Knowledge Synchronization

```text
Source Registry
      ↓
Git / filesystem change detection   ("what changed since the last processed revision?")
      ↓
candidate changed files
      ↓
relevance policy
      ↓
existing ingestion pipeline         (content hashing, deterministic ids, stale removal)
      ↓
Chroma
```

### Every 8 hours — Branding Workflow

```text
read knowledge (retrieval)
read operational state (publishing history, constraints)
identify content opportunities
      ↓
Agent decides: is publishing worthwhile?
      ↓
0 or 1 candidate
      ↓
generate
      ↓
verify evidence  (deterministic gates authoritative; LLM assist advisory)
      ↓
deterministic publish gate
      ↓
publish to LinkedIn
      ↓
persist outcome
```

An 8-hour run **does not require** a post. The system must prefer **no post**
over weak, repetitive, unsupported, or low-value content.

**Hard invariant:** `MAX_PUBLISHES_PER_RUN = 1`.

### The three workflow outcomes

Every run terminates in exactly one of these. They are distinct, and conflating
them is a defect.

#### 1. Normal no-op — `DO_NOT_PUBLISH`

No meaningful content opportunity exists, or the Agent judged publishing not
worthwhile. **This is a successful workflow.** Exit status is success. **No
failure notification is sent.** The run is recorded so history reflects it.

#### 2. Workflow failure — `WORKFLOW_FAILED`

A phase could not complete: generation service unavailable, retrieval error,
ingestion error, LinkedIn transport failure, state-store error.

The failure is **persisted and an email notification is sent.** Exit status is
non-zero.

#### 3. Human intervention required — `REQUIRES_HUMAN_INTERVENTION`

The system cannot safely resolve the condition on its own:

```text
LinkedIn authentication expired and cannot be renewed automatically
publication outcome is ambiguous (may have succeeded)
unrecoverable configuration problem
a registered source path is missing or is no longer a repository
state store unavailable or corrupted
```

The condition is **persisted and the user is notified.** Exit status is
non-zero and distinct from an ordinary workflow failure. The system **must not
blindly retry** in this state.

---

## 3. Architecture Summary

```text
                  ┌──────────────────────┐
                  │   Source Registry    │
                  └──────────┬───────────┘
                             ↓
                 ┌─────────────────────────┐
                 │ Knowledge Synchronizer  │
                 │ Git / Filesystem        │
                 └────────────┬────────────┘
                              ↓
                     Existing Ingestion  (unchanged — no second pipeline)
                              ↓
                           Chroma
                              ↓
                         Retrieval
                              ↓
                      Context / Evidence
                              ↓
                         Generation
                              ↓
                      Verification Gates
                              ↓
                    Autonomous Agent  (bounded reasoning)
                              ↓
                     Publish Decision
                              ↓
              Persistent Operational State Store (SQLite)
                              ↓
                     LinkedIn Integration
                              ↓
                       Publication Result
                              ↓
                         Run / Audit State

24h Scheduler ─────────────→ Knowledge Sync
8h  Scheduler ─────────────→ Branding Workflow

Any operational failure → persist failure → notification service → email → user
```

### Layer responsibilities

```text
Sources         Explicit registry over an inspected workspace. Include/exclude
                per source. Never a recursive root scan. Never self-ingestion.
Knowledge       RAG over data/ → Chroma (semantic index of facts about the user)
Operational     SQLite: runs, checkpoints, intents, publications, failures,
                notifications, locks. NEVER mixed into the Chroma collection.
Reasoning       Bounded Agent: opportunities, topic, angle, evidence, publish-worthiness
Generation      LCEL chain producing candidate posts from assembled context
Verification    Deterministic gates (authoritative) + LLM assist (advisory)
Tools           LinkedIn publish, retrieval, state reads — plain services
Execution       Two `python -m` CLI workflows, triggered by an OS scheduler
Notification    SMTP; deterministic infrastructure; never Agent-discretionary
Outcomes        Every run ends as DO_NOT_PUBLISH | WORKFLOW_FAILED |
                REQUIRES_HUMAN_INTERVENTION — recorded, never inferred
```

---

## 4. Current Implementation State

Based on repository inspection. **Component status must be re-verified in
Step 0**, because the current environment cannot import the application (see
§4.2).

| Area | Status | Evidence |
|---|---|---|
| Structured knowledge base (`data/`) | **DONE** | 10 categories: audit, certificates, completed_projects, evidence, in_progress_courses, in_progress_projects, public_positioning, stories_lessons, vision_goals, writing_style |
| Configuration (`app/config.py`) | **DONE** | Env loading, model id, generation params, embedding/reranker models, chunk params, retrieval defaults, `require_openrouter_key()` |
| Root `config.py` | **DEPRECATED SHIM** | 28-line re-export of `app.config`, self-documented as "Backwards-compatible re-export". Not imported by any application module. |
| Dependency pinning (`requirements.txt`) | **DONE (aspirational)** | Pins LangChain 1.x stack — **not satisfied by any environment on this machine** (§4.2) |
| Secrets / `.gitignore` | **DONE** | `.env`, `Auth_handling/linkedin_tokens.json`, `chroma_db/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `venv/`, `.venv/`, `logs/` all ignored; logging redacts secret *values*. 136 files tracked, none are runtime artifacts. |
| Ingestion pipeline | **DONE** | `app/ingestion/` — recursive discovery, path/heading metadata, deterministic `<sha256>:<index>` ids, content-hash idempotency, change + stale handling, partial-failure self-healing |
| Retrieval engine | **DONE** | `app/retrieval/engine.py` facade, 6 strategies: vector, metadata, bm25, multi_query, hybrid (RRF), reranked |
| Retrieval comparison playground | **DONE** | `python -m app.retrieval.compare "question"` |
| Retrieval evaluation | **DONE (v1)** | `python -m app.retrieval.evaluation`; 12-query gold set; results in `docs/retrieval/evaluation.md` |
| Retrieval learning docs | **DONE** | `docs/retrieval/` (5 corpus-grounded documents) |
| LinkedIn OAuth + publish | **PROVEN MANUALLY** | `Auth_handling/` published a real public post. Script-based, interactive, not a service. No usable token refresh. |
| Branding context engine | **NOT STARTED** | No `app/context/`. Raw material exists in `data/`. |
| Generation | **NOT STARTED** | No `app/generation/`, no `prompts/` |
| Content evaluation / verification | **NOT STARTED** | Retrieval eval exists; content gates do not |
| Agent core | **NOT STARTED** | `app/retrieval/engine.py` docstring: *"deliberately NOT an agent: the caller picks the strategy explicitly"* |
| Operational state store | **NOT STARTED** | No SQLite, no JSON state. Only Chroma + token file + log. |
| Git synchronization | **NOT STARTED** | Ingestion is content-hash driven; no git awareness, no source registry |
| Notifications | **NOT STARTED** | Nothing |
| Workflows / scheduling | **NOT STARTED** | No scheduler, no run state, no lock |
| Docs | **PARTIAL** | `docs/architecture/` (5), `docs/retrieval/` (6), `docs/phases/` (phase-01, phase-02 only). `docs/evaluation/` and `docs/operations/` are **empty directories**; `docs/decisions/ADRs/` holds only an index README, no ADR files. |

> `RAG_Lab.ipynb` is a historical course lab, retained as reference. It is not
> part of the production pipeline.

> **Uncommitted working-tree changes exist** in
> `Auth_handling/test_credentials.py` and `Auth_handling/test_post.py` (both
> change the token file to resolve relative to `__file__`). They are not part of
> any commit. Step 5 must reconcile them — and fix
> `linkedin_oauth_setup.py`, which they leave inconsistent.

### 4.1 The retrieval layer is a foundation — do not rewrite it

Vector, metadata filtering, BM25, multi-query, hybrid RRF, cross-encoder
reranking, a facade, comparison tooling, evaluation tooling, chunk-level
provenance, and deterministic fakes for tests all exist and are tested.

**The roadmap adds layers above and beside retrieval. It does not replace it.**

### 4.2 The environment does not currently work

`import` of the application fails today:

```text
tests/test_evaluation.py   → ModuleNotFoundError: rank_bm25
tests/test_fusion.py       → ModuleNotFoundError: rank_bm25
tests/test_retrieval.py    → ModuleNotFoundError: rank_bm25
tests/test_ingestion.py    → ImportError: cannot import name 'Search' from 'chromadb'
```

Installed versus pinned:

```text
                          pinned (requirements.txt)   installed
langchain                 >=1.3,<2                    0.3.12
langchain-core            >=1.6,<2                    0.3.63
langchain-chroma          >=1.1,<2                    1.1.0
chromadb                  >=1.5,<2                    0.4.24   ← incompatible pair
langchain-huggingface     >=1.2,<2                    MISSING
rank_bm25                 >=0.2.2,<1                  MISSING
```

There is no project-local virtual environment. Of 8 test modules, 4 fail to
collect; only 16 tests collect. **The historical "79 passing" baseline is not
reproducible today.** This blocks every other step and is therefore Step 0.

---

## 5. Constraints the Design Must Respect

These are repository facts, not preferences. They shape the roadmap.

### 5.1 LinkedIn can publish. It cannot read.

| Capability | Available? | Basis |
|---|---|---|
| Publish a post | **Yes** | `w_member_social` is held and self-serve; a real post was published |
| Read own post history | **No** | Requires `r_member_social`, which LinkedIn documents as *"restricted and is available to approved users only"* |
| Read certifications | **No** | No self-serve permission exposes profile detail beyond OpenID identity claims |
| Read own identity | **Yes** | `openid`/`profile` yield `sub`, name, email, picture |

**Consequences that must not be designed away:**

- `LOCAL PUBLICATION STATE = authoritative publication history`.
- `LINKEDIN = external publishing system`, not a source of truth.
- Autonomous operation must **not** depend on post read-back.
- Future reconciliation may be added if permissions are later granted — but
  nothing in Steps 0–13 may require it.

### 5.2 Token renewal is unverified and currently impossible

The saved token contains `access_token, expires_in, id_token, scope, token_type`
and **no `refresh_token`**, because `offline_access` was never requested. The
refresh code path in `test_credentials.py` therefore always returns
`"no refresh_token present in token file"` — it is dead code in practice.

The token expires roughly 60 days after issuance. An unattended system running
every 8 hours must survive that. **Do not assume adding `offline_access`
automatically solves this** — see `DECISION NEEDED 4` in Step 5.

### 5.3 The filesystem does not map to "four repositories"

The named sources (IBM, Quizey, FastAPI, DevOps) are **not four Git repos**. A
direct inspection of the declared workspace roots found:

```text
ROOT                    KIND          NESTED REPOSITORIES AND NOTABLE CONTENTS
~/LLMs/IBM              git repo      monorepo (13 commits). CONTAINS THIS PROJECT,
                                       plus Gradio, icebreaker.
~/LLMs/AI_Agents        git repo      12 commits; 9 entries
~/LLMs/AI_Hackthon      plain dir     hackathon_lectures (git, 18 commits);
                                       hackathon_practice_lab is NOT a repo
~/Quizey                plain dir     Quizey_V2 (git, 27); Quizey_Platform (git, 3)
~/FastAPI               plain dir     ExitProject (git, 0 COMMITS);
                                       course_practical_app; fastapi_venv (a venv)
~/DevOps                plain dir     jenkins-practice (14); KodeKloud_… (6);
                                       Manara/ (contains a nested repo)
~/ALX                   plain dir     ~18 nested repos, 2–274 commits each
~/Portfolio             git repo      21 commits; static site (html/css/images)
```

**Every declared root is a *place to look*, not a source to ingest.**

Three hazards this creates, all of which Step 2 must handle explicitly:

1. **Self-ingestion.** `~/LLMs/IBM` is a monorepo that contains this application.
   Registering it as a source would ingest the Personal Branding Agent's own
   source, `PLAN.md`, `chroma_db/`, and `logs/` as "professional evidence."
2. **Noise.** Roots contain environments (`fastapi_venv`), caches, and unrelated
   coursework. ~35 Git repositories exist within these roots.
3. **Zero-commit and non-repo sources.** `FastAPI/ExitProject` is a repository
   with no commits; several roots are plain directories whose content is
   filesystem-only.

**The registry must name exact sources with explicit include/exclude rules. The
system must never recursively scan a root and ingest everything it finds.**


### 5.4 The knowledge base is already stale

`data/in_progress_projects/quizey_v2.md` records a commit that is now **18
commits behind** the real repository, and its recorded source path no longer
exists. 48 of 71 KB files embed absolute source paths, some of them dead.

**Drift is the steady state, not an exceptional bug.** A one-time cleanup is not
a fix; continuous synchronization is.

### 5.5 Project completion is not currently machine-readable

`## Status` appears in 42 files; only 32 resolve against the vocabulary. The
corpus mixes *lifecycle* ("in progress") with *portfolio classification*
("studied / practiced"). Completion must therefore never be inferred from
inactivity, and must never become a permanent ignore flag.

---

## 6. Two Kinds of State — Keep Them Separate

| | Knowledge state | Operational state |
|---|---|---|
| **Answers** | What is known about the user | What the system has done |
| **Examples** | projects, certificates, skills, evidence, writing style, positioning | sync checkpoints, workflow runs, publish intents, publication outcomes, failures, notifications, locks |
| **Represented by** | `data/` Markdown corpus → ingestion → **Chroma** | **SQLite** (application-owned) |
| **Authority** | the corpus | the store |

**Hard rule:** a previously generated LinkedIn post must never become
authoritative evidence about the user.

### 6.1 Publishing history is NOT indexed into Chroma (V1)

**Decided.** For V1, authoritative publishing history lives **only** in SQLite:

```text
SQLite (authoritative publishing history)
        ↓
deterministic application service
        ↓
Branding Agent
```

The Agent still needs to answer:

```text
What have I published recently?
Which topics did I use?
Which evidence did I use?
Which projects have I talked about recently?
```

These are answered by **deterministic SQLite queries**, exposed to the Agent as
ordinary service calls — not by semantic retrieval. This is simpler, exact, and
cannot leak generated content back into the knowledge base as evidence.

A derived Chroma representation may be considered **later, only if evaluation
demonstrates a real benefit** — and never as authoritative. The risk it carries
is concrete: an indexed generated post can become "evidence" for the next post,
composing a loop the corpus's own audit policy exists to prevent.

**Consequence for the roadmap:** no step indexes publication history. Step 6
owns the store; Step 10 consumes it through a read service.

---

## 7. Explicitly Premature Architecture

Recorded here so it is not re-litigated each phase. These are deferred **only**
because the current workload does not justify them — not because they are
unfashionable. Each may be revisited when a concrete requirement appears.

| Technology | Verdict | Why (from this repository) |
|---|---|---|
| **LangGraph** | Deferred | The workflow is a linear state machine with one branch (PASS/REVISE/REJECT) and one decision (PUBLISH/DO_NOT_PUBLISH). No conditional complexity justifies a graph runtime. |
| **MCP** | Deferred | Nothing consumes these tools but this application. The requirement is a clean *service interface*, not a protocol with no second client. |
| **Multi-agent systems** | Deferred | Only two responsibilities involve genuine reasoning (topic/angle identification, evidence selection). Neither needs a separate agent. |
| **Message queues / event-driven infra** | Deferred | Two periodic jobs with mutual exclusion need a lock, not a broker. |
| **Redis** | Deferred | No cross-process cache or shared-session requirement exists. Chroma + SQLite cover persistence. |
| **PostgreSQL / external DB** | Deferred | One user, one machine, single-writer workload. SQLite provides transactions, uniqueness constraints, and zero deployment. |
| **Microservices** | Deferred | No independent scaling axis. |
| **Kubernetes** | Deferred | No orchestration problem exists. |
| **Distributed workers** | Deferred | Two sequential jobs on one machine. |
| **Large-scale event infrastructure** | Deferred | No event volume or fan-out. |
| **Docker / containerization** | Deferred | One machine, one user, no deployment target that requires it. A `.venv` plus a systemd timer is the whole runtime. |
| **`uv` / Poetry / Conda** | Deferred | `requirements.txt` already pins the stack and a plain project-local `.venv` satisfies it. A second environment manager adds a tool to document and reproduce for no gain at this size. |
| **A long-running in-process scheduler** | Deferred | Two periodic jobs. An OS-level trigger keeps both workflows independently executable and testable. |


**Also deferred, and worth naming explicitly:**

- **Replacing Chroma.** Measured latency is ~28 ms for hybrid retrieval; the real
  bottleneck is the cross-encoder at ~8 s. Replacing the vector store would
  optimize the wrong term.
- **Claim/fact extraction pipeline.** Step 4 requires an *assembler with coverage
  reporting*, not a fact database. The corpus's own audit policy is prose-first
  and treats uncertainty as something to preserve, not flatten.

---

# 8. The Roadmap

Steps 0–14, in dependency order. Every step uses the same ten-part format.

---

## Step 0 — Restore a Reproducible, Testable Environment

### Reason

Nothing in `app/` can currently be imported (see §4.2). Every later step is
unverifiable until a trustworthy baseline exists. This step also settles the
configuration-authority and secret-boundary questions that autonomous workflows
would otherwise inherit silently.

### Current state

- `requirements.txt` pins a LangChain 1.x stack; no environment on this machine
  satisfies it (`chromadb` 0.4.24 vs `langchain-chroma` 1.1.0 is the sharpest
  conflict; `rank_bm25` and `langchain-huggingface` are absent).
- No project-local virtual environment exists.
- Two configuration modules exist (root `config.py`, `app/config.py`). The root
  file is a re-export shim and no application module imports it.
- `Auth_handling/*.py` uses **CWD-relative** paths (`TOKEN_FILE =
  "linkedin_tokens.json"`, `load_dotenv()` with no path) — unlike `app/`, which
  was deliberately made CWD-independent.

### Scope

**Added:** a project-local environment; a documented reproduction procedure; a
configuration-authority decision recorded as documentation.
**Not changed:** no test is weakened, relaxed, skipped, or deleted. No source
module is refactored. Root `config.py` is **not** deleted in this step.

**Environment mechanism is decided:** a normal project-local `.venv` on
**Python 3.10** using the existing `requirements.txt`. Do **not** introduce
`uv`, Poetry, Conda, Docker, or any other environment mechanism unless
repository evidence later demonstrates a concrete need.

Explicitly out of scope: merging the two config modules, adding new
configuration keys (those arrive with the steps that need them).

### Architectural placement

Foundation. Owns `requirements.txt`, the environment, and the documented
configuration authority. No new application layer.

### Data/state

None. This step creates no persistent state.

### Implementation approach

1. **Establish the intended Python version.** Determine it from `requirements.txt`,
   current imports, and the installed baseline — not by preference.
2. **Create a project-local `.venv`** on that version.
3. **Resolve dependency compatibility.** The known conflict is
   `chromadb` 0.4.24 against `langchain-chroma` 1.1.0; `rank_bm25` and
   `langchain-huggingface` are also absent. Resolve by making the environment
   match the pins — **never** by relaxing a pin to match a broken environment.
4. **Reproduce the retrieval test baseline.** Install, then run the full suite.
   **Any failure is investigated as a real defect, not adjusted away.**
5. **Prevent dependence on the shared `~/.local` environment.** The `.venv` must
   be the only source of packages; verify nothing resolves out of `~/.local`
   (e.g. run with `PYTHONNOUSERSITE=1`).
6. Verify the three CLIs work from an unrelated CWD:
   `python -m app.ingestion.pipeline`, `python -m app.retrieval.compare`,
   `python -m app.retrieval.evaluation`.
7. Record the exact Python version and resolved dependency versions.
8. Document configuration authority: `app/config.py` is authoritative; root
   `config.py` is a compatibility shim with no consumers. **Removal is a
   follow-up, not part of this step.**
9. Confirm the secret boundary: which settings are secrets (never logged, never
   committed) versus ordinary configuration (committable).

### Tests

- **Focused:** the four currently-failing collection modules
  (`test_ingestion`, `test_retrieval`, `test_fusion`, `test_evaluation`) must
  import and pass.
- **Regression:** the full existing suite must pass at the recorded count.
- **Milestone:** ingestion re-run is a no-op (idempotency proven end to end).

### Failure/recovery

This step runs interactively and fails loudly. Partial environments are not
acceptable — a half-installed stack produces misleading import errors that
would be mistaken for code defects later.

### Acceptance criteria

- [ ] A fresh environment can be created from `requirements.txt` by following
      the written procedure, with no manual patching.
- [ ] `python -m pytest tests/ -q` passes with zero collection errors.
- [ ] Test count matches or exceeds the recorded baseline, with none removed.
- [ ] All three CLIs execute successfully from an unrelated working directory.
- [ ] The configuration authority and the secret/non-secret split are written
      down.
- [ ] The test baseline is reproducible a second time from scratch.
- [ ] A project-local `.venv` on Python 3.10 is the only package source; the
      suite passes with `PYTHONNOUSERSITE=1`, proving no dependence on
      `~/.local`.
- [ ] No environment manager other than `venv` was introduced.
- [ ] The intended Python version is documented and justified from repository
      evidence.

### Commit boundary

One commit: environment + requirements correction (if the pins prove wrong) +
documentation of configuration authority. No source-code changes.

---

## Step 1 — Introduce Persistent Operational State (SQLite)

### Reason

Every target behavior above `retrieval` depends on durable operational state.
It is deliberately sequenced **before** intelligence, because an autonomous
system that cannot record what it did cannot be audited, de-duplicated, or
recovered.

### Current state

No application-owned persistent state exists. The only durable artifacts are
`chroma_db/` (knowledge), `Auth_handling/linkedin_tokens.json` (credential), and
`logs/app.log` (append-only text, non-rotating). ADR-005 already states that
operational memory must be kept separate from the Chroma collection.

### Scope

**Added:** a state store module and its schema; a migration/bootstrap path.
**Not changed:** Chroma is untouched. No knowledge is written to the store and
no operational record enters Chroma.

Minimum entities:

```text
workflow_runs        run identity, workflow type, start/finish, outcome, failed phase
sync_checkpoints     per source: last successfully processed revision + timestamp
source_lifecycle     project lifecycle state (Step 2)
publish_intents      write-ahead intent, recorded BEFORE the API call
publications         outcome, LinkedIn post id, content hash, evidence refs
operational_failures structured error records
notifications        delivery records (Step 7)
locks                overlap prevention + stale-lock recovery
```

**`workflow_runs.outcome` is an enum with exactly the three values defined in
§2** — a run cannot be recorded any other way:

```text
DO_NOT_PUBLISH                 normal no-op; a SUCCESS; no notification
WORKFLOW_FAILED                a phase failed; persist + notify
REQUIRES_HUMAN_INTERVENTION    cannot be resolved automatically; persist + notify
```

**Publish state is a separate enum on the intent** (Step 6):

```text
intent_created · attempt_started · published · failed · unknown_requires_review
```

Storing these as constrained values — not free text — is what makes "did this
run succeed?" answerable by a query rather than by reading logs.


### Architectural placement

New lowest layer (`app/state/`), depended on by every later step. It depends on
nothing above it.

### Data/state

This **is** the state step. Location must be runtime-only and gitignored
(alongside `chroma_db/` and `logs/`). Schema versioning is required from the
first commit.

### Implementation approach

- Single-file SQLite. Enable foreign keys and WAL mode.
- **Uniqueness constraints carry the correctness guarantees**, not application
  code — e.g. at most one active publish intent per workflow run; at most one
  publication per content hash per time window.
- A `schema_version` table and a forward-only migration runner from day one.
- The store exposes narrow, typed operations. No SQL leaks into workflows.
- All timestamps stored in UTC.

### Tests

- **Focused:** schema creation; each uniqueness constraint actually rejects its
  violation; migration from empty; concurrent access behaves predictably.
- **Regression:** existing suite unaffected (the store is additive).
- **Milestone:** a run record survives process restart.

### Failure/recovery

- Store unavailable → the workflow **fails closed** and does not publish. For
  the publish path this is mandatory: no durable intent means no publish.
- Never silently swallow a write failure.

### Acceptance criteria

- [ ] The store is created automatically on first use, in a gitignored location.
- [ ] Violating the one-publish-per-run constraint is rejected by the database.
- [ ] Run outcome and publish state are constrained enums, not free text.
- [ ] Schema version is recorded and migrations re-run safely.
- [ ] A store failure prevents publishing rather than permitting it.
- [ ] No operational data is written into the Chroma collection.

### Commit boundary

One commit: store module, schema, migrations, tests.

---

## Step 2 — Define the Personal Knowledge Source Registry & Project Lifecycle

### Reason

Synchronization needs a precise, explicit definition of *what* is synchronized.
The declared workspace roots are **places to look, not sources to ingest**
(§5.3): they contain ~35 repositories, virtual environments, coursework, and —
critically — **this application itself**. Ingesting a root wholesale would put
the Personal Branding Agent's own source and runtime artifacts into the
knowledge base as "professional evidence."

### Current state

Nothing exists. Source locations are recorded as **prose inside Markdown
bodies** — and have already drifted: 48 of 71 KB files carry absolute paths,
several of them dead (a recorded path no longer exists; another differs from
reality only by a renamed directory).

An inspection of the declared roots has already established:

```text
~/LLMs/IBM          git repo, 13 commits — MONOREPO CONTAINING THIS PROJECT
~/LLMs/AI_Agents    git repo, 12 commits
~/LLMs/AI_Hackthon  plain dir; hackathon_lectures (git, 18); hackathon_practice_lab NOT a repo
~/Quizey            plain dir; Quizey_V2 (git, 27); Quizey_Platform (git, 3)
~/FastAPI           plain dir; ExitProject (git, 0 COMMITS); fastapi_venv (a venv)
~/DevOps            plain dir; jenkins-practice (14); KodeKloud_… (6); Manara/ (nested repo)
~/ALX               plain dir; ~18 nested repos, 2–274 commits
~/Portfolio         git repo, 21 commits; static site
```

### Scope

**Added:** a machine-readable source registry, an explicit inclusion/exclusion
model, and a lifecycle model. **The `data/` corpus is not restructured.**

#### Required first: complete the workspace inspection

**Do not invent include paths.** Before the registry is written, Step 2 must
complete an inspection of every declared root and record, per candidate source:

```text
exact path · is it a git repo? · commit count · dominant content type ·
is it professional evidence, coursework, tooling, or unrelated?
```

The inspection above is a starting point, not a substitute — it was performed at
limited depth. `~/ALX` in particular has ~21 entries and must be triaged
deliberately rather than ingested as a whole.

#### Per-source fields

```text
name                stable identifier
type                git | filesystem
local_path          absolute path
repo_identity       remote or root identity (git only)
ref                 branch/ref of interest (git only)
lifecycle           ACTIVE | PAUSED | COMPLETED | PLANNED
include             ordered patterns to admit
exclude             ordered patterns to reject, each with a reason
sync_state          last processed revision + timestamp (runtime, in the store)
```

The registry must support **Git-backed** and **filesystem-backed** sources,
because several roots are plain directories whose content is not in any
repository, and `FastAPI/ExitProject` is a repository with **zero commits**.

#### Self-ingestion prevention (mandatory)

`~/LLMs/IBM` contains this application. The registry must be able to express:

```text
IBM source
    include   selected project/course paths that constitute evidence
    exclude   PersonalBrandingAgent application internals, runtime state,
              and this repository's own planning documents
```

The exclusion must cover, at minimum, `chroma_db/`, `logs/`, `__pycache__/`,
`Auth_handling/` credentials, and the application's own source. **Runtime state
is never evidence.** A test must assert that no path inside the Personal
Branding Agent's own directory resolves to an ingested source.

### Architectural placement

Configuration-like data, owned by the synchronization layer. Consumed by
Step 3; read by Step 4 and Step 10.

### Data/state

Registry **definition** is version-controlled configuration. Its **runtime
state** (last processed revision, lifecycle transitions) lives in the Step 1
store — definition and state must not be conflated.

### Implementation approach

- Registry is a committed, human-editable file.
- Each entry is validated at load time: path exists, type matches reality, git
  sources actually have a repository, include/exclude patterns are well-formed.
  **A registered-but-missing path is a reported failure, not a silent skip.**
- **Lifecycle vocabulary is decided:** `ACTIVE | PAUSED | COMPLETED | PLANNED`.
  It must be explicit and stored — never derived from a Markdown heading, and
  **never inferred from inactivity**.
- Lifecycle affects **synchronization depth and priority, never visibility**:
  a `COMPLETED` project must still have deletions, renames, and new activity
  detected. `COMPLETED` must never mean `IGNORE FOREVER`.
- New activity in a `COMPLETED` source emits a **status-review signal** and
  surfaces as `REQUIRES_HUMAN_INTERVENTION` rather than being discarded.
- `PAUSED` and `PLANNED` exist and are distinct from *absent* — the corpus
  already uses both.


### Tests

- **Focused:** registry parsing; each validation failure produces a clear error;
  include/exclude patterns admit and reject correctly; lifecycle transitions.
- **Focused (self-ingestion):** **no path inside the Personal Branding Agent's
  own directory resolves to an ingested source**, and a source registered as
  `~/LLMs/IBM` cannot ingest the application's runtime directories.
- **Focused:** a `COMPLETED` source still yields changed-file candidates.
- **Regression:** ingestion and retrieval untouched.
- **Milestone:** registering a real repository and resolving its HEAD works.

### Failure/recovery

- Invalid registry → synchronization refuses to run (a partial registry silently
  dropping a source is worse than not running).
- A source that disappears → `REQUIRES_HUMAN_INTERVENTION`, with the source
  named; other sources continue.
- An exclusion pattern that would admit application internals → rejected at load
  time, not at ingestion time.

### Acceptance criteria

- [ ] The declared workspace roots are treated as places to inspect, never as
      sources to ingest.
- [ ] The workspace inspection is completed and its results recorded before the
      registry is written.
- [ ] The registry names exact sources; no recursive root scanning occurs
      anywhere in the codebase.
- [ ] **The application cannot ingest itself**, proven by test.
- [ ] A missing or invalid path is reported, never silently skipped.
- [ ] Both git-backed and filesystem-backed sources are supported, including a
      repository with zero commits and a plain directory.
- [ ] Include/exclude rules are explicit per source, each exclusion carrying a
      reason.
- [ ] Lifecycle is explicit, persisted, and never inferred from inactivity.
- [ ] A `COMPLETED` source with new commits produces a review signal.

### Commit boundary

One commit: inspection findings, registry format, loader, validation,
self-ingestion guard, lifecycle model, tests.

---

## Step 3 — Build Incremental Knowledge Synchronization

### Reason

The 24-hour workflow needs "read only what changed." The existing pipeline
already solves change detection *within* a file; git solves change detection
*across revisions*. Combining them is the whole step.

### Current state

`app/ingestion/pipeline.py` already provides content hashing, deterministic
`<sha256>:<index>` ids, change detection, idempotency, stale-vector removal, and
self-healing after partial failure. It has **no git awareness and no source
registry**.

### Scope

**Added:** a synchronization layer that runs *before* ingestion.

```text
Source Registry → change detection → candidate files → relevance policy
                → existing ingestion pipeline → content-hash validation → Chroma
```

**Not changed:** the ingestion pipeline's internals. **No second ingestion
pipeline is created.**

Two distinct responsibilities must stay distinct:

```text
Git answers:              what changed since the last processed revision?
Application state answers: what revision did the system successfully process?
```

### Architectural placement

New layer between the registry and ingestion. It **calls** the existing
pipeline; it never reimplements it.

### Data/state

`sync_checkpoints` (Step 1): per source, last successfully processed revision +
timestamp + outcome. **Runtime state only** — the registry holds definitions.

### Implementation approach

1. Resolve the source's current revision; compare with the checkpoint; compute
   changed paths. First run has no checkpoint and performs a full ingestion.
2. Apply the relevance policy to produce candidates. Reuse the existing
   precedent: `EXCLUDE_READMES` is already a **named, ordered, reversible**
   inclusion rule — generalize that pattern rather than inventing a classifier.
3. Hand candidates to the existing pipeline.
4. **The content-hash layer remains the correctness guarantee underneath.** Git
   narrows the candidate set; the hash decides what genuinely changed in
   indexable content. A commit touching only irrelevant files, or a revert
   restoring identical content, must be a no-op — and the existing hash check
   gives that for free.
5. **Renames** — the one real gap. Today a rename is handled as delete + add,
   which loses source identity. Because chunk ids are *content-addressed*, a
   rename can also produce identical ids. Resolve deliberately, using git's
   rename detection where available.
6. Advance the checkpoint **only after** the pipeline reports success.

### Tests

- **Focused:** unchanged source → zero work; changed file → exactly that file
  re-indexed; deleted file → vectors removed; renamed file → handled per the
  chosen policy; irrelevant change → no-op; no checkpoint → full ingestion.
- **Regression:** ingestion idempotency and stale-removal tests still pass.
- **Milestone:** two consecutive syncs on an unchanged source leave Chroma
  byte-identical in content.

### Failure/recovery

- **Partial run** → checkpoint does **not** advance; the next run re-processes
  the same range. This is safe because the content-hash layer makes
  re-processing idempotent.
- **Crash mid-ingestion** → self-heals on the next run (the existing pipeline
  already handles this).
- **Git command failure** → recorded as a structured failure; the source is
  marked failed; other sources proceed.

### Acceptance criteria

- [ ] A sync with no changes performs no embedding work and no writes.
- [ ] Deletions and renames are handled and reflected in Chroma.
- [ ] The checkpoint advances only after a fully successful run.
- [ ] An interrupted run is safe to re-run and reaches the same end state.
- [ ] No second ingestion path exists — the existing pipeline is reused.
- [ ] A `COMPLETED` source with new commits is detected and flagged (not ignored).

### Commit boundary

One commit: change detection, relevance policy, checkpoint advancement, rename
policy, tests.

---

## Step 4 — Build the Personal Branding Context & Evidence Layer

### Reason

Nothing exists between retrieval and generation. Without it, generation would
concatenate raw chunks into one prompt — which cannot distinguish *"I found
supporting evidence"* from *"I found something vaguely related."*

### Current state

`RetrievedDocument` carries `content, score, source, metadata, strategy,
chunk_id, rank`, with metadata including `category`, `document_type`,
optional `domain`/`status`/`evidence_state`/`project`, and `content_hash`.

**Absent:** freshness (no timestamp is written at all), confidence, coverage, and
any insufficient-evidence signal. An empty result list is the only "nothing
found" indication.

### Scope

**Added:** the smallest useful assembly layer. **Not** a summarizer, **not** a
fact database, **not** a replacement for `data/`.

It must assemble grounded context across the existing knowledge boundaries:

```text
identity            projects            evidence          vision/goals
positioning         certificates        writing style     stories/lessons
skills              current activity    publishing constraints
```

while preserving:

```text
provenance · source identity · evidence hierarchy · freshness · coverage ·
insufficient-evidence state · separation of evidence from positioning/style
```

**The `data/` structure is kept.** No generic `PersonalProfile` abstraction
replaces it unless evidence shows the existing structure cannot work.

### Architectural placement

New layer between retrieval and generation. Consumes `RetrievalResult`; produces
a structured context object.

### Data/state

No new persistence required. May read Step 1 run records to express "current
activity." Freshness requires either a new metadata field written during
ingestion (Step 3) **or** derivation from the sync checkpoint — decide when
implementing, and record the choice.

### Implementation approach

1. **Group** retrieved material into named sections, mapped from `category` /
   `document_type` — values that already exist reliably.
2. **Order deterministically** within each section using the evidence hierarchy
   the corpus already defines in `data/evidence/README.md` and
   `data/audit/README.md` (concrete repository evidence first; inference last).
3. **Report coverage honestly** — per section: item count, evidence states
   present, and whether the section is empty.
4. **Keep evidence and narrative separate.** Facts that support claims and the
   voice/positioning that shapes communication must not be blended into one blob.
5. **Expose an explicit insufficient-evidence state.** This is the single most
   important output for Step 9 — without it, the generator cannot know it lacks
   support.

### Tests

- **Focused:** section grouping from metadata; deterministic ordering; coverage
  counts; empty section produces an explicit insufficient state; style/positioning
  never counted as evidence.
- **Regression:** retrieval results unchanged.
- **Milestone:** a context object for a known topic contains the expected
  evidence with correct provenance.

### Failure/recovery

- No retrieved documents → return a context object that explicitly reports
  insufficiency. **Never return an empty object that downstream code could read
  as success.**
- A retrieval failure propagates and fails the run rather than silently
  degrading to an evidence-free context.

### Acceptance criteria

- [ ] Context is assembled into named sections, not one concatenated blob.
- [ ] Every item retains source, chunk id, and evidence state.
- [ ] Ordering is deterministic and follows the documented evidence hierarchy.
- [ ] Coverage is reported per section, including empty ones.
- [ ] Insufficient evidence is a distinguishable, first-class outcome.
- [ ] Evidence and positioning/style remain separate fields.

### Commit boundary

One commit: context assembly, evidence hierarchy ordering, coverage reporting,
insufficiency state, tests.

---

## Step 5 — Harden the LinkedIn Integration for Autonomous Use

### Reason

Publishing is **already proven** against the real API. The task is not to
re-prove it — it is to turn an interactive script into a service an unattended
workflow can call.

### Current state

`Auth_handling/` contains the working path. Known defects:

- **Token path is inconsistent across the three scripts, and this is live.** As
  currently on disk: `test_post.py` and `test_credentials.py` resolve the token
  file relative to `__file__` (these two fixes exist as **uncommitted
  working-tree changes**), while `linkedin_oauth_setup.py` —
  **the script that creates the token** — still uses the literal relative path
  `TOKEN_FILE = "linkedin_tokens.json"`. Running the setup script from any
  directory other than `Auth_handling/` therefore writes the token somewhere the
  two readers will never look. This must be made consistent before autonomous
  use.
- `load_dotenv()` is still called with **no path** in all three scripts.
- `test_post.py` has **no `timeout=`** and no exception handling around the POST
  (unlike `test_credentials.py`, which sets timeouts on all four of its calls).
- Failures **print** status and body but do not raise or return a status — a
  caller cannot programmatically distinguish success from failure.
- Publishing is gated behind an interactive `input()`.
- The API version is hardcoded in the request headers and must become
  configuration, since versioned headers expire on a rolling cadence.
- Token renewal does not work (§5.2).

### Scope

**Added:** a reusable integration service wrapping the proven path, **plus
explicit credential-lifecycle handling**.
**Not rebuilt:** the OAuth flow, the endpoint, the payload, or the person-URN
resolution — all proven and retained.

Must provide:

```text
publish_to_linkedin(post_text) -> structured result
```

**Decided: the application must not assume automatic refresh capability.** It
must remain correct when automatic refresh is unavailable — which is the
situation today (§5.2). If programmatic refresh is later *verified* to work for
this LinkedIn application, the service may support it; **`offline_access` alone
is not evidence that it does.**

### Architectural placement

New integration layer (`app/integrations/linkedin/`). Called by the publish
service (Step 6). Never called directly by the Agent.

### Data/state

Produces a structured result. **Does not** persist — persistence belongs to
Step 6, which owns the write-ahead intent. The integration must never record
success on its own authority.

### Implementation approach

1. **CWD-independent paths** — resolve the token file and `.env` through the
   existing absolute-path module, matching how `app/` already behaves.
2. **Bounded timeouts** on every request.
3. **Structured results**, never prints: outcome, HTTP status, post id when
   returned, error category, retryable flag, human-readable message.
4. **Error classification** — the architecture docs already specify the desired
   categories (authentication, permission, validation, rate limit, transport,
   unknown). Implement that table rather than inventing another.
5. **Remove interactive confirmation.** An unattended workflow cannot block on
   `input()`.
6. **API version is configuration**, not a literal.
7. **Secrets never logged.** The existing redaction filter covers the configured
   secret values; verify the token itself is included.
8. **No blind retries.** Publishing is not idempotent; retry policy is owned by
   Step 6.

### Credential lifecycle (required, not optional)

```text
token expiry detection          read expiry from the stored credential; never guess
expiry warning                  detect BEFORE expiry that reauthorization is approaching
clear authentication failure    a distinct, classified state — not a generic error
email notification              via Step 7
manual re-authorization         the documented fallback
```

When the token is expired or unusable:

```text
workflow → authentication failure → persist → notify → do not blindly retry
```

This terminates the run as `REQUIRES_HUMAN_INTERVENTION`, not `WORKFLOW_FAILED`
— the system is behaving correctly; it needs a human, and retrying cannot help.

The expiry timestamp must be recorded in operational state so the warning fires
ahead of the failure rather than after it.

### Tests

- **Focused:** success classification; each error category from a simulated
  response; timeout handling; a missing/expired token is reported as an auth
  failure; timeouts are actually set.
- **Focused (lifecycle):** an expired token produces
  `REQUIRES_HUMAN_INTERVENTION`, not a retry; an approaching expiry produces a
  warning before failure; no refresh is attempted when none is available.
- **Regression:** nothing in the retrieval/ingestion suites changes.
- **Milestone:** one manual, explicit, non-interactive publish against real
  LinkedIn succeeds and returns a post id.

### Failure/recovery

Every failure returns a classified, structured result. The integration never
raises into a state where the caller cannot tell whether a post exists.

Authentication expiry is **not** treated as a transient error and is never
retried.

### Acceptance criteria

- [ ] The service works from any working directory.
- [ ] Every request has a timeout.
- [ ] Failures are structured and classified, never printed-and-forgotten.
- [ ] No interactive prompt exists on the publish path.
- [ ] The API version is configurable and its value is recorded with each attempt.
- [ ] No token value appears in logs, errors, or results.
- [ ] Token expiry is detected, warned about ahead of time, and recorded.
- [ ] Token expiry yields `REQUIRES_HUMAN_INTERVENTION` and triggers a
      notification.
- [ ] The system is correct **without** automatic refresh, and does not assume
      `offline_access` provides it.
- [ ] A real post published through the service returns its LinkedIn post id.

### Commit boundary

One commit: integration service, error classification, structured results,
timeouts, path reconciliation, credential lifecycle, tests.

---

## Step 6 — Build Persistent Publishing, Idempotency & Recovery

### Reason

This is the hardest requirement in the system. Publishing has an irreversible
external side effect, there is **no read-back** to reconcile against (§5.1), and
the target guarantees *at most one post per run*.

### Current state

Nothing persists. `test_post.py` confirms intent only via an interactive prompt.
There is no run identity, no intent record, no duplicate detection, and no
ambiguous-outcome state.

### Scope

**Added:** the publish service, its state machine, and the deterministic
**publishing-history read service**.

#### State machine

```text
intent created  →  attempt started  →  published
                                   →  failed
                                   →  unknown / requires review
```

**Not claimed:** exactly-once delivery to LinkedIn. That guarantee is not
achievable here and must not be promised. The real guarantee is:

```text
at most one publication attempt reaches the final publish gate per workflow run
+ durable publication intent
+ explicit ambiguous outcome state
+ fail-closed recovery
```

#### Publishing-history read service (required by Decision 2)

Because publishing history is **not** indexed into Chroma (§6.1), the Agent
needs a deterministic service to answer:

```text
What have I published recently?
Which topics did I use?
Which evidence did I use?
Which projects have I talked about recently?
```

These are **SQLite queries**, exposed as typed read methods — not vector search.
The service is read-only with respect to history and must never return generated
content as evidence. Every result is attributable to a stored publication record,
never inferred.

### Architectural placement

Service layer between the Agent's decision and the LinkedIn integration. Owns
all publishing state transitions **and** is the only reader of publishing
history. The Agent never queries the state store directly.

### Data/state

`publish_intents` and `publications` (Step 1):

```text
run identity · publication identity · timestamp · content or content hash
LinkedIn post id (when returned) · topic/angle · evidence references
verification outcome · generation metadata · final outcome
```

Evidence references must be stored as **source path + content hash**, because
the corpus is resynchronized every 24 hours (Step 3) — without the hash, a later
audit cannot distinguish "grounded in evidence that has since changed" from
"never grounded."

### Implementation approach

1. **Write the intent before the API call.** With no read-back, the durable
   intent is the *only* duplicate protection that exists.
2. Enforce `MAX_PUBLISHES_PER_RUN = 1` with a **database constraint**, not
   application logic.
3. Resolve the intent on return: success → `PUBLISHED` with the post id;
   classified failure → `FAILED`; timeout or ambiguous transport outcome →
   `UNKNOWN`, requiring review.
4. **On `UNKNOWN`, do not republish.** Since the post cannot be read back, the
   only safe resolution is to refuse and surface it for human confirmation.
5. **Duplicate checks, in three distinct forms** — they need different data:
   - *Exact:* deterministic content hash.
   - *Near:* similarity against recently published content (reuse the existing
     embedding stack).
   - *Topic/evidence overuse:* requires stored topic and evidence references —
     text similarity alone cannot answer *"have I overused this project?"*
6. Do not blind-retry. A conflict-style response may indicate the original
   request succeeded; retrying could double-publish.

### Tests

- **Focused:** intent persisted before the call; one-publish-per-run enforced by
  the database; exact duplicate rejected; near duplicate flagged; topic overuse
  detected; timeout → `unknown_requires_review` and **not** republished; a crash
  between intent and response leaves a recoverable unknown state.
- **Focused (read service):** "what did I publish recently" returns only stored
  records; topic and evidence queries are exact; an empty history returns empty,
  not an error; **no result is ever returned as evidence**.
- **Regression:** prior steps unaffected.
- **Milestone:** simulated failure injection at each transition leaves the store
  in a consistent, explainable state.

### Failure/recovery

```text
POST succeeds, local process crashes before recording
    → intent exists, no outcome  →  unknown_requires_review
    →  REQUIRES_HUMAN_INTERVENTION  →  never auto-retried
```

This case must be **prevented by design**, not repaired afterward, because
repair is impossible without read access.

### Acceptance criteria

- [ ] No publish occurs without a prior durable intent.
- [ ] A second publish attempt in the same run is rejected by the database.
- [ ] An ambiguous outcome is persisted and never blindly retried.
- [ ] Exact duplicates are impossible; near duplicates and topic overuse are
      detectable.
- [ ] Evidence references are stored with content hashes.
- [ ] Publishing state is never written into Chroma.
- [ ] Publishing history is queryable deterministically without retrieval.
- [ ] No generated post can be returned as evidence about the user.

### Commit boundary

One commit: publish service, state machine, duplicate detection, history read
service, tests.

---

## Step 7 — Build Operational Failure Notifications via Email

### Reason

The system runs unattended. Failures that are only written to a log file are
effectively invisible. Notification must be deterministic infrastructure — **not**
an Agent decision.

### Current state

Nothing exists. There is no notification path of any kind.

### Scope

**Added:** an **SMTP-based** notification service reachable from **every**
autonomous workflow phase.

```text
workflow phase fails → persist failure → notification service → email → user
```

#### Every phase must be able to reach it

Notification is deterministic application infrastructure. **The Agent is not
responsible for remembering to notify the user** — a phase that fails inside the
Agent still notifies, because the workflow wraps it.

| Layer | Notification reachable |
|---|---|
| Source registry loading | ✓ |
| Sync / git change detection | ✓ |
| File discovery & relevance policy | ✓ |
| Ingestion & embedding | ✓ |
| Retrieval | ✓ |
| Context construction | ✓ |
| Generation | ✓ |
| Verification | ✓ |
| Agent reasoning | ✓ (via the workflow wrapper, never by Agent choice) |
| LinkedIn authentication / permission / transport / publish | ✓ |
| Ambiguous publication result | ✓ |
| State store | ✓ |
| Scheduling & lock handling | ✓ |
| Recovery | ✓ |

#### Transport (decided)

SMTP, provider-agnostic at the interface, **configured initially for Gmail**.
All values come from environment/configuration — **nothing hardcoded**:

```text
SMTP host · SMTP port · sender address · recipient address
username (if required) · password / app-password (if required) · TLS configuration
```

Prefer the **Python standard library** SMTP support unless repository evidence
justifies another dependency. Automated tests use a **fake/test transport** and
make no network calls.

### Architectural placement

Cross-cutting infrastructure beneath the workflows. Every phase reports through
the failure store; the notification service consumes it. No phase calls the
Agent to notify.

### Data/state

`operational_failures` and `notifications` (Step 1), including delivery outcome
and the SMTP/TLS configuration used.

### Implementation approach

- Email content carries: **workflow, phase, timestamp, run ID, error category,
  human-readable explanation, retryable-or-not, human-intervention-required-or-not**.
- **Never include secrets.** The existing redaction filter is reused, not
  bypassed.
- **Notification delivery failure is a distinct outcome from workflow failure.**
  The two must be separately recorded and separately visible. A delivery failure
  **must never replace or erase the original workflow failure** — the failure
  record is written first and independently, before any send is attempted.
- Credentials come from configuration and are covered by the existing redaction
  filter.
- Noise control: repeated identical failures should not produce unbounded email.
  Deduplicate or rate-limit, but **never suppress the first occurrence**.

### Tests

- **Focused:** a failure in each phase produces a notification; the message
  contains the required fields; no secret value ever appears; the fake transport
  captures messages in tests.
- **Focused (distinctness):** a **delivery failure** still leaves the original
  **workflow failure** recorded and visible — the two outcomes are separately
  observable.
- **Focused:** SMTP configuration is read from configuration, never hardcoded;
  a missing credential produces a clear configuration error.
- **Regression:** prior steps unaffected.
- **Milestone:** a deliberately injected failure end-to-end produces exactly one
  email through the fake transport.

### Failure/recovery

- Delivery failure → recorded as a delivery failure, original workflow failure
  preserved, retried or surfaced on the next run.
- Notification service unavailable → the workflow still completes its own
  failure handling.
- A `DO_NOT_PUBLISH` run sends **no** notification — a normal no-op is not a
  failure.

### Acceptance criteria

- [ ] Every phase in the reachability table can raise a notifiable failure.
- [ ] A notification is sent for a failed unattended run.
- [ ] No notification is sent for a normal `DO_NOT_PUBLISH` run.
- [ ] No secret value can appear in a notification.
- [ ] A transport failure does not erase or mask the original failure, and the
      two are separately recorded.
- [ ] Tests use a fake transport and make no real network calls.
- [ ] SMTP settings and credentials come from configuration only.
- [ ] Duplicate suppression never hides a first occurrence.

### Commit boundary

One commit: notification service, SMTP transport, failure wiring, fake
transport, tests.

---

## Step 8 — Build Grounded Post Generation

### Reason

With context assembly (Step 4) and publishing infrastructure (Steps 5–6) in
place, generation becomes a bounded, testable transformation rather than the
center of the system.

### Current state

No generation layer exists. `app/config.py` already holds the model id,
OpenRouter base URL, and generation parameters; `app/retrieval/multi_query.py`
demonstrates the working OpenRouter client pattern, including a deterministic
fallback.

### Scope

**Added:** a generation layer producing a candidate post from assembled context.

Inputs: `context + selected evidence + publishing history constraints + writing
style + content rules`.

Returns a **structured result**, not a bare string.

### Architectural placement

Between context assembly and verification. Called by the workflow; callable
directly with an explicit context for testing.

### Data/state

**Writes no state.** Returns a draft and its metadata to the caller. Persistence
happens only at the publish step.

### Implementation approach

- LCEL chain, consistent with the existing stack.
- The prompt receives **assembled sections**, not a concatenated chunk dump.
- Writing-style and positionining guidance come from the existing knowledge
  files, not a hardcoded prompt.
- The chain must be able to receive an **insufficient-evidence signal** and be
  expected to decline rather than fabricate.
- Model id, prompt/version identifier, and parameters are returned with the
  draft for the audit record.
- Generation failure is a distinct outcome from a low-quality draft.

### Tests

- **Focused:** structured output shape; the chain is invoked with a fake LLM;
  insufficient-evidence context produces a declining result; prompt assembly is
  deterministic; no real API call in tests.
- **Regression:** retrieval and ingestion untouched.
- **Milestone:** a draft generated from a known evidence set cites only sources
  present in that set.

### Failure/recovery

A generation failure notifies (Step 7) and ends the run with `DO_NOT_PUBLISH`.
There is **no valid degraded post** — unlike retrieval, generation cannot
usefully fall back to a weaker result.

### Acceptance criteria

- [ ] Generation consumes assembled context, not raw chunks.
- [ ] Output is structured and carries model/prompt metadata.
- [ ] Insufficient evidence produces a declining outcome, not a fabricated post.
- [ ] Tests run fully offline with a fake LLM.
- [ ] Style and positioning come from knowledge files, not hardcoded text.

### Commit boundary

One commit: generation chain, prompt assembly, structured result, tests.

---

## Step 9 — Build Evidence Verification & Revision Gates

### Reason

The system must prevent coursework being presented as professional experience,
local projects as production systems, and plausible capability as verified fact.
The repository already contains a strong evidence policy; this step
**operationalizes** it rather than inventing a different philosophy.

### Current state

**No verification code exists.** Strong policy does exist in
`data/evidence/` (seven evidence states), `data/audit/` (hierarchy, forbidden
inferences, correction policy, worked audit examples), and `docs/decisions/`
(ADR: evidence grounding, supported claims over plausible claims).

### Scope

**Added:** the gate.

```text
DRAFT → VERIFY → PASS
               → REVISE
               → REJECT
```

**Deterministic checks (authoritative):**

```text
citation exists · source exists · cited evidence actually available ·
evidence state satisfies policy · exact factual references validated ·
required evidence is not empty
```

**LLM-assisted checks (advisory, and they run only after deterministic checks
pass):**

```text
claim semantically supported · claim strength exceeds evidence strength ·
paraphrase changed meaning · wording exaggerates experience
```

### Architectural placement

Not a pipeline stage — a **function** called by both the decision path and the
revision loop. A failed verification routes to revision, not straight to
rejection.

### Data/state

Verification outcomes are persisted with the publication record (Step 6):
which claims were checked and how they fared.

### Implementation approach

- Deterministic checks first; they are cheap and strict. Semantic checks are
  expensive and advisory.
- Reuse the corpus's existing vocabulary rather than defining new categories.
- Reuse the existing lexical-overlap primitive where exact-string checking is
  appropriate, and know its limit for paraphrase.
- **Revision limits are enforced** — an unbounded revise loop is a failure mode,
  not a feature. `REJECT` after the limit is a correct outcome.
- An unverifiable claim is rejected, not tolerated.

### Tests

- **Focused:** a claim citing a non-existent source fails; a claim whose evidence
  state is too weak fails; a fabricated exact reference fails; a supported claim
  passes; revision limit terminates the loop; deterministic checks run before
  LLM checks.
- **Regression:** prior steps unaffected; tests need no network.
- **Milestone:** the documented forbidden inferences (coursework→experience,
  local→production) are each caught by a fixture.

### Failure/recovery

- Verification infrastructure failure → **fail closed** (`DO_NOT_PUBLISH`), never
  default to `PASS`.
- LLM-assist unavailable → deterministic gates still run; the run may still
  publish if deterministic checks pass, and the degraded verification mode is
  recorded.

### Acceptance criteria

- [ ] Deterministic gates are authoritative and cannot be bypassed.
- [ ] The three documented false-inference classes are caught by tests.
- [ ] Revision is bounded and terminating.
- [ ] Verification failure never results in publishing.
- [ ] Outcomes are persisted with the publication record.

### Commit boundary

One commit: deterministic gates, semantic checks, revision loop, tests.

---

## Step 10 — Build the Autonomous Branding Agent

### Reason

Steps 1–9 build deterministic capability. This step adds the *only* genuine
reasoning the system needs, bounded by everything already built.

### Current state

No agent exists. `app/retrieval/engine.py` explicitly states it is
*"deliberately NOT an agent."*

### Scope

Introduce a **single bounded Agent** that reasons about:

```text
content opportunities · topic · angle · evidence selection ·
whether there is sufficient value to publish
```

The Agent must **not** bypass: state rules, evidence gates, duplicate rules,
max-post limits, or publication safeguards.

### Architectural placement

Above generation and verification; below the workflows. The Agent proposes; the
workflow disposes.

### Data/state

Reads context (Step 4) and publishing history **through the Step 6 read
service** — never by querying the store directly. **Writes no state** — recording
is a deterministic workflow responsibility, or the system could "forget" to
record.

### Implementation approach

- **One** agent. No multi-agent decomposition.
- No graph framework. The decision is binary plus a bounded revision loop.
- The Agent's outputs are **proposals** validated by deterministic gates.
- The Agent must be able to answer `DO_NOT_PUBLISH`, and that must be a
  first-class success, not a failure.
- Topic and angle selection may use retrieval strategy selection — note that
  `RetrievalEngine` accepts a strategy but nothing currently chooses one.

### Tests

- **Focused:** `DO_NOT_PUBLISH` is reachable and respected; the Agent cannot
  exceed the post limit; it cannot publish without passing gates; evidence
  selection is constrained to retrieved sources; the decision is reproducible
  under a fake LLM.
- **Regression:** full prior suite.
- **Milestone:** a full simulated run reaches a decision end-to-end with fakes.

### Failure/recovery

Agent reasoning failure → `DO_NOT_PUBLISH` plus a notification. **Never** a
fallback that publishes something weaker.

### Acceptance criteria

- [ ] Exactly one agent exists.
- [ ] `DO_NOT_PUBLISH` is a normal, reachable outcome.
- [ ] The Agent cannot circumvent any deterministic gate.
- [ ] Evidence selection is limited to what retrieval actually returned.
- [ ] Tests run deterministically with fakes.

### Commit boundary

One commit: agent, decision logic, bounded reasoning, tests.

---

## Step 11 — Build the 24h Knowledge-Sync and 8h Branding Workflows

### Reason

Two independent workflows with different periods, different failure domains, and
different blast radii must be explicit, separately executable units.

### Current state

No workflow entry points exist. All current entry points are `python -m` CLIs
that work from any working directory.

### Scope

**Added:** two explicit entry points.

```text
python -m app.workflows.sync        (24h)
python -m app.workflows.branding    (8h)
```

Each produces a **structured run result** and is independently executable and
testable without a scheduler.

### Architectural placement

Top-level orchestration. The workflows own sequencing, error handling, state
recording, and notification. They never contain reasoning.

### Data/state

Owns `workflow_runs`: run id, type, start/finish, status, failed phase,
structured error. Each phase transition is recorded.

### Implementation approach

- Workflow decides *sequencing*; the Agent decides *content*.
- **The sync workflow and publishing workflow remain separate.** Sync must never
  publish; publishing must never trigger ingestion.
- Every phase is wrapped so a failure identifies *which phase failed*.
- Publishing is never retried automatically once ambiguous.
- `0 or 1` posts is enforced by the workflow, backed by the Step 6 constraint.

#### Every run terminates in one of the three outcomes (§2)

```text
DO_NOT_PUBLISH                 exit 0        no notification
WORKFLOW_FAILED                exit non-zero  persist + notify
REQUIRES_HUMAN_INTERVENTION    exit non-zero  persist + notify (distinct code)
```

- The outcome is **recorded on the run**, not inferred from an exit code at read
  time.
- `REQUIRES_HUMAN_INTERVENTION` uses a **distinct exit status** from
  `WORKFLOW_FAILED`, so a scheduler can distinguish "it broke" from "it needs
  you."
- The workflow — never the Agent — classifies the outcome and decides whether to
  notify.

### Tests

- **Focused:** each workflow runs to completion with fakes; a failure in each
  phase is attributed correctly; exit codes are correct per outcome; the sync
  workflow never publishes; the branding workflow never ingests; a no-opportunity
  run exits successfully having published nothing and sending no notification.
- **Focused:** a `REQUIRES_HUMAN_INTERVENTION` condition (expired token,
  ambiguous publication, missing source) produces its distinct outcome and
  exactly one notification.
- **Focused:** a `WORKFLOW_FAILED` condition produces its distinct outcome and a
  notification.
- **Regression:** full prior suite.
- **Milestone:** both workflows run back-to-back against a fixed fixture set
  with deterministic outcomes.

### Failure/recovery

Any phase failure → failure recorded → notification sent → workflow exits
non-zero. **Partial success is recorded as partial, never as success.**

### Acceptance criteria

- [ ] Both workflows are separately invocable without a scheduler.
- [ ] Each returns a structured result and a meaningful exit code.
- [ ] All three outcomes are reachable, recorded, and distinguishable.
- [ ] A `DO_NOT_PUBLISH` run is a success and sends no notification.
- [ ] `REQUIRES_HUMAN_INTERVENTION` has a distinct exit status.
- [ ] Sync cannot publish; branding cannot ingest.
- [ ] Every failure names its phase.
- [ ] The Agent never decides whether a failure is notified.

### Commit boundary

One commit: both workflows, run recording, exit codes, tests.

---

## Step 12 — Add External Scheduling, Locks & Recovery

### Reason

The two workflows must run unattended, without overlapping, and recover safely
from interrupted runs.

### Current state

No scheduler, no lock, no run state. `app/` contains no scheduling references.

### Scope

**Added:** a thin external trigger plus overlap protection.

```text
external scheduler → python -m app.workflows.<name>
```

**Not added:** a long-running Python scheduler, a queue, or a worker system.

### Architectural placement

Outside the application. The scheduler triggers; the workflow executes.

### Data/state

`locks` (Step 1): an overlap guard with stale-lock detection and safe recovery.
Lock state must be recoverable after an ungraceful exit.

### Implementation approach

- Compare OS-level options (cron vs systemd timer) and choose based on the
  deployment environment. Both are thin triggers; neither adds a runtime
  dependency.
- **Overlap is real, not hypothetical** — an 8-hour workflow that retries can
  outlive its own window.
- **Stale locks must be recoverable** without manual intervention, but a stale
  lock must never silently permit a concurrent run.
- The 8-hour window is a trigger interval, **not** a cadence that must produce
  posts.
- Scheduler exit status must reflect workflow outcome so failures are visible
  outside the application.

### Tests

- **Focused:** a second invocation while locked is rejected; a stale lock is
  recovered; an interrupted run leaves a recoverable state; the scheduler command
  passes through the workflow's exit code.
- **Regression:** workflows still run standalone.
- **Milestone:** two scheduled invocations in immediate succession produce one
  run and one rejection.

### Failure/recovery

- Lock held → exit without running, recorded.
- Stale lock → recovered, recorded.
- Interrupted run → detected on next invocation and reported.

### Acceptance criteria

- [ ] Overlapping invocations cannot run concurrently.
- [ ] Stale locks recover automatically and are logged.
- [ ] A scheduled failure surfaces a non-zero exit status.
- [ ] No long-running Python process is required.
- [ ] Workflows remain independently executable without the scheduler.

### Commit boundary

One commit: lock mechanism, scheduler configuration, recovery, tests.

---

## Step 13 — End-to-End Autonomous Evaluation

### Reason

Unit tests prove components; only end-to-end scenarios prove the *system* behaves
correctly when things go wrong — which is the common case for an unattended
process.

### Current state

Retrieval evaluation exists (gold set, Hit@K, MRR). No workflow-level or
content-level evaluation exists.

### Scope

Realistic full-workflow scenarios, with deterministic fakes for external
services:

```text
no-change sync                          changed Git source
completed project with new commit       deleted file
normal publication                      no publication opportunity
duplicate candidate                     weak evidence
generation failure                      verification failure
LinkedIn timeout                        ambiguous publication
token expired                           notification delivery failure
duplicate scheduled invocation          recovery after interrupted run
self-ingestion attempt                  unregistered source path missing
```

Each scenario asserts its **recorded outcome** (`DO_NOT_PUBLISH`,
`WORKFLOW_FAILED`, or `REQUIRES_HUMAN_INTERVENTION`), not merely that it ran.

At least one **manual/integration path** for real LinkedIn publishing is
retained.

### Architectural placement

Evaluation layer, alongside the existing retrieval evaluation.

### Data/state

Uses an isolated test state store. **Never** the production database.

### Implementation approach

- Fakes for LinkedIn, the LLM, and email.
- The real LinkedIn path stays manual and explicitly invoked.
- Assertions target **outcomes and state**, not log strings.
- The ambiguous-publication scenario is the most important test in the suite.

### Tests

- **Focused:** each scenario above as its own test.
- **Regression:** full unit suite.
- **Milestone:** the full scenario set runs deterministically from a clean state.

### Failure/recovery

The suite itself must be deterministic; any flakiness is a defect to fix, not
to retry.

### Acceptance criteria

- [ ] Every listed scenario has a test.
- [ ] Tests make no real network calls.
- [ ] Each scenario asserts its recorded outcome, not just completion.
- [ ] The ambiguous-publication case is verified to never double-publish.
- [ ] The interrupted-run case verifies recovery.
- [ ] The self-ingestion case verifies the application cannot ingest itself.
- [ ] A manual real-LinkedIn path remains available and documented.

### Commit boundary

One commit: end-to-end scenarios, fixtures, fakes, manual path documentation.

---

## Step 14 — Operational Documentation, Deployment & Final Hardening

### Reason

An unattended system is only as operable as its documentation. Everything a
future operator needs must exist outside the code.

### Current state

`docs/architecture/` and `docs/retrieval/` exist and are good.
`docs/evaluation/` and `docs/operations/` are **empty directories**.
`docs/phases/` covers only phases 1–2. `docs/decisions/ADRs/` holds an index
referencing ADRs that have no files.

### Scope

Document:

```text
final architecture · state model · source registry · sync lifecycle ·
LinkedIn integration · authentication lifecycle · publishing lifecycle ·
evidence policy · notification behavior · scheduler setup ·
recovery procedures · manual intervention · environment configuration ·
security · operational commands
```

### Architectural placement

Documentation. No code change beyond what documentation reveals as necessary.

### Data/state

The **state model must be documented as a schema** — the tables, their
constraints, and what each guarantees.

### Implementation approach

- Write the documents the directory structure already promises.
- Write real ADR files for the decisions already indexed as accepted, plus new
  ADRs for the decisions taken during Steps 0–13.
- Document **manual intervention boundaries** explicitly (§11).
- Document the security posture: what is secret, what is redacted, what is
  gitignored.

### Tests

- **Focused:** the documented reproduction procedure works from scratch.
- **Regression:** full suite green.
- **Milestone:** a clean checkout plus the documentation alone reproduces a
  working, scheduled system.

### Failure/recovery

Documented recovery procedures must be *exercised* at least once during this
step, not merely written.

### Acceptance criteria

- [ ] Every promised document exists.
- [ ] The state model is documented as a schema.
- [ ] Real ADR files exist for all indexed decisions.
- [ ] Manual intervention boundaries are explicit.
- [ ] A clean environment can be reproduced from documentation alone.

### Commit boundary

One commit (or a small series): documentation, ADRs, operational procedures.

---

# 9. Milestones

| # | Milestone | Steps | Proves |
|---|---|---|---|
| M1 | Reproducible foundation | 0, 1 | The project runs and can remember what it did |
| M2 | Known sources, incremental sync | 2, 3 | Knowledge stays current without re-indexing everything |
| M3 | Grounded context | 4 | The system can tell evidence from relevance |
| M4 | Safe publishing | 5, 6, 7 | Publishing is a service; failures are visible; ambiguity is contained |
| M5 | Grounded generation & gates | 8, 9 | Nothing publishes without support |
| M6 | Bounded autonomy | 10, 11 | The Agent decides; the workflow enforces |
| M7 | Unattended operation | 12, 13 | It runs on a schedule and survives failure |
| M8 | Operable system | 14 | Someone else could run it |

---

# 10. Definition of Done

**Knowledge**

- [ ] Ingestion is idempotent and content-hash driven
- [ ] Retrieval is evaluated against a gold set
- [ ] Sources are explicitly registered from an inspected workspace; no root or
      home-directory scanning
- [ ] The application cannot ingest itself
- [ ] Synchronization is incremental and checkpointed
- [ ] Deletions, renames, and partial runs are handled correctly
- [ ] Lifecycle is explicit, and never inferred from inactivity

**Grounding**

- [ ] Context is assembled with provenance, hierarchy, coverage, and freshness
- [ ] Insufficient evidence is a first-class outcome
- [ ] Evidence and positioning/style remain separate

**Publishing**

- [ ] The LinkedIn service is non-interactive, timeout-bounded, and classified
- [ ] A durable intent precedes every publish
- [ ] At most one post per run, enforced by constraint
- [ ] Ambiguous outcomes fail closed and are never blindly retried
- [ ] Publishing history is durable and authoritative in the state store

**Autonomy**

- [ ] The Agent can return `DO_NOT_PUBLISH`, and that is a success
- [ ] The Agent cannot bypass any deterministic gate
- [ ] Both workflows run independently and produce structured results
- [ ] All three outcomes — `DO_NOT_PUBLISH`, `WORKFLOW_FAILED`,
      `REQUIRES_HUMAN_INTERVENTION` — are recorded and distinguishable
- [ ] Scheduling cannot overlap; stale locks recover

**Operations**

- [ ] Every phase failure is persisted and notified by email
- [ ] A normal no-op run sends no notification
- [ ] Notification delivery failure never masks the original workflow failure,
      and the two are separately recorded
- [ ] LinkedIn token expiry is detected, warned about, and notified
- [ ] No secret appears in logs, notifications, tests, or documentation
- [ ] Recovery procedures are documented **and exercised**
- [ ] Tests cover every layer and every listed failure scenario

---

# 11. Manual Intervention Boundaries

Explicit, because "autonomous" must have a defined edge. Each condition below
maps to the outcome vocabulary in §2.

## `REQUIRES_HUMAN_INTERVENTION` — stop, persist, notify

```text
1. A publication outcome is ambiguous (a post may have succeeded).
2. The LinkedIn token has expired or is unusable and cannot be renewed automatically.
3. A registered source path is missing, or is no longer a repository.
4. The state store is unavailable or corrupted.
5. A completed project has received relevant new activity (status-review signal).
6. An unrecoverable configuration problem.
```

**Never retried automatically.** Each persists its condition and notifies.

Note on (5): new activity in a `COMPLETED` source is a **review signal**, not a
crash. It notifies and surfaces for review; it does not require retrying the
sync, and it must not cause the source to be silently ignored.

Note on (4): a store failure on the publish path is **fail-closed** — no store,
no publish.

## `WORKFLOW_FAILED` — persist, notify, exit non-zero

```text
generation service failure · retrieval error · ingestion error ·
LinkedIn transport failure · embedding failure · network timeout
```

## `DO_NOT_PUBLISH` — a success, no notification

```text
no sync changes · no publishing opportunity · duplicate candidate ·
weak evidence · revision limit exhausted without a passing draft
```

## Handled automatically, without notification

```text
stale locks · interrupted runs (self-healing) ·
ordinary API failures with a retryable classification
```

**Rule:** when in doubt, the system does less (publishes nothing) and reports
more.

---

# 12. Decisions

## 12.1 Resolved

| # | Decision | Resolution | Where it applies |
|---|---|---|---|
| 1 | Knowledge source scope | **Explicit source registry.** Declared roots are inspected, never ingested wholesale. Include/exclude per source. The app must not ingest itself. | Step 2 |
| 2 | Publishing history | **Not indexed into Chroma in V1.** SQLite is authoritative; a deterministic read service answers the Agent's history questions. A derived view only if evaluation proves a real benefit. | §6.1, Step 6 |
| 3 | Email transport | **SMTP**, provider-agnostic interface, configured for Gmail. All values from configuration. Stdlib preferred. Fake transport in tests. | Step 7 |
| 4 | LinkedIn token lifecycle | **No assumed automatic refresh.** Expiry detection + warning + clear auth-failure state + notification + manual re-authorization. Correct without refresh. | Step 5 |
| 5 | Project lifecycle | **`ACTIVE · PAUSED · COMPLETED · PLANNED`.** Explicit; never inferred from inactivity; `COMPLETED` affects depth, not visibility. | Step 2 |
| 6 | Environment | **Project-local Python 3.10 `.venv`** with the existing `requirements.txt`. No `uv`, Poetry, Conda, or Docker. | Step 0 |

## 12.2 Still open

These are **inputs**, not architectural choices — they are produced by executing
the plan, not by deciding it.

| # | Open item | Produced by | Note |
|---|---|---|---|
| A | The concrete registry contents (which exact paths are evidence) | Step 2 inspection | Requires the completed workspace inspection, including triage of `~/ALX`'s ~21 entries |
| B | Confirmed Python version | Step 0 | Determined from `requirements.txt`, imports, and the installed baseline |
| C | Concrete SMTP sender and recipient addresses | Step 7 | Configuration values; mechanism is already decided |
| D | Scheduler mechanism (cron vs systemd timer) | Step 12 | Determined by the deployment environment; both are thin triggers |
| E | Whether programmatic token refresh is genuinely available | Step 5 | If verified, the service may support it; the plan does not depend on it |

Resolved decisions are recorded as ADRs during Step 14.

---

# 13. Documentation Map

- Roadmap (this file): `PLAN.md`
- Docs index: `docs/README.md`
- Architecture: `docs/architecture/` — `system-overview.md`,
  `agent-architecture.md`, `rag-architecture.md`, `linkedin-integration.md`,
  `data-flow.md`
- Retrieval (implemented): `docs/retrieval/` — README + 5 corpus-grounded
  documents
- Phases: `docs/phases/` — `phase-01-foundation.md`, `phase-02-ingestion.md`
  exist; phase-03 onward are superseded by the steps above and should be
  rewritten to match Steps 0–14
- Evaluation: `docs/evaluation/` — **empty; to be written in Steps 9 and 14**
- Operations: `docs/operations/` — **empty; to be written in Step 14**
- Decisions: `docs/decisions/ADRs/` — index exists; **ADR files to be written in
  Step 14**

---

# 14. How to Proceed

Work through Steps 0–14 in order. Step 0 is not optional and not parallelizable —
the application does not import today, so nothing downstream can be verified
until it is fixed.

At each step:

1. Read the step's **Current state** and confirm it still matches the repository.
2. Implement only the declared **Scope**.
3. Run the focused tests, then the regression tests.
4. Satisfy every **Acceptance criterion** before moving on.
5. Record any new `DECISION NEEDED` as an ADR when it is resolved.

A step is complete only when its acceptance criteria pass. Do not weaken a test
to complete a step.
