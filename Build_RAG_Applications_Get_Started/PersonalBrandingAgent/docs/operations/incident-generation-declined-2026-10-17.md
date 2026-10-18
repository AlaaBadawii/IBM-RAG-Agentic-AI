# Incident Report — `generation_declined` on run `branding-20261017T210022Z-0d6c8abf`

**Scope:** investigation only. No application code, prompt, configuration, database,
persistent state, credential, or schedule was modified. No live model was invoked, no
external API was called, and nothing was published.

**Method:** read-only inspection of `logs/app.log`, `logs/branding-cron.log`,
`state_db/operational_state.db` (opened `mode=ro&immutable=1`),
`chroma_db/chroma.sqlite3` (opened `mode=ro&immutable=1`), `data/`, `docs/`, and the
application source. All SQLite access was read-only and bounded.

**Evidence that could not be retrieved (safely or at all)** — see §3 and §6:
1. The exact body of the incident email is **not persisted**: the `notifications` table
   has no `body` column (`notification_id, failure_id, run_id, recipient, subject,
   transport, smtp_config, delivery_state, error_message, created_at, attempted_at,
   delivered_at`). The body below is *reconstructed* from the template at
   `app/notify/messages.py:228` (`build_no_publish_message`). It is a faithful
   composition but is not a stored record.
2. No retrieval scores, ranks, or per-stratum traces were persisted for the incident run.
   Only the frozen chunk identifiers in the opportunity snapshot survive. Re-running the
   retrieval or an embedding evaluation was out of scope and forbidden.
3. `GEMINI_MODEL_ID` in `.env` was not read (secret-adjacent). The model actually used is
   taken from log lines, not from configuration.
4. The recipient address is redacted in this report.

---

## 1. Executive diagnosis

The run did **not** fail in publishing, verification, credentials, scheduling, or
synchronization. It stopped because **the writer model declined to produce a post** from
the evidence it was handed, and the evidence it was handed was the wrong part of the
source documents.

The stopping point is `app/agent/agent.py:381` — when `generated.declined or
generated.post is None`, the loop returns `NoPublishReason.GENERATION_DECLINED`
(`app/agent/enums.py:78`). The run-level reason recorded is exactly that string.

The evidence handed to the writer for the publishing candidate (`opp_4cf21f3a5c7d`,
topic `stories_lessons`) was **three "metadata tail" chunks** — each the final
`## Evidence` / `## Content Potential` / `Story strength` block of a story file, not the
story. The writer was therefore asked to write a grounded post whose narrative
(Context, Problem, What I Did, Result) it had never been given. It produced a draft, the
verifier flagged two unsupported claims, one revision was attempted, and the second
generation call declined.

This is a **content-selection defect that has been frozen into stored state**, not a
transient failure. It recurs on every run that claims the same fingerprint because the
weak snapshot is written once (`app/opportunities/backlog.py`) and never replaced.

**Primary root cause (high confidence):** stratified retrieval admitted and persisted the
metadata-tail chunk of each story as the opportunity's evidence, and that frozen snapshot
is what generation is now permanently asked to write from.
**Secondary cause (high confidence):** the history-derived repetition constraint biases
the model away from the topics that *do* have good underlying material (§7–§8).
**Contributing defect (confirmed):** the reasoner intermittently returns a malformed topic
label (`unusable_answer`), aborting the opportunity before generation even runs (§7).

---

## 2. Incident timeline and actual stopping point

Run row (`workflow_runs`):

| field | value |
|---|---|
| `run_id` | `branding-20261017T210022Z-0d6c8abf` |
| `workflow` | `branding` |
| `started_at` | `2026-10-17T21:00:22.372353+00:00` |
| `finished_at` | `2026-10-17T21:00:43.248185+00:00` |
| `outcome` | `DO_NOT_PUBLISH` |
| `failed_phase` | *(none)* |
| `no_publish_reason` | `generation_declined` |

Wall-clock duration ≈ 21 s. `failed_phase` is empty because nothing *failed* in the
workflow sense; the run reached a normal, if disappointing, terminal state.

`logs/app.log` trace (condensed; the run's phase order is
context → decide → generate/verify/revision → publish → notify):

- `21:00:32.934` — `prepared 6 persisted opportunitie(s), 14 in backlog`.
- `21:00:35.066` — run prepared, two opportunities claimed.
- `21:00:41.967` — `opportunity opp_4cf21f3a5c7d deferred (generation_declined)`.
- `21:00:43.235` — `opportunity opp_507666864e7a deferred (no_value)`.
- `21:00:43` — run terminates `DO_NOT_PUBLISH`, `no_publish_reason=generation_declined`;
  notification `notif_c95f00cf292c` composed and `sent`.

Stopping point, verbatim in structure:

```python
# app/agent/agent.py:381
if generated.declined or generated.post is None:
    return self._do_not_publish(
        NoPublishReason.GENERATION_DECLINED, ...)
```

The run's two claimed opportunities and their terminal reasons:

| opportunity | topic | terminal reason | disposition |
|---|---|---|---|
| `opp_4cf21f3a5c7d` | `stories_lessons` | `generation_declined` | deferred (attempts 1 → 2) |
| `opp_507666864e7a` | `evidence` | `no_value` | deferred (attempts 2 → 3) |

### The email that was actually sent (reconstructed)

Because the body is not stored, it is reconstructed from
`app/notify/messages.py:228-274`. Subject is the constant `"Branding Agent"`
(`app/notify/messages.py:41`). Recipient redacted.

```
PersonalBrandingAgent — no post published

No post was published for this run.

Reason:                           generation_declined

--- Backlog ---

Opportunities considered:         14
Opportunities tried:              0
Still queued:                     14

Tried but unpublished:
- <deferred entry: stories_lessons …>
- <deferred entry: evidence …>

Outcome:                          DO_NOT_PUBLISH
Run:                              branding-20261017T210022Z-0d6c8abf
Notified:                         <compose time>

No action is required from you. This is a normal outcome, and the next scheduled
run will evaluate new opportunities.
```

**Important caveat about the email:** the run-level `no_publish_reason` is the *first*
quiet reason only (`quiet_reason = quiet_reason or outcome[1]` in the workflow). The
single "Reason: generation_declined" therefore **under-represents** a run that actually
had two different terminal outcomes (`generation_declined` **and** `no_value`). A reader
of the email cannot see the `no_value` outcome at all except by reading "Tried but
unpublished". This is a reporting-fidelity gap, not the cause of the incident.

---

## 3. Explanation of `generation_declined`

`GENERATION_DECLINED` is defined at `app/agent/enums.py:78`. In the entire codebase it is
set in exactly one place: `app/agent/agent.py:381-388`, gated on
`generated.declined or generated.post is None`. It means, precisely:

> The reasoner **did** choose to publish this opportunity, and the writer model was called,
> and the writer either set `"declined": true` or returned no post.

It does **not** mean: retrieval failed, the reasoner declined, verification refused a
final draft, a duplicate gate refused, or publishing failed. Each of those has a distinct
terminal reason (`no_value`, `gate_rejected`, the duplicate refusal, and the publishing
outcomes respectively).

The decline is offered to the model as a first-class, correct answer by design, in two
places:

- Reasoner system prompt (`app/agent/prompt.py:100-101`): *"Say less rather than more.
  Declining is a normal, correct answer, and publishing something thin is worse than
  publishing nothing."*
- Writer system prompt (`app/generation/prompt.py:104-105`): *"Say less rather than more.
  If the evidence does not support a post worth publishing, decline."* and the output
  contract at `app/generation/prompt.py:111-112`.

So the vocabulary of `generation_declined` is: **the model, judged against the material it
was given, decided there was not enough to say.** The investigation's job is to establish
*what material it was given* and *why that material was insufficient* — which is §4–§6.

---

## 4. Complete accounting of all 14 opportunities

Backlog composition (`content_opportunities`): 24 rows total — **9 `published`,
14 `queued`, 1 `requires_review`**. The 14 queued opportunities, with their current
`last_decision`, `attempts`, numeric `evidence_strength`, and full recorded
`last_error`, are below. This is the complete set the pipeline is rotating through.

| # | opportunity | topic | attempts | strength | last_error (verbatim, abridged whitespace) |
|---|---|---|---|---|---|
| 1 | `opp_507666864e7a` | `evidence` | 3 | 6 | "The only available opportunity is a general certificate program overview that lacks substantive technical implementation details, and certificates have also been recently covered by the audience." |
| 2 | `opp_98f8f1b02cc8` | `in_progress_courses` | 2 | 6 | "The only available opportunity is an in-progress course with minimal detail and no concrete practical lab or project evidence provided to form a substantive professional post." |
| 3 | `opp_045fe2e85214` | `stories_lessons` | 2 | 6 | "The evidence does not provide enough specific details about the debugging story or context regarding the CI failures to construct a verified post meeting the rules." |
| 4 | `opp_c70a837328b8` | `audit` | 2 | 6 | "The only available opportunity is an internal audit process document regarding story evidence verification, which contains no technical lessons, projects, or learning achievements suitable for a LinkedIn post." |
| 5 | `opp_494657badb57` | `in_progress_courses` | 2 | 6 | "The only available opportunity is in_progress_courses, and in_progress_courses has already been recently covered by the audience according to the ALREADY PUBLISHED history. Publishing it again would be repetitive." |
| 6 | `opp_97441524ee25` | `evidence` | 2 | 6 | "There are no actionable opportunities or specific project/learning evidence items available in the input to construct a substantive LinkedIn post." |
| 7 | `opp_1e96921679bf` | `in_progress_courses` | 2 | 6 | "The only available opportunity is an in-progress course at 24% completion with no concrete technical labs, projects, or lessons yet. This is too thin to make a substantive post." |
| 8 | `opp_582d6508281e` | `audit` | 2 | 6 | "The only available opportunity is an audit about missing certificate evidence, which is an internal knowledge base maintenance issue rather than a publishable software engineering topic." |
| 9 | `opp_6193e517ff7c` | `evidence` | 2 | 6 | "claim 4: the claim asserts something the supplied evidence does not support, and the draft attributes it to nothing" |
| 10 | `opp_c963643f1abc` | `evidence` | 2 | 2 | `branding reasoning failed … (unusable_answer)`: chose topic `'evidence: 2 item(s), evidence states: IN_PROGRESS'`, not one of `['evidence']` |
| 11 | `opp_0d4e16489052` | `in_progress_courses` | 2 | 6 | "The evidence only lists an in-progress learning track without enough specific details, outcomes, or reflections to form a meaningful professional post." |
| 12 | `opp_0cd2e117277f` | `stories_lessons` | 2 | 6 | "The topic and angle violate the constraint against repeating stories_lessons topics that have already been published or overlap with restricted angles." |
| 13 | `opp_650c0cd97bec` | `evidence` | 2 | 0 | `branding reasoning failed … (unusable_answer)`: chose topic `'evidence: 3 item(s), evidence states: VERIFIED'`, not one of `['evidence']` |
| 14 | `opp_4cf21f3a5c7d` | `stories_lessons` | 2 | 6 | "The evidence lists paths, commit titles, and content potential without detailing a concrete debugging story or the specific lessons learned, making it insufficient to write a substantive post without unsupported claims." |

Observations that matter for the diagnosis:

- **Every one of the 14 is `queued`/deferred.** Nothing is in a "tried and dropped"
  state; the deferral mechanism increments `attempts` and re-queues (§8), so these are
  perpetually re-selected.
- **The topic distribution is skewed toward low-substance categories**: `evidence` ×5,
  `in_progress_courses` ×5, `stories_lessons` ×5, `audit` ×2, `in_progress_projects` ×2.
  The high-value `completed_projects` / `in_progress_projects` opportunities have *all*
  been published already and are gone from the queue.
- **The recorded reasons are overwhelmingly "thin/weak/repetitive evidence"** — rows 1–9
  and 11. Row 12 is the repetition constraint firing. Rows 10 and 13 are a separate
  reasoning-label defect.
- Row 14 (`opp_4cf21f3a5c7d`) is the incident's primary candidate, and its own
  `last_error` is the model correctly describing exactly the defect investigated here:
  *"lists paths, commit titles, and content potential without detailing a concrete
  debugging story."* The model is not wrong; the evidence really is only the tail.

The one `requires_review` row, `opp_0548fbd364db` (`completed_projects`), is unrelated to
this incident: its `publication_id` is `pub_d8f019ed0c71`, the 2026-10-05 publish that
**failed** because *"the LinkedIn credential expired on 2026-10-02…"*. It is parked for a
human by the ambiguity rule (§9), and correctly so.

---

## 5. Root-cause analysis with confidence levels

### RC-1 — Wrong chunk persisted as opportunity evidence (CONFIRMED, high confidence)

The evidence snapshot stored on the incident's primary opportunity is three metadata-tail
chunks. Read directly from `content_opportunities.evidence` for
`opp_4cf21f3a5c7d`:

| source | stored chunk id |
|---|---|
| `stories_lessons/ci_failures_are_environment_not_code.md` | `751e…:2` |
| `stories_lessons/quizey_exam_versioning.md` | `1b50…:2` |
| `stories_lessons/test_every_ai_step_with_a_fake_llm.md` | `5f42…:2` |

The `:2` suffix is the chunk index produced by `app/ingestion/chunker.py`
(`chunk_id = <content_hash>:<index>`). The corpus chunker splits on
`CHUNK_SIZE=1000` with `CHUNK_OVERLAP=200` (`app/config.py:99-100`). Each story file is
short enough (67–72 lines) to split into two or three chunks; index `:2` is the **tail**.
Confirmed by decoding `chroma_db/chroma.sqlite3`, the `:2` chunk for
`ci_failures_are_environment_not_code.md` (embedding id 280) is literally:

```
## Evidence
- `/home/alaabadawii/DevOps/jenkins-practice/Jenkinsfile`
- …
## Content Potential
- Debugging story ("when CI is red, check the environment first")
- …
Story strength:
STRONG
Reason:
Concrete event, first-hand action over multiple commits, …
```

The narrative that a post would actually need — `## Context`, `## Problem`, `## What I Did`,
`## Decision / Insight`, `## Result`, `## Engineering Lesson` — lives in chunks `:0`/`:1`
of the same file (`data/stories_lessons/ci_failures_are_environment_not_code.md:7-49`).
The writer never received it.

**Why the tail was selected.** Stratified retrieval admits, per category, up to
`chunks_per_document` chunks from each of the top three documents
(`app/retrieval/strata.py:149-153`, `_documents_of` at `:409-420`). The per-category
candidate pool is the full fused list, `_POOL = 2 * HYBRID_CANDIDATES = 20`
(`app/retrieval/strata.py:117`, `_category_pool` at `:363-373`). That pool is ranked by
hybrid (vector+BM25 RRF) similarity to the production query
`"recent professional work, projects, and achievements worth sharing"`
(`app/workflows/branding.py:123`). The tail chunk is, by construction, the chunk that
*contains the words* "achievements / content potential / story strength / evidence" — the
lexical overlap with that query is highest in the tail. So the tail ranks first for the
document, and `_by_document` + `chunks[:chunks_per_document]` (which keeps the document's
strongest chunks, `app/retrieval/strata.py:376-387`) can legitimately return only the
tail. The module's own docstring (`app/retrieval/strata.py:46-55`) describes the
document-then-chunk policy; what it does not guard against is a document whose
*strongest chunk is its least narrative* one.

> Note the frozen snapshot is three chunks even though the stratum allows two per
> document: `opp_4cf21f3a5c7d` was created 2026-10-02T13:00:52Z and its `store`-side
> fingerprint (`ed39e8e690…`) has matched on every run since, so the original snapshot is
> never rebuilt (`app/opportunities/backlog.py`, idempotent `persist_discoveries`).

### RC-2 — The weak snapshot is frozen and re-served forever (CONFIRMED, high confidence)

`persist_discoveries` writes an opportunity once, keyed by fingerprint, and does not
overwrite it. Because the fingerprint of a given discovery is stable across runs, each
subsequent run rebuilds the context from *the stored evidence snapshot*, not from a fresh
retrieval. Confirmed by the fact that the incident run "prepared 6 persisted
opportunitie(s)" — 6 discoveries whose fingerprints already existed — and therefore
generated from pre-existing snapshots. The consequence is that the tail-chunk defect
is not a periodic accident; it is the permanent nature of these opportunities. Fixing
retrieval alone would not repair the already-stored rows.

### RC-3 — Writer declines because the tail cannot ground a narrative (CONFIRMED mechanism, high confidence)

With only the tail, the writer faces a hard contradiction between two absolute rules: it
must not invent anything the evidence does not support
(`app/generation/prompt.py:92-94`), and it should decline rather than pad
(`:104-105`). The tail actively *advertises* content ("Debugging story …", "Short lesson
on `python -m pytest` vs `pytest`") that it does not contain. A reasonable model drafts
the advertised story, which the verifier then finds unsupported (it flags paraphrase of
narrative it never received), and after the bounded revision attempt
(`MAX_REVISION_ATTEMPTS = 2`, `app/verification/revision.py:27`; loop at
`app/agent/agent.py:366-409`) the safe terminal answer is to decline. That is exactly the
recorded path.

### RC-4 — Repetition constraint biases away from good material (CONFIRMED, high confidence)

`publishing_constraints` (`app/agent/models.py:490-511`) derives `recent_topics`,
`recent_projects`, and `recent_angles` from `HistoryDigest` and feeds them to the writer
as an "ALREADY PUBLISHED / avoid repeating" block (`app/generation/prompt.py:257-263`),
and to the reasoner as rule 4 (`app/agent/prompt.py:97-99`, block at
`app/agent/prompt.py:308`). Published topic counts among the 9 successes are dominated by
the *good* categories: `completed_projects` ×4, `in_progress_projects` ×3,
`stories_lessons` ×3, plus certificates/courses. Because the digest is **not
time-windowed** (`DEFAULT_DIGEST_LIMIT=10`, most recent publications), and because topic
is coarse, the constraint tells the model that the very categories with the strongest
underlying stories are "already covered". Row 12 (`opp_0cd2e117277f`) is this constraint
firing verbatim. Rows 2/5/7/11 (`in_progress_courses`) and 12 are, directly or indirectly,
repetition-driven declines.

### HD-1 — Model downgrade (HYPOTHESIS, medium confidence)

The documented, deliberately pinned model is `gemini-3.6-flash`
(`app/config.py:75-83`, with an explicit rationale naming it the stable pin). Every Gemini
call in `logs/app.log` uses **`gemini-3.5-flash-lite`** (258 occurrences; zero occurrences
of `gemini-3.6-flash`), so `.env` overrides `GEMINI_MODEL_ID`. A "flash-lite" tier is
plausibly more decline-prone and less able to reconstruct narrative from sparse evidence.
This is a *plausible contributor*, not established: there is no A/B evidence in the logs,
and the tail-chunk defect alone fully explains the decline. **Do not treat as proven.**

### HD-2 — Retrieval configuration drift (HYPOTHESIS, low confidence)

`HYBRID_CANDIDATES`, `TOP_K`, and `CHUNK_SIZE` are env-overridable. `.env` was not read;
the observed behavior is consistent with the defaults. No log evidence indicates drift,
but it cannot be excluded from configuration alone.

### HD-3 — Corpus cadence / stale backlog (HYPOTHESIS, low–medium confidence)

The last successful publication before the incident was 2026-10-15
(`pub_1e99a03e668c`); the 2026-10-16 run `WORKFLOW_FAILED` on the reasoning defect
(§7). The queue is now dominated by material that was always going to be weak
(`evidence`, `in_progress_courses`, `audit`). Whether the *corpus* has genuinely exhausted
its strong stories, or whether selection merely stopped surfacing them, is not settled by
the persisted data (§8).

---

## 6. Retrieval and evidence-quality audit

**The source documents are not the problem.** `data/stories_lessons/*.md` are
well-formed, honest stories with the full Context→Result arc, and the repo's own audit
(`data/audit/stories_evidence_audit.md`) grades the majority STRONG or SUPPORTED, with one
RED FLAG (`committed_ssh_key_to_git.md`, which must be corrected before use) and one WEAK
(`kubernetes_first_step_typos.md`). The defect is entirely in *which slice of a good
document* became the persisted evidence.

**Chain of custody, confirmed:**

1. Ingestion chunks at `CHUNK_SIZE=1000` / `CHUNK_OVERLAP=200`
   (`app/config.py:99-100`), id = `hash:index` (`app/ingestion/chunker.py`).
2. Stratified retrieval (`app/retrieval/strata.py:209`) runs a hybrid query per category
   with scope `for_category` (`app/retrieval/scope.py`), pool `_POOL=20`, and admits up to
   `documents=3`, `chunks_per_document=2` per tier (`app/retrieval/strata.py:149-153`).
3. `build_context` (`app/context/builder.py:66`) groups by `category` metadata into
   sections; classification is metadata-only by design (`_classify` at `:147-180`).
4. The reasoner's topic vocabulary is one entry per non-empty evidence section
   (`app/agent/prompt.py:137-149`), so `stories_lessons` becomes a topic.
5. The reasoner selects **one** opportunity's evidence; generation is handed the selected
   items only (`selected_evidence`, `app/generation/prompt.py:121-159`).
6. `persist_discoveries` freezes the section's items as the opportunity's `evidence`
   (idempotent by fingerprint).

**The quality failure is at step 2→6:** the *tail* is the chunk with the highest lexical
overlap with the production query, so within a story it wins the "strongest chunk" slot,
and the snapshot records it. Confirmed three ways: (a) the stored chunk ids all end
`:2`; (b) decoding the Chroma document for `751e…:2` returns the `## Evidence` /
`## Content Potential` / `Story strength` block, not the narrative; (c) the same pattern
recurs on a *second* `stories_lessons` opportunity, `opp_045fe2e85214`, whose snapshot is
also three `:2` tails (`ci_failures…:2`, `kubernetes_first_step_typos…:2`,
`quizey_exam_versioning…:2`).

**The `evidence` topic is independently weak.** `opp_507666864e7a`'s snapshot is a single
`:2` tail of `evidence/professional/professional.md`, and the reasoner's recorded reason
is *"a general certificate program overview … recently covered"*. The `evidence/` corpus
is generic credentials/experience claims with declared-but-unproven states, which the
system correctly refuses to dress up as achievement — consistent with the `no_value`
outcome in the same run. This is a genuine content limitation, not a retrieval bug.

**Retrieval-quality evidence that could not be obtained:** no rank/score traces exist for
the incident. The conclusion above is drawn from persisted identifiers plus the decoded
chunk text, which is sufficient to establish *what* was selected, though not *by how much*
it outranked the narrative chunk.

---

## 7. Prompt, generation, verification, and scoring audit

**Prompt versions in play:** reasoner system prompt `branding-agent-v3` (v3 landed in
commit `46e75c2 "PersonalBrandingAgent: learning-value reasoning (v3) and coverage-aware
retrieval"`); writer system prompt `grounded-post-v2`. Both are constant system messages
by design, so a caller's context cannot push the rules out of the prompt
(`app/agent/prompt.py:129-132`, `app/generation/prompt.py:116-118`).

**Reasoner (`app/agent/prompt.py`):** rules 1–7 are well-specified and honest. Rule 5
(:100-101) and rule 7 (:112-118) explicitly license declining thin material but also warn
against declining substantive learning. The failure here is not the prompt wording; it is
that the model saw only tails and (correctly) judged them thin. Row 3's recorded reason —
*"does not provide enough specific details about the debugging story"* — is the model being
*right*.

**Reasoning label defect (`unusable_answer`, CONFIRMED):** on two opportunities the
reasoner returned a topic string that is not a listed opportunity:
`'evidence: 2 item(s), evidence states: IN_PROGRESS'` and
`'evidence: 3 item(s), evidence states: VERIFIED'` instead of `'evidence'`. Both aborted
with `branding reasoning failed … (unusable_answer)`. This is a structured-output
adherence problem in the reasoner (the model concatenated the section name with its
coverage summary). It contributes to the queue stalling on `evidence` rows but is
independent of RC-1.

**Writer (`app/generation/prompt.py`):** rule 1 (no invention, :92-94), rule 4 (cite only
listed labels, :102-103), rule 5 (decline rather than pad, :104-105). Given a tail that
advertises a narrative it does not contain, the writer's two obligations (be grounded; be
substantive) are mutually unsatisfiable, and rule 5 selects decline. Confirmed by the
agent trace: a draft *was* produced (549 chars, one citation), i.e. the writer did try
before declining.

**Verifier (`app/verification/`):** the gate returned `REVISION_REQUIRED` with 6 extracted
claims and 2 unsupported findings (one about the "first instinct when CI goes red", one
about the `python -m pytest` vs `pytest` moral). It is behaving correctly: those claims
are genuinely absent from the tail. The support judge is advisory and strict ("plausible is
not supported"), which, combined with thin evidence, makes a second rejection likely.
`MAX_REVISION_ATTEMPTS = 2` (`app/verification/revision.py:27`) bounds the loop; the second
generation call declined before a second verdict.

**Scoring / `evidence_strength`:** the column is `6` for 12 of 14 queued rows, `2` for
`opp_c963643f1abc`, `0` for `opp_650c0cd97bec`. The two non-6 values correspond exactly
to the two `unusable_answer` failures, so the field appears to degrade on reasoning
failure rather than reflecting document quality. It is **not** a reliable content-quality
signal here.

---

## 8. State and backlog analysis

**Claim ordering and anti-starvation.** `store.claim_opportunities` orders by
`attempts ASC, created_at ASC, evidence_strength ASC, fingerprint ASC`, and a deferral
increments `attempts`. This is a deliberate rotation: a deferred opportunity moves to the
back so others get a turn. The observed effect is that the *entire* queue is now `attempts
= 2` (or 3), so ordering has flattened and the same weak set is re-claimed each run,
early-creation-first. The rotation prevents starvation but also prevents *retirement* —
a permanently-unpublishable opportunity is never dropped, so it re-consumes the
`MAX_PUBLISHES_PER_RUN = 2` budget (`app/publishing/service.py:72`) indefinitely.

**The repetition loop.** Each run: rebuild contexts from frozen snapshots → reasoner
declines most (thin/repetitive) → the one or two `stories_lessons` it does attempt hit the
tail-chunk wall → `generation_declined` → defer (attempts++). `persist_discoveries` yields
the same 6 persisted discoveries and 14 backlog rows every run
(`logs/app.log`: "prepared 6 persisted opportunitie(s), 14 in backlog", repeated across
2026-10-14/15/16/17). Backlog size has been ~14–16 since 2026-10-14; it is not draining.

**Corpus exhaustion vs. selection failure.** Both are partly true. The strong
`completed_projects`/`in_progress_projects` opportunities are all published, so the queue
genuinely holds mostly `evidence`/`in_progress_courses`/`audit` material much of which is
legitimately postless. But the `stories_lessons` rows *do* have strong stories behind them
(the tails prove the underlying docs are STRONG/MEDIUM) — those are a selection failure,
not exhaustion. `opp_4cf21f3a5c7d` and `opp_045fe2e85214` are recoverable; the
`in_progress_courses` and `audit` rows are not.

**Trigger changes relevant to the window.** The 2026-10-16 run
(`branding-20261016T210017Z-3395106a`) ended `WORKFLOW_FAILED` at phase `decide` — the
same `unusable_answer` label defect (row 13). So the two runs immediately preceding the
incident show (a) a hard failure from the reasoning defect and (b) a quiet decline from the
tail-chunk defect. There is no evidence of a scheduling, sync, or credential change in the
window: `sync_checkpoints` show the last sync succeeded
(`sync-20261016T231038Z-c4bde7bf`), the only `FAILED` checkpoints are dated 2026-09-23, and
`source_lifecycle` is empty. Synchronization is **not** implicated.

**No source/code change in the window.** The git working tree for this project is clean;
the most recent `PersonalBrandingAgent` commit is `46e75c2` (v3 reasoning + coverage-aware
retrieval). The incident is behavioral/stateful, not a fresh regression.

---

## 9. Separate publishing-health assessment

**Publishing is healthy and is not implicated in this incident.** The run reached
`selected = 0`; nothing was ever handed to the publisher, so no publish gate could have
been involved.

Audited and found sound:

- **Intent-before-request.** `app/publishing/service.py` records a `publish_intents` row
  before the LinkedIn request and never retries on ambiguity; an ambiguous result becomes
  `unknown_requires_review` rather than a double-post. This is why
  `opp_0548fbd364db` is parked as `requires_review` with `pub_d8f019ed0c71`, the only
  failure in the log.
- **Duplicate gates.** `app/publishing/duplicates.py` implements exact content-hash,
  near-duplicate embeddings, and topic/project/evidence overuse. Note: the near-duplicate
  embedding check is **not wired in production** — `PublishingService(store)` is
  constructed without an embedder — so only the exact-hash and overuse checks are live.
  This is a latent gap, not a cause here.
- **Run budget.** `MAX_PUBLISHES_PER_RUN = 2` (`app/publishing/service.py:72`) — not
  reached.
- **Recent publish history.** 9 `published`, 1 `failed` (`pub_d8f019ed0c71`, expired
  credential, 2026-10-05), 1 in `requires_review`. Cadence sane through 2026-10-15
  (`pub_1e99a03e668c` → `urn:li:share:7516362382730743808`); one out-of-slot publish on
  2026-10-09T16:03Z (`pub_821620cf9f85`), likely a manual run, harmless.

**Conclusion:** the publisher is exonerated. The email's "no post published" is a
programmatic consequence of an upstream content decision, and the publishing layer
correctly did nothing.

---

## 10. Best candidate opportunities and offline post simulations

These are hand-written, offline drafts. **No model was invoked** and nothing was published.
Each draft is grounded **only** in the full narrative of the underlying story file (the
`Context`/`Problem`/`What I Did`/`Result` chunks that the frozen snapshots omitted), and
each is paired with the queued opportunity whose underlying documents it recovers. They
exist to demonstrate that the source material *is* publishable when the correct evidence is
retrieved, and to inform the policy in §11.

### Candidate A — `ci_failures_are_environment_not_code` (STRONG)
Recovers: `opp_4cf21f3a5c7d`, `opp_045fe2e85214`. Grounded in
`data/stories_lessons/ci_failures_are_environment_not_code.md`.

> My pipeline was red while `pytest` passed locally. The app was a trivial Flask service,
> so the bug was almost certainly not the code — and it wasn't.
>
> `tests/test_app.py` does `from app import app`, which needs the repo root importable. In
> CI, `pytest` was being invoked in a way that didn't put the working directory on
> `sys.path`. The fix was one line of *invocation*: use `python -m pytest` (which sets
> `sys.path[0]` to the cwd) and add `PYTHONPATH=.` to the Jenkins step.
>
> Same test logic. Same code. Green pipeline.
>
> Lesson I keep relearning: when CI fails but the tests pass locally, check cwd, PATH, and
> PYTHONPATH before suspecting the app. The environment is part of the system.

### Candidate B — `never_trust_llm_arithmetic` (STRONG)
Recovers the `stories_lessons` material in `opp_0cd2e117277f`. Grounded in
`data/stories_lessons/never_trust_llm_arithmetic.md`.

> I let a grading LLM compute a weighted average. It returned `2.75` for scores `4, 2, 3, 4`
> at `0.25` each. The correct answer is `3.25`. It was confidently wrong.
>
> I caught it because I did the arithmetic by hand. Then I changed the rule: the Judge's
> weighted average and the Critic's agreement are **never** taken verbatim from the model —
> they're recomputed in plain Python where they can be tested.
>
> LLMs reason well and do arithmetic unreliably. Any number your system depends on should
> be computed in code you can unit-test, not extracted from a generation.

### Candidate C — `quizey_idempotency` (STRONG)
Grounds the `stories_lessons`/`in_progress_projects` material. Grounded in
`data/stories_lessons/quizey_idempotency.md`.

> Students submit an exam; a double-click or a network retry must not grade it twice. I
> wanted "exactly once" to be a property of the system, not a hope.
>
> Two layers: an `@idempotent` decorator keyed by an `Idempotency-Key` header with a unique
> `(user, key, endpoint)` constraint, plus a status check in the attempt service. Completed
> requests are replayed; in-flight ones return `409`. Then I wrote a harness that fires 10
> concurrent `/submit` calls and asserts exactly one graded attempt.
>
> The lesson: exactly-once is designed and proven, not assumed. A unique constraint stops
> the second writer; the status check stops logical re-processing. You need both.

### Candidate D — `quizey_exam_versioning` (STRONG)
Recovers `opp_4cf21f3a5c7d`/`opp_045fe2e85214` material. Grounded in
`data/stories_lessons/quizey_exam_versioning.md`.

> "Can I just edit a published exam?" sounds like a small feature. It collides head-on with
> in-flight attempts and grading fairness.
>
> Instead of mutating a live exam, editing a published exam now auto-creates a new version
> via `create_exam_version()` — copy-on-write. Published versions are immutable; a new
> version starts as a draft and links to its family through `root_exam_id`. Attempts
> reference the version they ran against.
>
> When a "simple edit" meets in-flight users, the product's integrity priority should
> drive the data model. Immutable + versioned beat mutable + shared.

### Candidate E — `test_every_ai_step_with_a_fake_llm` (SUPPORTED/MEDIUM)
Recovers `opp_4cf21f3a5c7d` material. Grounded in
`data/stories_lessons/test_every_ai_step_with_a_fake_llm.md`.

> Every AI step in my grader had to be testable without burning API calls or fighting
> non-determinism.
>
> I routed all model access through one `core/llm.py` with a `(prompt, schema) -> dict`
> interface, then injected a fake LLM in tests. The pipeline logic is exercised with zero
> API calls; the real model is a swappable detail behind a stable seam.
>
> If you can't test an AI step with a fake, your step logic is probably tangled with the
> model call. Split them and the whole pipeline becomes cheap and deterministic to verify.

**Framing constraints carried from `data/audit/stories_evidence_audit.md` (must be
honored in any publication):** Quizey work is **designed, not shipped** (uncommitted tree);
`test_every_ai_step` is a *technique*, not a production system; `committed_ssh_key_to_git`
must be corrected or withheld (its headline claim is contradicted by git history);
`kubernetes_first_step_typos` is a learning start, not a headline.

**Simulation verdict:** A–D are publishable today from the existing corpus, *if* the
narrative chunks are retrieved. E is publishable as a short technique note.

---

## 11. Recommended editorial decision policy

Proposals only; no implementation.

1. **Select evidence by role, not by lexical rank.** A story's narrative chunks
   (Context/Problem/What I Did/Decision/Result/Lesson) are the publishable evidence; the
   `## Evidence` / `## Content Potential` / `## Story strength` tail is *catalog metadata*,
   never the basis of a post. The selection layer should prefer narrative-bearing chunks
   for a document and deprioritize the metadata tail (e.g. by chunk position/structure or
   by excluding `## Evidence`/`## Content Potential` sections from the candidate set for
   generation).
2. **Never freeze a snapshot you cannot write from.** If the persisted evidence for an
   opportunity yields `generation_declined` (or verifier `GATE_REJECTED`) on first use, the
   stored snapshot should be *rebuilt from a fresh retrieval* on the next claim rather than
   re-served unchanged. A snapshot that has failed to produce a post N times is evidence
   the snapshot is bad, not that the model is.
3. **Make the repetition constraint time-windowed and angle-aware, not topic-count
   based.** Telling the writer "stories_lessons has been covered" blocks the *category* even
   when the *angle* is new (CI debugging vs. LLM arithmetic vs. Quizey idempotency are
   different stories). Constrain on recent angles/projects with a recency window, not on a
   cumulative topic tally.
4. **Introduce retirement, not just rotation.** An opportunity that exhausts its attempt
   budget across distinct runs without ever passing generation should be moved to a
   terminal `exhausted`/`requires_review` state so it stops consuming the publish budget.
   Keep deferral for genuinely recoverable items (after snapshot rebuild).
5. **Classify topics by publishability up front.** `audit` and most `in_progress_courses`
   evidence are internal/insubstantial by nature; they should not become publishing
   candidates at all (they may still exist as context). Reserve LinkedIn candidates for
   `completed_projects`, `in_progress_projects`, and narrative-backed `stories_lessons`.
6. **Treat `in_progress_courses` as learning-milestone-only.** Per
   `app/agent/prompt.py:102-118`, learning material *can* be publishable — but only when
   described honestly as learning. A course at 24% completion with no labs is not; a
   completed course with concrete artifacts is.
7. **Report every terminal outcome, not just the first quiet reason.** The email should
   enumerate each claimed opportunity's outcome (e.g. `opp_4cf21f3a5c7d:
   generation_declined`, `opp_507666864e7a: no_value`) so a reader can act on the run
   without opening the database.
8. **Fix the reasoning label contract.** The reasoner must return a topic name exactly as
   listed; including the coverage summary (`evidence: 3 item(s)…`) is a contract violation
   that aborts a whole opportunity. Validate-and-retry, or coerce to the matching label.

---

## 12. Prioritized remediation plan

No fixes were applied; this is the recommended order and rationale.

### P0 — Stop the bleeding (wrong evidence is frozen and re-served)
- **P0.1** Ensure generation is not asked to write from metadata-tail chunks (narrative
  selection at ingest/selection time; or strip `## Evidence`/`## Content Potential` from
  generation evidence). Addresses RC-1.
- **P0.2** Rebuild stored snapshots that have repeatedly failed generation instead of
  re-serving them forever. Addresses RC-2 and the permanent-stall behavior in §8.
- Rationale: without these two, every future run repeats the incident regardless of any
  prompt tweak.

### P1 — Remove the two confirmed amplifiers
- **P1.1** Replace the cumulative/coarse repetition constraint with a time-windowed,
  angle-aware one (RC-4; rows 2/5/7/11/12).
- **P1.2** Fix the `unusable_answer` topic-label contract in the reasoner (RC, §7; caused
  the 2026-10-16 `WORKFLOW_FAILED`).

### P2 — Improve throughput and honesty of the queue
- **P2.1** Add opportunity retirement / terminal states so exhausted weak rows stop
  consuming the publish budget (§8, policy 4).
- **P2.2** Exclude `audit` and non-substantive `in_progress_courses` from publishing
  candidacy (policy 5).
- **P2.3** Verify the `.env` `GEMINI_MODEL_ID` against the documented pin; if it is a
  "lite" tier, evaluate whether the decline rate changes with the pinned model
  (HD-1, medium confidence).

### P3 — Hardening and observability
- **P3.1** Enumerate all per-opportunity terminal outcomes in the run notification
  (policy 7).
- **P3.2** Wire the near-duplicate embedding check into production (currently inert, §9).
- **P3.3** Persist a lightweight retrieval/selection trace (chosen chunk ids + ranks) per
  run so a future incident of this class is diagnosable without decoding Chroma.
- **P3.4** Correct or withhold `committed_ssh_key_to_git.md` and fix the "24+" test-count
  in `quizey_attempt_state_machine.md` before either is ever published (per
  `data/audit/stories_evidence_audit.md`).

### Concluding diagnosis

`branding-20261017T210022Z-0d6c8abf` did **not** fail because of publishing, credentials,
sync, scheduling, or a code change. It ended `DO_NOT_PUBLISH / generation_declined` because
the writer model was handed the **metadata tail** of three otherwise-strong stories and,
correctly refusing to invent the narrative those tails advertised, declined — after a
grounded draft was raised and the verifier rejected it for the missing narrative. The
snapshot that caused this was frozen into the opportunity on 2026-10-02 and has been
re-served unchanged every run since, while a cumulative repetition constraint pushed the
model away from the categories that still contain good material and a reasoner label bug
aborted two `evidence` opportunities outright. The core fault is in **evidence selection
and snapshot lifecycle**, not in the models, the prompts' intent, or the publishing
machinery — and it will recur on schedule until the persisted evidence is corrected and
snapshots that cannot produce a post are allowed to be rebuilt or retired.
