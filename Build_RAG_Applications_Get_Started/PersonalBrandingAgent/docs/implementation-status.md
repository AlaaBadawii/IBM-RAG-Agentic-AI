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
    Step 5 — Harden the LinkedIn Integration for Autonomous Use

Status:
    NOT STARTED

Overall Progress:
    Steps 0–4 COMPLETED. The environment is reproducible, the operational state
    store exists, the source registry defines exactly which directories are
    evidence about the user, synchronization is incremental, and there is now a
    context layer that turns a retrieval result into named, ranked, provenance-
    preserving sections — with evidence and positioning separated, coverage
    reported, and the absence of evidence a first-class outcome. Steps 5–14
    have not been started.

Last Completed Step:
    Step 4 — Build the Personal Branding Context & Evidence Layer

Next Step:
    Step 5 — Harden the LinkedIn Integration for Autonomous Use
```

The roadmap was rewritten and finalized after an architecture and readiness
analysis of the repository. Steps 0–3 have since been implemented, verified,
and committed; every later step remains untouched.

```text
Sources registered:  29          (8 ACTIVE · 20 COMPLETED · 1 PLANNED)
Declared roots:       9          (inspected, never ingested)
Not registered:      10          (with the evidence behind each decision)
Sources synchronized: 0          (the mechanism exists; no real source has been
                                  run through it yet — see Known Issue #7)
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
Step 5 — Harden the LinkedIn Integration for Autonomous Use
Status: NOT STARTED
```

The full specification — reason, scope, implementation approach, tests, failure
handling, and acceptance criteria — is in `PLAN.md` §8, Step 5. It is not
duplicated here.

What Step 4 leaves on the table for it:

- `app/context/` is complete and stands alone: `build_context()` consumes a
  `RetrievalResult` and returns a `PersonalBrandingContext`. Nothing calls it
  yet — Step 8 owns generation and Step 10 owns the workflow that will.
- The insufficiency signal exists but has no consumer. `EvidenceStatus` is the
  field Step 9's gates are meant to read; until then it is a value nobody acts
  on, and it is worth confirming in Step 9 that "insufficient" actually stops a
  publish rather than merely being visible.
- Freshness reads `sync_checkpoints` and therefore reports `UNKNOWN` for every
  registered source in the real workspace, because no source has ever been
  synchronized (Known Issue #7). The mechanism is correct and the answer is
  honest; the data it reads is still empty.
- The hand-written `data/` corpus is reported as untracked with no freshness at
  all. If a later step needs to know whether a curated document is stale, that
  information does not exist yet — Issue #2 is still the open question behind
  it.

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
| **Notifications use SMTP** | Provider-agnostic interface, configured for Gmail; stdlib preferred; fake transport in tests | `PLAN.md` Step 7 |
| **Infrastructure stays minimal** | LangGraph, MCP, multi-agent, queues, Redis, PostgreSQL, microservices, Kubernetes, and distributed workers are deferred with reasons | `PLAN.md` §7 |

---

## Next Step

### Step 5 — Harden the LinkedIn Integration for Autonomous Use

The next implementation task is defined in `PLAN.md` §8, Step 5.

Publishing is already proven against the real API; Step 5 turns an interactive
script into a service an unattended workflow can call, and gives credentials an
explicit lifecycle.

Constraints carried in from Steps 0–4:

- **`Auth_handling/` carries uncommitted working-tree changes that belong to
  this step.** `test_credentials.py` and `test_post.py` already resolve the
  token file relative to `__file__`; `linkedin_oauth_setup.py` — the script that
  *creates* the token — still uses the literal relative path, so it writes the
  token where the two readers will never look. They were deliberately left
  untouched through Steps 0–4 and must be reconciled here. See Known Issue #3.
- **The `app/` integration layer is a wrapper, not a rewrite.** The OAuth flow,
  the endpoint, the payload and the person-URN resolution are proven and are
  retained; `app/integrations/linkedin/` wraps them behind
  `publish_to_linkedin(post_text)`.
- **Automatic token refresh must not be assumed.** The saved token has no
  `refresh_token`, and `offline_access` alone is not evidence that programmatic
  refresh works. The service must be correct without it.
- **The integration never records success on its own authority.** Persistence —
  the write-ahead intent, the publication record — belongs to Step 6. Step 5
  returns a structured result and stores nothing.
- **Retrieval and context are not consulted by this step.** Step 4 produces a
  context object; Step 5 publishes text it is handed, and the two do not meet
  until Step 8 generates from one the other assembled.
- **No credentials are to be committed, and nothing is to be published as part
  of implementing this step.** The existing verification is a pre-existing
  baseline, not something Step 5 needs to repeat.
- **Known Issue #5 (the LLM key does not match the configured provider) is not a
  Step 5 blocker** — nothing in the LinkedIn integration path uses an LLM. It
  must be corrected before Step 8.


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
