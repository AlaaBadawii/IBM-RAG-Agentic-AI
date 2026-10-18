# Abu Prompt Improvement Lab

An offline, evidence-driven evaluation loop that lives **beside** the production
pipeline, never inside it. It exists so a proposed change to Abu Prompt (or the
verification policy, or the context builder) can be measured against a **frozen
reference set** before anyone applies it — and so that the measurement itself
can never publish, notify, or mutate operational state.

This directory and `app/improvement/` are **Stage 0 (substrate)** and **Stage 1
(frozen content-evaluation baseline)** of the approved self-improvement roadmap.
They do **not** implement autonomous prompt editing, candidate promotion,
configuration switching, or code self-modification. Generating a proposal does
not authorize applying it. Every step that would change production runs through
a human decision.

---

## The boundary (why this is safe to run)

Nothing in `app/improvement/` may:

- import the publishing service, the LinkedIn client/publisher, the
  notification service, or a production workflow entry point;
- open the authoritative operational database, or any `StateStore` that would
  migrate it;
- make an external network call, or invoke a live model;
- write to production state.

Evidence is read from an explicit, consistent **copy** of the database that the
caller supplies, opened read-only. Missing information is recorded as explicitly
*unavailable*, never as a fabricated zero. The boundary is pinned by
`tests/test_improvement_isolation.py`.

Two commands are available; neither can publish or write production state:

```text
python -m app.improvement collect  --source <db> --dest <private-dir>
python -m app.improvement evaluate [--dataset <file>] [--split <name>]
                                   [--designation baseline|candidate]
                                   [--out <dir>] [--quiet]
```

---

## `collect` — read-only evidence snapshot

```bash
python -m app.improvement collect \
    --source state_db/operational_state.db \
    --dest   ~/.local/state/abu-prompt-lab/evidence-2026-10-18
```

`collect` snapshots the named database using SQLite's **online backup API** into
a private directory (`0700`, files `0600`) and reads the copy in `mode=ro`. The
backup API is used rather than a plain file copy because a live SQLite file
copied naively can be torn.

Only explicitly allowlisted columns are exported (`EXPORT_ALLOWLIST` in
`app/improvement/evidence.py`): runs, publication outcomes, publication
evidence, content opportunities and opportunity outcomes. Draft text, tokens,
credentials and notification bodies are intentionally **absent**, so a later
schema that adds a secret-bearing column cannot leak through a `SELECT *`.

The copy's **own** `schema_version` ledger is read and validated; the collector
refuses a copy newer than `SUPPORTED_SCHEMA_VERSION` rather than misreading it.
Absent historical information stays absent — the collector does not reconstruct
prompts, model settings, drafts or verdicts that were never recorded.

---

## `evaluate` — the frozen content baseline

```bash
python -m app.improvement evaluate --designation baseline
```

This loads the frozen dataset, runs the deterministic pipeline over each case,
and writes four files into `improvement/artifacts/` (gitignored):

| File | Contents |
| --- | --- |
| `<designation>.artifact.json` | the full `EvaluationArtifact` |
| `<designation>.cases.jsonl` | one `CaseArtifact` per line |
| `<designation>.manifest.json` | reproducibility header (versions, environment) |
| *(stdout)* | a short human-readable summary |

The evaluator builds the **real** evidence context
(`app.context.builder.build_context`, handed an offline checkpoint stub so it
never opens the store), builds the **real** draft
(`GeneratedPost`), and calls the **real** gate
(`app.verification.verifier.verify`). It measures the deterministic gate, not
the generator, and **no model is called in this stage**.

Metrics are defined in [`rubric/content-rubric-v1.md`](rubric/content-rubric-v1.md).
They are kept separate and are never summed. The run has a **baseline quality
gate** (`baseline_quality_gate_passed`): if any selected candidate is
unacceptable, or a candidate is selected where the review says none should be,
or a selected candidate carries a forbidden-inference or unsupported-reference
finding, the gate is `false` and the CLI exits non-zero. The gate concerns
*evaluated-output quality only*; isolation is proven separately by
`tests/test_improvement_isolation.py`. The artifact also reports how many
findings were **detected** versus how many **reached a selected candidate**.

Use `--split development` while iterating on a candidate and `--split held_out`
(only once, at comparison time) to check it generalises. The held-out split must
**not** inform candidate revision.

---

## The dataset

`dataset/content_eval_v1.json` is the frozen reference set: **23 cases** —
16 development, 6 held-out, and **1 known-limitation probe** — across a range of
positive and negative scenarios: strong narratives, completed and in-progress
projects, thin learning, generic certificate prose, catalog-only evidence,
repetitive angles, insufficient evidence, malformed drafts, weak evidence
states, and unsupported/uncited references.

A **known-limitation probe** is a fixture whose reviewed expectation is exactly
what the current deterministic gate is known *not* to deliver (for example, a
fabricated bare count). Probes are evaluated so the weakness is *observed*, but
they are excluded from every scored metric and from the quality gate, and are
reported in `known_limitations`. See the rubric's "Known limitations" section.

Each case carries:

- a `provenance` block naming the real corpus files it is shaped by, with their
  SHA-256. On load these hashes are **recomputed and verified**; a source that
  changes forces the dataset version to be bumped, and the dataset hash (over
  the canonical case block) changes with any fixture edit.
- one or more **offered candidates**, each with a reviewed `status`
  (`preferred` / `acceptable` / `unacceptable` / `unlabeled`);
- the reviewed **expectations** — whether *any* candidate should publish, which
  outcomes are valid, and which candidates are preferred, acceptable or
  unacceptable.

Expectations are reviewed, not single-answer: a case may legitimately admit
several valid outcomes. The evaluator must not impose one right answer where
several are defensible.

---

## What the baseline does and does not establish

These are four different things, and only the first is what Stages 0/1 deliver:

1. **The deterministic, model-free fixture baseline (this change).** It measures
   how the real offline pipeline *behaves on a frozen, human-reviewed set of
   cases*: which drafts pass the deterministic gate, which are selected, and
   whether the selection matches the review. It is a property of the **gate and
   the fixtures**, not of any language model.
2. **The production workflow's behavior.** Established by the production test
   suite and the operational database, not by the Lab. The Lab neither changes
   nor re-measures it.
3. **The production LLM prompts' performance.** **Not established here.** No live
   model is called in Stages 0/1, so this baseline says **nothing** about whether
   `grounded-post-v3` (or any prompt) outperforms another. It cannot, and does
   not claim to, demonstrate that the agent has improved itself.
4. **A future baseline-vs-candidate model experiment.** Requires a *new,
   isolated* stage: a candidate provider that calls a model, a pre-registered
   hypothesis, and an accept/reject decision — all still offline and
   human-gated. When that exists, the comparison can be read against the frozen
   baseline recorded here.

What can be compared **with existing records today**: reproducibility of the
deterministic pipeline (same dataset/evaluator/rubric ⇒ identical artifact), and
the gate's behavior across fixture revisions. What **requires new isolated model
experiments**: any prompt-vs-prompt or model-vs-model claim.


---

## Where this sits in the roadmap

| Stage | Scope | Status |
| --- | --- | --- |
| 0 | Substrate: evidence collection, artifacts, manifests, isolation | **this change** |
| 1 | Frozen content-evaluation baseline + rubric | **this change** |
| 2 | Candidate *proposal* generation (still human-gated) | not started |
| 3 | Baseline-vs-candidate experiment runner | not started |
| 4 | Configuration experiments under hard bounds | not started |
| 5 | Code-level loops, last and most gated | not started |

Production stays deterministic. Any future meta-loop (including one that uses
LangGraph) lives here, offline, and never in the production path.
