# Remediation delivery — evidence pipeline and editorial reliability

Date: 2026-10-18
Incident: `docs/operations/incident-generation-declined-2026-10-17.md`
Scope: Phases 0–8 of the approved remediation plan. No publish, no live model
call, no external request, no notification, no change to production state.

## What the incident was

A run persisted an opportunity whose evidence was a story's metadata footer —
its `## Evidence` path list, `## Content Potential`, `Story strength` — instead
of the story. The fingerprint then froze that snapshot, so a rebuild never
happened and every retry re-served the same unwritable index card. The writer
declined each time, and the run reported `generation_declined`. A decorated
reasoner label (`evidence: 3 item(s), evidence states: VERIFIED`) compounded it
by being refused as an unknown topic (`unusable_answer`).

## What changed

| Phase | Change | Where |
| ----- | ------ | ----- |
| 1 | Narrative-aware evidence selection: classify chunks (narrative / mixed / catalog / unknown); a document's narrative siblings replace a footer-only pool; catalog-only items never persist | `app/context/evidence_roles.py`, `app/retrieval/strata.py`, `app/opportunities/backlog.py` |
| 2 | Snapshot versioning + repair: `EVIDENCE_SNAPSHOT_VERSION`, a fingerprint-stable in-place refresh for actionable rows, an exhausted terminal state, and a dry-run repair CLI | `app/state/schema.py` (mig 10), `app/state/store.py`, `app/opportunities/{backlog,repair}.py` |
| 3 | Time/angle-aware constraints (30-day window, anchored to the newest publication) and non-candidate sections (`audit`, unclassified, thin in-progress courses) | `app/agent/models.py`, `app/context/evidence_roles.py`, `app/generation/prompt.py` |
| 4 | Reasoner topic normalization: exact → case-insensitive → decorated-prefix, deterministic and one-shot; a genuinely unknown topic is still refused, with a diagnostic | `app/agent/{prompt,agent}.py` |
| 5 | Per-opportunity outcomes (decision, rationale, bounded evidence trace) recorded per run and surfaced in the run notification | `app/state/schema.py` (mig 11), `app/state/store.py`, `app/workflows/branding.py`, `app/notify/{messages,service}.py` |
| 6 | LinkedIn discoverability guidance in the writer contract + a non-blocking advisory check (flags weak openings, never rejects) | `app/verification/editorial.py`, `app/verification/{models,verifier}.py`, `app/generation/voice.py` |
| 7 | Publication engagement metrics and an honest age-comparable baseline, imported by hand via a safe dry-run CLI | `app/state/schema.py` (mig 12), `app/state/store.py`, `app/metrics/import_metrics.py`, `docs/operations/publication-metrics.md` |
| 8 | Full regression, an incident reproduction test, this report | `tests/test_incident_reproduction.py` |

## Cadence change — twice weekly, one post per run

Approved after the remediation review: the branding schedule moved from every
8h (up to two posts per run) to **twice weekly** (Tue + Fri 10:00), still with
**one post per run**, so the target is two posts a week. Decisions are
decoupled from publications so a declined candidate falls through to the next
one, but a run can never publish twice.

| Change | Where |
| ------ | ----- |
| `MAX_PUBLISHES_PER_RUN` 2 → 1; one publish attempt per run | `app/publishing/service.py` |
| Migration 13: drop the `≥ 2` trigger, recreate it as `≥ 1` (one publish intent per run) | `app/state/schema.py` |
| Decision budget (`MAX_DECISIONS_PER_RUN = 2`) split from the publish budget; declined candidates fall through; verified siblings released without spending their attempts; ambiguous outcome ends the run | `app/workflows/branding.py`, `app/opportunities/backlog.py` |
| Cron `0 */8 * * *` → `0 10 * * 2,5` (system tz, `Africa/Cairo`) | `ops/personal-branding-agent.cron` |
| Weekly target check: record `weekly_target_jeopardy` + notify once per ISO week when the posts already recorded plus the runs still to come cannot reach the target | `app/workflows/branding.py`, `app/config.py` (`WEEKLY_PUBLISH_TARGET`, `BRANDING_RUNS_PER_WEEK`) |

The target is advisory: it never forces a post through a failed quality gate
and never changes a run's exit code. The full `schedule_policy`/`missed_windows`
machinery is deliberately left unwired — the counter above is the minimal
"did we fall behind this week, and tell someone" check.

`docs/implementation-status.md` still describes the original 8-hour interval in
its Step 11 narrative; it is kept as the historical build record, while the
operational docs (`scheduling.md`, `deployment.md`, `state-model.md`,
`publishing.md`) state the current cadence.

## Verification

- **Incident reproduction** (`tests/test_incident_reproduction.py`): the exact
  three real chunks of the incident document drive the *backlog and store*
  links of the chain — a catalog-only tail is never persisted; a mixed pool
  persists the story, not the footer; a queued snapshot frozen on the footer is
  refreshed in place to the story (same row, same lifecycle state); and the
  incident's decorated label resolves instead of declining. It is not a single
  retrieval→generation end-to-end test: the retrieval half (narrative sibling
  selection) is covered by `tests/test_evidence_roles.py`, and the operational
  repair half by `tests/test_opportunity_repair.py`.
- **Schema migration on a disposable production copy**: v9 → v13 applies
  cleanly, all 24 opportunities preserved (14 queued), `publication_metrics`
  present, an empty baseline reports `None` rather than a misleading `0.0`, and
  the recreated `trg_publish_intents_run_limit` refuses a second intent for the
  same run while allowing the first.
- **Cadence**: `tests/test_weekly_target.py` (9) covers the weekly-target
  status and enforcement (met / one run left / jeopardy / dedupe / disabled);
  `tests/test_branding_backlog.py` and `tests/test_publishing_service.py`
  cover the one-publish bound and the one-intent-per-run trigger;
  `tests/test_scheduling.py` asserts the `0 10 * * 2,5` line and the absence of
  `0 */8`.
- **Full regression**: 1385 passed, 5 failed — the five known pre-existing
  failures below; no other suite fails.

## Pre-existing failures (unchanged, not regressions)

Confirmed by running each at `HEAD` with the working tree stashed:

- `tests/test_autonomous_evaluation.py` — 4 tests
  (`test_no_publication_opportunity_sends_nothing`,
  `test_duplicate_candidate_is_refused_before_any_request`,
  `test_weak_evidence_prefers_no_post`, `test_recovery_after_interrupted_run`):
  each `assert report["emails"] == 0` but receives `1`. Not in the CI baseline;
  captured in the incident report as a separate finding.
- `tests/test_branding_startup.py::test_branding_config_constructs_with_normal_defaults`:
  `cfg.publish_fn` is `None` where the test expects `_default_publish`.

## Known pre-existing lint (not introduced here)

`app/state/schema.py` `ISC004` (throughout), `app/state/store.py`
`UP035`/`F401`/`PYI034`, and the same classes in `app/opportunities/backlog.py`,
`app/workflows/branding.py`, `app/agent/agent.py`, `app/verification/verifier.py`.
Every new file passes `ruff check` clean. The only new findings introduced by
this work are two `S112` (`try`/`except`/`continue`) in the best-effort
`_record_run_outcomes` in `app/workflows/branding.py`, which are intentional
(an informational report must never change what happened) and cosmetic.

## Operational notes

- The metrics importer is a reading aid only: it feeds no decision and writes
  one table. `.venv/bin/python -m app.metrics.import_metrics FILE` is a dry run;
  add `--apply` to record. See `docs/operations/publication-metrics.md`.
- Ranked retrieval scores are not persisted, so no embedding evaluation was
  re-run; the incident was reconstructed from the stored chunk ids.
- No production state was modified *during Phases 0–8*. The separate, explicit
  production rollout (migration + repair + canary) was executed later the same
  day — see "Production rollout — executed 2026-10-18" below.

## Release-readiness status (reviewed 2026-10-18)

Verified by read-only inspection; no production state was changed.

- **Active runtime.** The installed crontab (`crontab -l`) runs
  `.venv/bin/python -m app.workflows.branding` with
  `PROJECT_ROOT=/home/alaabadawii/LLMs/IBM/Build_RAG_Applications_Get_Started/PersonalBrandingAgent`
  — i.e. **this working tree**, so the modified code is what the next scheduled
  run executes. There is no separate deploy step.
- **Migration is automatic and had not yet run (state at review time).**
  `StateStore.__init__` calls `ensure_schema`, so *any* open of the store
  applies pending migrations. At review time the live operational database
  `state_db/operational_state.db` was still at **schema version 9** (24
  opportunities, 14 queued, integrity `ok`). It has since been migrated to v13
  under the rollout below; the review-time statement above is retained as the
  before-state.
- **The repair dry run is not read-only against production.** Even with the
  default `dry_run=True`, `app/opportunities/repair.py` constructs a
  `StateStore` and therefore migrates the active database. The repair CLI also
  has no `--database` flag (only `--apply`/`--limit`), so it cannot be pointed
  at a copy. A rehearsal was therefore run against a consistent read-only copy
  (`sqlite3 ".backup"`): migration v9→v13 succeeded, **14 stale rows, 3 would
  change** (`opp_4cf21f3a5c7d`, `opp_045fe2e85214`, `opp_0cd2e117277f` — all
  `stories_lessons`, footer-only → narrative `:0`/`:1`), and no row's status or
  attempt count moved.
- **Known limitation (backlog hygiene).** A stale row whose document yields no
  narrative is left unchanged by repair, so it keeps `snapshot_version = 1`; and
  `_release_or_retire` retires only *current*-snapshot rows. Such a row is
  therefore neither repaired nor retired and rotates indefinitely (≈11 of the 14
  existing rows, mostly `audit`/`evidence`/thin `in_progress_courses`). Because
  claim order is `attempts ASC, created_at ASC`, these high-attempt rows sort
  behind fresh discoveries, so this wastes backlog rows rather than starving the
  budget — but it does not fully deliver the "retirement" goal for
  non-repairable material.
- **Test-integrity note.** `StateStore.schema_version` returns the code
  constant `SCHEMA_VERSION`, not the database's recorded version, so
  assertions of the form `store.schema_version == 13` cannot fail and do not
  prove a migration ran. The replay test in `tests/test_state_schema.py`
  (which builds a real v9 store and migrates it) is the meaningful check.

## Production rollout — executed 2026-10-18

Controlled rollout of the twice-weekly cadence, performed stage by stage. Every
result below was observed, not assumed. Nothing here was done without an actual
check; skips are stated as skips.

### Stage 1 — preflight and state protection

- **Repo**: `/home/alaabadawii/LLMs/IBM/Build_RAG_Applications_Get_Started/PersonalBrandingAgent`,
  branch `main`, HEAD `97334e62`; 41 modified + 15 untracked paths in this
  project (all rollout work) plus one unrelated modified path under
  `Agentic_AI_with_LangChain_and_LangGraph/` (left untouched). No commit, reset,
  clean, or stash was performed.
- **Timezone**: system zone `Africa/Cairo` (`/etc/timezone`, `timedatectl` →
  EEST +0300). cron 3.0 has no `CRON_TZ`, so cron times are local by
  definition.
- **Writers**: no process held `state_db/operational_state.db` (verified via a
  `/proc/*/fd` scan; `lsof`/`fuser` unavailable). cron service is active; no
  other branding/sync timers exist.
- **Pause**: the installed crontab was backed up, then both job lines
  (`app.workflows.branding`, `app.workflows.sync`) were commented `# PAUSED`
  and reinstalled. Both jobs can open the store (both call `StateStore` →
  `ensure_schema`), so both were paused for the duration.
- **Backup**: `~/backups/personal-branding-agent/rollout-2026-10-18/operational_state.pre-migration.db`
  (dir mode 700, file mode 600), taken with Python's `sqlite3.Connection.backup`
  (a consistent SQLite backup, not a filesystem copy). `PRAGMA integrity_check`
  = **ok**. Single self-contained file (the empty WAL sidecar was checkpointed
  and removed, then integrity re-verified).
- **Baseline recorded** (`baseline.pre-migration.json`): schema **v9**, 24
  opportunities (**9 published / 14 queued / 1 requires_review**), 24 distinct
  fingerprints, 14 publish intents, 14 publications, 1 historical run with 2
  intents (the migration-9 relaxation).
- **Recovery artifacts**: original + paused crontabs, `working-tree.patch`,
  an untracked/source/`.env` tarball, git status/HEAD, and `RESTORE.md` with
  the exact restore procedure.

### Stage 2 — controlled migration (v9 → v13)

- Authoritative path confirmed: `app.paths.STATE_DB_PATH` =
  `state_db/operational_state.db`.
- Applied with one controlled open (`StateStore()`), the project's established
  mechanism.
- **Real version read from the ledger** (not the code constant): applied
  versions `[1..13]`, `current_version` = **13**. `integrity_check` = **ok**.
- `opportunity_outcomes` and `publication_metrics` tables present;
  `snapshot_version`/`snapshot_hash` columns present.
- 24 opportunities preserved, **9 published / 14 queued / 1 requires_review**,
  24 distinct fingerprints (no duplicates). Queued rows' ids, topics, and
  attempts are byte-identical to the pre-migration baseline.
- One-publish-per-run trigger verified both by definition
  (`trg_publish_intents_run_limit`, `>= 1`) and behaviourally inside a
  rolled-back transaction: the first intent was accepted, the second was
  refused with `at most 1 publish intent per run`; the transaction rolled back
  and live counts were unchanged.

### Stage 3 — evidence snapshot repair

- Dry run (project repair functions via a direct `chromadb` client; the
  `get_vector_store()` CLI path loads the HuggingFace model and hung, and
  repair only needs `collection.get(...)`): **14 stale rows, 3 changed** — the
  expected three, all `stories_lessons`:
  `opp_045fe2e85214`, `opp_4cf21f3a5c7d`, `opp_0cd2e117277f`.
- The planned "after" chunks were fetched and confirmed narrative-bearing
  (`has_narrative=True`) lesson content, not catalog tails. Plan matched the
  rehearsal.
- Applied: all three moved from catalog-only `:2` chunks to narrative
  `:0`/`:1` chunks; `snapshot_version` 1 → **2**; each now has 6/6 narrative
  evidence items. **Statuses (queued) and attempts (2) unchanged**, no new or
  duplicate opportunities. Re-inspection: **11 stale rows, 0 would repair**.
  `integrity_check` = **ok**. The 11 weak rows were left in place (not
  deleted); selection/lifecycle policies keep them behind strong candidates.

### Stage 4 — LinkedIn credential

- **No re-authorization was needed.** The stored credential's signed
  `id_token.iat` dates it 2026-10-09; expiry **2026-12-08T14:59:04Z** (~51.5
  days) — not the stale "expired 2026-10-02" from the earlier review. Scope
  includes `w_member_social`; there is no refresh token (expected).
- Application lifecycle check (`check_credential`) reported **valid**;
  `/v2/userinfo` returned **HTTP 200** (identity present, email verified).
- No token, secret, code, or token-file content was printed. No credential-test
  post was created. Note: `w_member_social` permission has no non-posting
  probe in the codebase; it is evidenced by the Stage 5 canary's successful
  post.

### Stage 5 — supervised publishing canary

- Schedules stayed paused; `MAX_PUBLISHES_PER_RUN = 1` and the DB trigger were
  confirmed before running. Ran exactly one foreground invocation of the normal
  entry point: `python -m app.workflows.branding`.
- **Run**: `branding-20261018T025056Z-2cb3c100`.
- Claimed 2 candidates (decision budget 2). `opp_98f8f1b02cc8`
  (`in_progress_courses`, attempts 2) was **deferred (no_value)** — insufficient
  concrete detail; attempts 2 → 3.
- `opp_045fe2e85214` (**one of the repaired `stories_lessons` rows**) was
  selected; the agent proposed `stories_lessons` with 2 evidence items from the
  narrative chunks `751e…:0`/`751e…:1`.
- **Draft**: 809 chars, 2 citations, 0 unresolved labels. **Verification**:
  PASS (7 claims, 0 findings, not degraded); duplicate gate not triggered.
- **Published exactly one post**: `urn:li:share:7517417253945151488` (API
  version 202607), recorded `publication_id = pub_a8f9b0c8353c`,
  `intent_id = intent_265bda4d64e9`,
  `content_hash = e4fc70cdbbd4…`. Run exited **0**.
- **Run outcome caveat**: the run row's outcome is `DO_NOT_PUBLISH` — which
  `RunOutcome` defines as the *success* value — with
  `detail.published = true` and the post id attached by the backlog path. The
  publication is proven by the `publications` row, not by the outcome name.
  This is pre-existing behaviour, not a change made here; it is flagged so
  observers do not misread a successful publish as "nothing published".
- **Reconciliation**: opportunities now **10 published / 13 queued / 1
  requires_review**; 15 publications, 15 intents; only the single historical
  run has two intents; `integrity_check` = **ok**. `opp_045fe2e85214` →
  `publication_id = pub_a8f9b0c8353c`, `last_decision = published`.
- Weekly-target monitor ran after the run and did **not** alert, correctly: 3
  posts were already published this ISO week (Oct 14, Oct 15, Oct 18), so the
  target of 2 was met. A hypothetical target of 5 with no run left reports
  `in_jeopardy = True`, confirming the check is honest and target-driven, and
  it never touches a publish gate.

### Stage 6 — schedule enabled

- Installed `ops/personal-branding-agent.cron`; verified via `crontab -l`:
  - branding: `0 10 * * 2,5` (Tue + Fri 10:00, Africa/Cairo)
  - sync: `10 2 * * *` (unchanged)
  - no `PAUSED` lines remain; no unrelated entries were present or removed.
- Effective production config confirmed: `WEEKLY_PUBLISH_TARGET = 2`,
  `BRANDING_RUNS_PER_WEEK = 2`, `MAX_PUBLISHES_PER_RUN = 1`.

### Rollback readiness

- Pre-migration backup retained at the path above.
- Rollback **rehearsed** (non-destructive): the backup was restored to a temp
  path and verified — `integrity_check` = ok, version **9**, 24 opportunities
  (9/14/1). Procedure documented in `RESTORE.md`; the original crontab copy is
  available to revert the schedule.

### Checks actually executed

- `tests/test_weekly_target.py` — 9 passed.
- Focused suite (`test_branding_backlog`, `test_publishing_service`,
  `test_publishing_duplicates`, `test_opportunity_backlog`,
  `test_opportunity_changes`, `test_state_store`, `test_state_schema`,
  `test_operations_docs`, `test_scheduling`, `test_notify_service`) — 304
  passed.
- Full suite — **1385 passed, 5 failed**, the 5 known pre-existing failures
  listed above (unchanged).
- Migration, trigger, repair, credential, canary, and rollback checks as
  detailed above.

### Unresolved / residual risks (not claimed as resolved)

- The live canary **published a real, public post** under the user's account,
  authorized explicitly for this one run.
- The workflow has **no pre-publication human approval gate**; future scheduled
  runs will decide, verify, and publish autonomously. This was the documented
  Stage 5 caveat and remains a standing operational characteristic.
- 5 pre-existing test failures and a pre-existing
  `interrupted_run:sync-20260923T103808Z-362dd1c0` failure (occurrence 15,
  unrelated to branding) remain.
- Backlog hygiene limitation for non-repairable stale rows (~11) remains, as
  described under "Known limitation" above.
- The rollout changed production state and the schedule; the working tree is
  intentionally left uncommitted. No Git push or commit was performed.
- The repair was executed through the project's repair functions with a
  model-free Chroma client because the bundled `repair.py` CLI's
  `get_vector_store()` path hung on embedding-model load; the CLI itself was
  not used end-to-end.
