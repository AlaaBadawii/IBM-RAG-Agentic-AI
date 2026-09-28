"""The 8-hour branding workflow (``PLAN.md`` Step 11).

Owns and sequences the existing branding pipeline — nothing more:

    context  →  decide  →  publish  →  record outcome + notify on failure

* ``context`` assembles the Step 4 branding context from retrieval and
  operational state, persists every meaningful discovery to the
  content-opportunity backlog (idempotent — re-discovery never duplicates),
  and loads the actionable backlog: queued opportunities plus newly
  discovered ones. Stale claims left by finished runs are recovered first.
* ``decide`` runs the Step 10 ``BrandingAgent`` (which drives Step 8
  generation and the Step 9 verification gates under Step 9's own stopping
  rule). The workflow branches on the returned ``AgentResult``; it never
  re-derives the decision. With a non-empty backlog, up to
  ``MAX_PUBLISHES_PER_RUN`` claimed opportunities are each decided
  independently; with an empty backlog the run is exactly the historical
  single-shot path.
* ``publish`` sends up to ``MAX_PUBLISHES_PER_RUN`` posts through the Step 6
  publishing service, each with its own intent lifecycle and its own
  recovery. An ambiguous outcome is never retried — it escalates to a
  person. Opportunities that are not selected stay queued, untouched.
* Every phase transition is recorded; a failure identifies its phase.
* A ``workflow_runs`` row tracks the run from start to its recorded outcome.
* The workflow — never the Agent — classifies the outcome and decides whether
  to notify. The Agent holds no notifier and makes no notification decision.
* This workflow **never ingests or syncs sources** — asserted structurally by
  the test suite, not just behaviourally.

Outcomes — three independent axes, never conflated:

* Agent decision (``AgentDecision``): ``PUBLISH`` or ``DO_NOT_PUBLISH``.
  What the Agent concluded; a ``PUBLISH`` is unconstructible without a
  passing verification.
* Publication decision (``PublishDecision``): ``PUBLISHED``, ``REFUSED``,
  ``FAILED``, or ``UNKNOWN_REQUIRES_REVIEW``. What Step 6 did, recorded on
  the publication row with the LinkedIn post id as evidence.
* Run outcome (``RunOutcome``): ``DO_NOT_PUBLISH`` (exit 0),
  ``WORKFLOW_FAILED`` (exit 1), or ``REQUIRES_HUMAN_INTERVENTION``
  (exit 2). Whether the workflow completed and whether a person is
  needed — *not* whether a post went out. A successful publication
  terminates ``DO_NOT_PUBLISH`` with ``{"published": True,
  "linkedin_post_id": ...}`` in the result detail and exactly one linked
  ``PUBLISHED`` publication row: the pair is the consistent record, and a
  test pins that a published run always has it.

* ``DO_NOT_PUBLISH`` (exit 0): no opportunity, the Agent declined, the gate
  refused, a duplicate refused, or a post was published. No *failure*
  notification is sent; a published post is reported once as a publication.
* ``WORKFLOW_FAILED`` (exit 1): a phase could not complete — persist the
  failed phase + exactly one failure notification.
* ``REQUIRES_HUMAN_INTERVENTION`` (exit 2): an ambiguous publication, an
  unresolved earlier attempt, an expired credential, or another condition the
  system cannot resolve — persisted separately + exactly one notification.

``python -m app.workflows.branding`` runs it once and exits with the outcome's
exit code. No scheduler lives here (Step 12).
"""
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

from app.agent.enums import NoPublishReason
from app.errors import StateStoreError
from app.logging_config import get_logger, setup_logging
from app.notify.service import NotificationService
from app.opportunities.backlog import OpportunityDecision
from app.state.enums import OpportunityStatus, PublishState, RunOutcome, Workflow
from app.state.store import StateStore
from app.workflows.common import (
    EXIT_OK,
    Escalation,
    WorkflowResult,
    finish,
    record_phase_failure,
    run_phase,
    start,
)
from app.workflows.scheduled import EXIT_LOCKED, WorkflowLocked, workflow_lock

logger = get_logger(__name__)

#: The branding workflow's phases, in order. The workflow enters each one,
#: and each transition is recorded — so a run's trail is queryable afterwards.
BRANDING_PHASES = ("context", "decide", "publish")

__all__ = ["BRANDING_PHASES", "BrandingConfig", "main", "run_branding"]


def _default_assemble(store: StateStore):
    """The real context binding: retrieval, then the Step 4 assembler.

    The retrieval is **stratified by the corpus's own priority order**, not by
    similarity to the query. :mod:`app.retrieval.strata` carries the evidence
    and states plainly that this ordering is a deliberate policy override —
    read it before changing anything here.

    Two layers of narrowing, both necessary and neither sufficient alone:

    * the corpus (:data:`app.retrieval.scope.CURATED`) — the synchronized
      ``@source/*`` mirrors are 94% of the collection and, unscoped, take every
      candidate slot a general-purpose query has to offer;
    * the stratum — inside the curated corpus, certificates answer this query
      better than projects do, measurably: their *median* document outranks the
      best ``completed_projects`` document. Scoping alone returned five
      certificates, no project, and not the file recording the very system the
      Agent was deciding whether to announce.

    The query is unchanged, and it is not a knob: three rewordings were
    measured against the scoped corpus and none put the target in the top-5.
    """
    from app.context import build_context
    from app.retrieval.strata import stratified_retrieve

    # Coverage before similarity, within each stratum: sources the system has
    # already persisted as opportunity evidence sort behind material it has
    # never turned into an opportunity, so newly added documents displace
    # incumbents that would otherwise keep their slots forever. The preference
    # is purely ordinal inside a stratum — same query, strata, budget, and
    # exclusions — and vacuous when nothing is covered yet.
    known_sources = store.covered_evidence_sources()
    result = stratified_retrieve(
        "recent professional work, projects, and achievements worth sharing",
        known_sources=known_sources,
    )
    return build_context(result, store)


def _default_agent(store: StateStore):
    """The real decision binding: the Step 10 agent over the real services."""
    from app.agent import BrandingAgent, LlmContentReasoner
    from app.generation import PostGenerator
    from app.publishing import PublishingHistory
    from app.verification import EvidenceVerifier, LlmSupportJudge

    return BrandingAgent(
        reasoner=LlmContentReasoner(),
        generator=PostGenerator(),
        verifier=EvidenceVerifier(judge=LlmSupportJudge()),
        history=PublishingHistory(store),
    )


def _default_publish(agent_result, run_id: str, store: StateStore):
    """The real publish binding: one post through the Step 6 service."""
    from app.publishing import PublishingService

    assert agent_result.draft is not None, (
        "the publish phase is entered only for a publishable agent result"
    )
    return PublishingService(store).publish(
        _build_publish_request(agent_result, None),
        run_id,
    )


def _default_history(store: StateStore):
    """The real history binding: the Step 6 read service (never the store)."""
    from app.publishing import PublishingHistory

    return PublishingHistory(store)


def _default_notifier(store: StateStore):
    """The real notification binding: the Step 7 service over SMTP config."""
    return NotificationService(store)


def _default_persist(store: StateStore, context: Any):
    """The real discovery binding: persist meaningful topics as backlog rows.

    Defensive: anything without evidence sections (including instrumented
    stand-ins) persists nothing and returns ``[]``.
    """
    from app.opportunities.backlog import persist_discoveries

    return persist_discoveries(store, context)


def _default_backlog(store: StateStore, run_id: str):
    """The real backlog binding: recover stale claims, then load the pool."""
    store.recover_stale_claims(run_id)
    return store.list_backlog()


def _default_claim(store: StateStore, run_id: str, limit: int):
    """The real claim binding: atomically take up to ``limit`` rows."""
    return store.claim_opportunities(run_id, limit)


def _default_opportunity_context(store: StateStore, opportunity: Any):
    """The real per-opportunity input: rebuild it from the stored snapshot.

    The opportunity stays actionable even when current retrieval omits it,
    because its input no longer depends on retrieval at all.
    """
    from app.opportunities.backlog import build_opportunity_context

    return build_opportunity_context(opportunity)


def _build_publish_request(agent_result, opportunity_id: str | None):
    """The Step 6 request one verified draft implies, with backlog linkage."""
    from app.publishing import PublishRequest, evidence_ref

    proposal = agent_result.proposal
    refs = tuple(
        evidence_ref(item.source, item.chunk_id)
        for item in (proposal.evidence if proposal is not None else ())
    )
    return PublishRequest(
        content=agent_result.draft.content,
        topic=proposal.topic if proposal is not None else None,
        angle=proposal.angle if proposal is not None else None,
        project=proposal.project if proposal is not None else None,
        evidence=refs,
        opportunity_id=opportunity_id,
    )


def _default_publish_one(agent_result, run_id: str, store: StateStore,
                         opportunity: Any):
    """The real per-opportunity publish: one post, one intent lifecycle."""
    from app.publishing import PublishingService

    return PublishingService(store).publish(
        _build_publish_request(
            agent_result,
            opportunity.opportunity_id if opportunity is not None else None,
        ),
        run_id,
    )


@dataclass
class BrandingConfig:
    """The branding workflow's seams. Defaults are the real layers; tests
    inject fakes. No real LinkedIn, SMTP, ingestion, or LLM call happens
    unless the default bindings are used."""

    store_factory: Callable[[], StateStore] = field(
        default_factory=lambda: StateStore
    )
    assemble_fn: Callable[[StateStore], Any] = field(
        default_factory=lambda: _default_assemble
    )
    agent_factory: Callable[[StateStore], Any] = field(
        default_factory=lambda: _default_agent
    )
    publish_fn: Callable[[Any, str, StateStore], Any] | None = field(
        default=None
    )
    """Legacy single-shot publish seam: ``(agent_result, run_id, store)``.

    ``None`` means the real Step 6 binding. An explicitly injected fake is
    honored by *both* paths: the backlog path wraps it per selection (the
    fake then owns transport, as the evaluation suite's fakes do), while an
    injected ``publish_one_fn`` takes precedence for backlog selections.
    """
    history_fn: Callable[[StateStore], Any] = field(
        default_factory=lambda: _default_history
    )
    notifier_factory: Callable[[StateStore], Any] = field(
        default_factory=lambda: _default_notifier
    )
    persist_fn: Callable[[StateStore, Any], list] = field(
        default_factory=lambda: _default_persist
    )
    backlog_fn: Callable[[StateStore, str], list] = field(
        default_factory=lambda: _default_backlog
    )
    claim_fn: Callable[[StateStore, str, int], list] = field(
        default_factory=lambda: _default_claim
    )
    opportunity_context_fn: Callable[[StateStore, Any], Any] = field(
        default_factory=lambda: _default_opportunity_context
    )
    publish_one_fn: Callable[[Any, str, StateStore, Any], Any] | None = field(
        default=None
    )
    """Per-selection publish seam: ``(agent_result, run_id, store, opp)``.

    ``None`` falls back to an explicitly injected ``publish_fn`` (wrapped
    per selection), else to the real Step 6 binding with backlog linkage.
    """


def _prepare_run(cfg: BrandingConfig, store: StateStore, run_id: str):
    """Assemble, persist discoveries, and load the actionable backlog.

    One ``context`` phase row covers all three: assembly is the historical
    step, persistence makes every meaningful discovery durable before any
    selection happens, and the backlog load (which first recovers stale
    claims from finished runs) is the pool this run selects from. A failure
    in any of them means the run cannot know what it may publish, so the
    run fails closed on the ``context`` phase — it never publishes from an
    input it could not record.
    """
    context = cfg.assemble_fn(store)
    persisted = cfg.persist_fn(store, context) or []
    pool = cfg.backlog_fn(store, run_id) or []
    logger.info(
        "Branding run %s prepared %d persisted opportunitie(s), %d in backlog",
        run_id, len(persisted), len(pool),
    )
    return context, list(persisted), list(pool)


def run_branding(config: BrandingConfig | None = None) -> WorkflowResult:
    """Run one branding pass and return its structured result.

    Up to ``MAX_PUBLISHES_PER_RUN`` posts are published per run: with an
    empty backlog the run is the historical single-shot path (one optional
    draft, the publish phase entered at most once); with a backlog, up to
    the bound of claimed opportunities are each decided and published
    independently. See the module docstring for the outcome table.

    The whole run executes under the Step 12 overlap guard: a second
    invocation while this workflow is locked raises :class:`WorkflowLocked`
    without running anything.
    """
    cfg = config or BrandingConfig()
    try:
        store = cfg.store_factory()
    except StateStoreError as exc:
        logger.error("Branding workflow could not open the state store: %s", exc)
        raise
    with workflow_lock(store, Workflow.BRANDING):
        run = start(store, Workflow.BRANDING)
        notifier = cfg.notifier_factory(store)

        try:
            prepared = run_phase(
                store, run, "context",
                lambda: _prepare_run(cfg, store, run.run_id),
            )
            context, persisted, pool = prepared
            agent = cfg.agent_factory(store)
            if pool:
                return _run_backlog_pool(
                    cfg, store, run, notifier, agent,
                    persisted, pool,
                )
            agent_result = run_phase(
                store, run, "decide", lambda: agent.run(context)
            )
        except Escalation as esc:
            return finish(
                store, run, esc.outcome,
                failed_phase=esc.phase, error=esc.error,
                error_category=esc.error_category, notifier=notifier,
            )

        if agent_result.failed:
            failure = agent_result.failure
            assert failure is not None  # ``failed`` is exactly "carries a failure"
            error = (
                f"branding reasoning failed ({failure.category.value}): "
                f"{failure.detail}"
            )
            logger.warning("Branding run %s: %s", run.run_id, error)
            record_phase_failure(store, run, "decide", error, "reasoning_failed",
                                 human=False)
            return finish(
                store, run, RunOutcome.WORKFLOW_FAILED,
                failed_phase="decide", error=error,
                error_category="reasoning_failed",
                notifier=notifier,
                detail={"no_publish_reason": agent_result.reason.value},
            )

        if not agent_result.is_publishable:
            reason = agent_result.reason.value if agent_result.reason else "unknown"
            logger.info(
                "Branding run %s decided DO_NOT_PUBLISH (%s)",
                run.run_id, reason,
            )
            result = finish(
                store, run, RunOutcome.DO_NOT_PUBLISH,
                notifier=notifier,
                detail={
                    "no_publish_reason": reason,
                    "attempts_made": agent_result.attempts_made,
                },
                no_publish_reason=reason,
            )
            _report_no_publish(store, notifier, run.run_id, reason=reason)
            return result

        # The Agent proposed a verified post. Before touching the network, check
        # whether an earlier attempt's outcome is still unknown: publishing over
        # an ambiguity is how a duplicate happens.
        history = cfg.history_fn(store)
        pending = history.requires_review()
        if pending:
            error = (
                "an earlier publication attempt is still awaiting human review "
                f"({len(pending)} unresolved); refusing to publish over an ambiguity"
            )
            logger.warning("Branding run %s: %s", run.run_id, error)
            record_phase_failure(store, run, "publish", error,
                                 "unresolved_ambiguity", human=True)
            return finish(
                store, run, RunOutcome.REQUIRES_HUMAN_INTERVENTION,
                failed_phase="publish", error=error,
                error_category="unresolved_ambiguity",
                notifier=notifier,
            )

        try:
            publish_via = cfg.publish_fn or _default_publish
            report = run_phase(
                store, run, "publish",
                lambda: publish_via(agent_result, run.run_id, store),
            )
        except Escalation as esc:
            return finish(
                store, run, esc.outcome,
                failed_phase=esc.phase, error=esc.error,
                error_category=esc.error_category, notifier=notifier,
            )

        if report.requires_human_intervention:
            error = (
                "publication requires human review: "
                f"{report.message} (decision={report.decision.value})"
            )
            logger.warning("Branding run %s: %s", run.run_id, error)
            record_phase_failure(store, run, "publish", error,
                                 "publication_needs_review", human=True)
            return finish(
                store, run, RunOutcome.REQUIRES_HUMAN_INTERVENTION,
                failed_phase="publish", error=error,
                error_category="publication_needs_review",
                notifier=notifier,
            )
        if report.refused:
            logger.info(
                "Branding run %s published nothing (duplicate refusal: %s)",
                run.run_id, report.message,
            )
            # A duplicate refusal is recorded in detail only: there is no
            # closed-vocabulary NoPublishReason for "a verified draft the
            # duplicate gate refused", so the column stays NULL by design.
            # (A backlog run whose selections were all refused instead
            # records NO_VALUE via _finish_backlog_run; both shapes are
            # pinned by tests and neither is harmonized.)
            result = finish(
                store, run, RunOutcome.DO_NOT_PUBLISH,
                notifier=notifier,
                detail={"refused": True, "refusal": report.message},
            )
            _report_no_publish(
                store, notifier, run.run_id,
                refused=True, refusal=report.message,
            )
            return result
        if report.published:
            post_id = report.linkedin_post_id or ""
            logger.info(
                "Branding run %s published post %s", run.run_id, post_id
            )
            _report_publication(store, notifier, run.run_id, post_id)
            return finish(
                store, run, RunOutcome.DO_NOT_PUBLISH,
                notifier=notifier,
                detail={"published": True, "linkedin_post_id": post_id},
            )
        error = f"publication failed: {report.message}"
        logger.warning("Branding run %s: %s", run.run_id, error)
        record_phase_failure(store, run, "publish", error, "publication_failed",
                             human=False)
        return finish(
            store, run, RunOutcome.WORKFLOW_FAILED,
            failed_phase="publish", error=error,
            error_category="publication_failed",
            notifier=notifier,
        )


def _release_backlog_claim(store: StateStore, opportunity: Any, run_id: str,
                           decision: OpportunityDecision,
                           error: str | None = None,
                           attempts_increment: int = 1) -> None:
    """Return one claim to ``queued`` so a later run may select it again.

    "Not selected" (or "not yet published") is never a resolution: the row
    keeps everything it needs for the next run, with one more attempt
    counted and the reason recorded. Releasing another run's claim raises
    instead of stealing it.
    """
    store.record_opportunity_decision(
        opportunity.opportunity_id, decision.value,
        release_claim=True, run_id=run_id,
        attempts_increment=attempts_increment, error=error,
    )


def _run_backlog_pool(cfg: BrandingConfig, store: StateStore, run: Any,
                      notifier: Any, agent: Any,
                      persisted: list, pool: list) -> WorkflowResult:
    """Decide and publish from the persistent backlog, bounded per run.

    Each claimed opportunity runs the same decide-then-publish pipeline the
    single-shot path uses — reason, generate, verify, duplicate-gate,
    write-ahead intent — with its own claim lifecycle around it:

    * a declined or unrepairable draft releases (or, for an unrepairable
      gate rejection, terminally rejects) only its own row;
    * a definitive publish failure releases only its own row as retryable;
    * an ambiguous publication resolves only its own row to
      ``requires_review``, which no later run republishes;
    * rows never selected stay queued, untouched, by construction: nothing
      here writes them at all.

    A ``StateStoreError`` mid-loop stops the loop rather than guessing:
    claims this run still holds belong to an unfinished run, which is
    exactly what the next run's stale-claim recovery releases.
    """
    from app.publishing.service import MAX_PUBLISHES_PER_RUN

    events: list[tuple] = []
    selections: list[tuple] = []
    published: list[tuple] = []
    tally: dict = {}
    quiet_reason: str | None = None

    try:
        claimed = cfg.claim_fn(store, run.run_id, MAX_PUBLISHES_PER_RUN) or []
    except StateStoreError as exc:
        return _backlog_store_dead(store, run, notifier, str(exc))
    if not claimed:
        logger.info(
            "Branding run %s: backlog holds %d opportunitie(s) but none "
            "could be claimed", run.run_id, len(pool),
        )
        result = finish(
            store, run, RunOutcome.DO_NOT_PUBLISH,
            notifier=notifier,
            detail=_backlog_summary(
                store, persisted, pool, [], [], 0, 0, tally,
                NoPublishReason.NO_VALUE.value),
            no_publish_reason=NoPublishReason.NO_VALUE.value,
        )
        _report_no_publish(
            store, notifier, run.run_id,
            reason=NoPublishReason.NO_VALUE.value,
        )
        return result

    for opportunity in claimed:
        try:
            outcome = _decide_backlog_claim(
                cfg, store, run, agent, opportunity)
        except StateStoreError as exc:
            return _backlog_store_dead(store, run, notifier, str(exc))
        if outcome is None:
            continue
        kind = outcome[0]
        if kind == "selected":
            selections.append((opportunity, outcome[1]))
        elif kind == "quiet":
            quiet_reason = quiet_reason or outcome[1]
        else:
            events.append(outcome[1])

    if selections:
        try:
            _publish_backlog_selections(
                cfg, store, run, notifier, selections,
                published, events, tally)
        except StateStoreError as exc:
            return _backlog_store_dead(store, run, notifier, str(exc))

    return _finish_backlog_run(
        store, run, notifier, persisted, pool, selections,
        published, events, tally, quiet_reason, claimed)


def _backlog_store_dead(store: StateStore, run: Any, notifier: Any,
                        error: str) -> WorkflowResult:
    """The store stopped answering mid-run: fail closed, keep claims safe.

    Claims still held belong to this unfinished run, so the next run's
    stale-claim recovery — not this run's guesswork — decides their fate.
    """
    logger.warning("Branding run %s: state store failure: %s",
                   run.run_id, error)
    return finish(
        store, run, RunOutcome.REQUIRES_HUMAN_INTERVENTION,
        failed_phase="decide", error=error,
        error_category="state_store_unavailable",
        notifier=notifier,
    )


def _decide_backlog_claim(cfg: BrandingConfig, store: StateStore, run: Any,
                          agent: Any, opportunity: Any):
    """Run one claimed opportunity through decide; return its disposition.

    Returns ``("selected", agent_result)``, ``("quiet", reason)``, or
    ``("event", (outcome, phase, error))``. Releases or finalizes the claim
    for every non-selected outcome, so the caller only tracks selections.
    """
    opp_id = opportunity.opportunity_id

    def _run_one():
        # Rebuilding the input and reasoning over it are one ``decide``
        # phase row per claim — the same trail shape as the single-shot
        # path, so one selection reads exactly like the historical run.
        opp_context = cfg.opportunity_context_fn(store, opportunity)
        return agent.run(opp_context)

    try:
        agent_result = run_phase(store, run, "decide", _run_one)
    except Escalation as esc:
        _release_backlog_claim(
            store, opportunity, run.run_id,
            OpportunityDecision.DEFERRED, esc.error)
        return ("event", (esc.outcome, esc.phase, esc.error))

    if agent_result.failed:
        failure = agent_result.failure
        assert failure is not None
        error = (
            f"branding reasoning failed for opportunity {opp_id} "
            f"({failure.category.value}): {failure.detail}"
        )
        logger.warning("Branding run %s: %s", run.run_id, error)
        record_phase_failure(store, run, "decide", error, "reasoning_failed",
                             human=False)
        _release_backlog_claim(
            store, opportunity, run.run_id,
            OpportunityDecision.DEFERRED, error)
        return ("event", (RunOutcome.WORKFLOW_FAILED, "decide", error))

    if not agent_result.is_publishable:
        reason = (agent_result.reason if agent_result.reason is not None
                  else NoPublishReason.NO_VALUE)
        rationale = agent_result.rationale or reason.value
        if reason is NoPublishReason.GATE_REJECTED:
            # Unrepairable by rewriting: an explicit terminal rejection with
            # its reason, never a silent disappearance.
            store.finalize_opportunity(
                opp_id, OpportunityStatus.REJECTED, run_id=run.run_id,
                decision=OpportunityDecision.REJECTED.value, error=rationale)
            logger.info(
                "Branding run %s: opportunity %s rejected by the gate",
                run.run_id, opp_id)
        else:
            _release_backlog_claim(
                store, opportunity, run.run_id,
                OpportunityDecision.DEFERRED, rationale)
            logger.info(
                "Branding run %s: opportunity %s deferred (%s)",
                run.run_id, opp_id, reason.value)
        return ("quiet", reason.value)

    logger.info(
        "Branding run %s: opportunity %s selected for publishing",
        run.run_id, opp_id)
    return ("selected", agent_result)


def _publish_entry(cfg: BrandingConfig):
    """Resolve which publish binding backlog selections use.

    An injected ``publish_one_fn`` wins; otherwise an injected legacy
    ``publish_fn`` is wrapped per selection (it owns transport, as the
    evaluation fakes do); otherwise the real Step 6 binding with backlog
    linkage serves.
    """
    if cfg.publish_one_fn is not None:
        return cfg.publish_one_fn

    def _via_legacy(agent_result, run_id: str, store: StateStore,
                    _opportunity: Any):
        assert cfg.publish_fn is not None  # resolved by the caller below
        return cfg.publish_fn(agent_result, run_id, store)

    if cfg.publish_fn is not None:
        return _via_legacy
    return _default_publish_one


def _publish_backlog_selections(cfg: BrandingConfig, store: StateStore,
                                run: Any, notifier: Any,
                                selections: list, published: list,
                                events: list, tally: dict) -> None:
    """Publish each selection with its own intent lifecycle.

    Results accumulate into ``published``, ``events``, and ``tally``;
    every claim is released or finalized exactly once, whatever the
    outcome.
    """
    publish_one = _publish_entry(cfg)
    history = cfg.history_fn(store)
    pending = history.requires_review()
    if pending:
        error = (
            "an earlier publication attempt is still awaiting human review "
            f"({len(pending)} unresolved); refusing to publish over an ambiguity"
        )
        logger.warning("Branding run %s: %s", run.run_id, error)
        record_phase_failure(store, run, "publish", error,
                             "unresolved_ambiguity", human=True)
        for opportunity, _ in selections:
            _release_backlog_claim(
                store, opportunity, run.run_id,
                OpportunityDecision.DEFERRED, error, attempts_increment=0)
        events.append(
            (RunOutcome.REQUIRES_HUMAN_INTERVENTION, "publish", error))
        return

    for opportunity, agent_result in selections:
        try:
            report = run_phase(
                store, run, "publish",
                lambda: publish_one(
                    agent_result, run.run_id, store, opportunity),
            )
        except Escalation as esc:
            _triage_publish_exception(
                store, opportunity, run.run_id, esc, events)
            continue
        _settle_publish_report(
            store, run, notifier, opportunity, report,
            published, events, tally)


def _settle_publish_report(store: StateStore, run: Any, notifier: Any,
                           opportunity: Any, report: Any,
                           published: list, events: list,
                           tally: dict) -> None:
    """Resolve one claim from the publishing service's report."""
    opp_id = opportunity.opportunity_id
    if report.published:
        post_id = report.linkedin_post_id or ""
        publication_id = (report.publication.publication_id
                          if report.publication is not None else None)
        store.finalize_opportunity(
            opp_id, OpportunityStatus.PUBLISHED, run_id=run.run_id,
            publication_id=publication_id,
            decision=OpportunityDecision.PUBLISHED.value)
        logger.info("Branding run %s published opportunity %s as post %s",
                    run.run_id, opp_id, post_id)
        _report_publication(store, notifier, run.run_id, post_id)
        published.append((opportunity, report))
    elif report.refused:
        _release_backlog_claim(
            store, opportunity, run.run_id,
            OpportunityDecision.DUPLICATE, report.message)
        tally["refused"] = tally.get("refused", 0) + 1
        tally.setdefault("refusal", report.message)
        logger.info(
            "Branding run %s: opportunity %s refused at the duplicate gate",
            run.run_id, opp_id)
    elif report.requires_human_intervention:
        publication_id = (report.publication.publication_id
                          if report.publication is not None else None)
        store.finalize_opportunity(
            opp_id, OpportunityStatus.REQUIRES_REVIEW, run_id=run.run_id,
            publication_id=publication_id,
            decision=OpportunityDecision.REQUIRES_REVIEW.value,
            error=report.message)
        error = (
            "publication requires human review: "
            f"{report.message} (decision={report.decision.value})"
        )
        logger.warning("Branding run %s: %s", run.run_id, error)
        record_phase_failure(store, run, "publish", error,
                             "publication_needs_review", human=True)
        events.append(
            (RunOutcome.REQUIRES_HUMAN_INTERVENTION, "publish", error))
    else:
        _release_backlog_claim(
            store, opportunity, run.run_id,
            OpportunityDecision.PUBLISH_FAILED, report.message)
        error = f"publication failed: {report.message}"
        logger.warning("Branding run %s: %s", run.run_id, error)
        record_phase_failure(store, run, "publish", error,
                             "publication_failed", human=False)
        events.append((RunOutcome.WORKFLOW_FAILED, "publish", error))


def _triage_publish_exception(store: StateStore, opportunity: Any,
                              run_id: str, esc: Escalation,
                              events: list) -> None:
    """Resolve one claim after its publish raised instead of reporting.

    Reads what the store actually holds rather than guessing from the
    exception: a terminal publication finalizes the row from its recorded
    outcome; an ``attempt_started`` intent with no outcome means a post may
    exist, so the row is blocked for a person; anything else provably sent
    nothing, so leftover ``intent_created`` intents are resolved as failed
    (the recovery service's own never-attempted rule) and the row returns
    to the backlog as retryable.
    """
    opp_id = opportunity.opportunity_id
    intents = [intent for intent in store.list_intents_for_run(run_id)
               if intent.opportunity_id == opp_id]
    for intent in intents:
        publication = store.get_publication_for_intent(intent.intent_id)
        if publication is None:
            continue
        if publication.outcome is PublishState.PUBLISHED:
            store.finalize_opportunity(
                opp_id, OpportunityStatus.PUBLISHED, run_id=run_id,
                publication_id=publication.publication_id,
                decision=OpportunityDecision.PUBLISHED.value,
                error=(f"published before the publish call raised "
                       f"({esc.error}); finalized from the stored outcome"))
            return
        if publication.outcome is PublishState.UNKNOWN_REQUIRES_REVIEW:
            store.finalize_opportunity(
                opp_id, OpportunityStatus.REQUIRES_REVIEW, run_id=run_id,
                publication_id=publication.publication_id,
                decision=OpportunityDecision.REQUIRES_REVIEW.value,
                error=(f"ambiguous outcome recorded before the publish "
                       f"call raised ({esc.error})"))
            events.append((RunOutcome.REQUIRES_HUMAN_INTERVENTION,
                           esc.phase, esc.error))
            return
    started = [intent for intent in intents
               if intent.state is PublishState.ATTEMPT_STARTED]
    if started:
        store.finalize_opportunity(
            opp_id, OpportunityStatus.REQUIRES_REVIEW, run_id=run_id,
            decision=OpportunityDecision.REQUIRES_REVIEW.value,
            error=(f"the attempt started and no outcome was recorded "
                   f"({esc.error}); a post may exist"))
        events.append((RunOutcome.REQUIRES_HUMAN_INTERVENTION,
                       esc.phase, esc.error))
        return
    for intent in intents:
        if intent.state is PublishState.INTENT_CREATED:
            store.record_publication(intent.intent_id, PublishState.FAILED)
    _release_backlog_claim(
        store, opportunity, run_id,
        OpportunityDecision.PUBLISH_FAILED, esc.error)
    events.append((esc.outcome, esc.phase, esc.error))


def _backlog_summary(store: StateStore, persisted: list, pool: list,
                     selections: list, published: list,
                     failed: int, needs_review: int,
                     tally: dict | None = None,
                     quiet_reason: str | None = None) -> dict:
    """The multi-publish run record: considered/selected/published/queued.

    Carries the legacy detail keys quiet runs historically exposed —
    ``no_publish_reason`` and, when duplicate gates refused everything,
    ``refused`` — so a single-refusal backlog run reads exactly like the
    historical single-shot refusal.
    """
    try:
        queued_remaining = store.count_backlog()
    except StateStoreError:
        queued_remaining = -1
    tally = tally or {}
    summary = {
        "considered": len(pool),
        "persisted_new": len(persisted),
        "selected": len(selections),
        "published_count": len(published),
        "published_post_ids": [
            report.linkedin_post_id or ""
            for _, report in published
        ],
        "queued_remaining": queued_remaining,
        "failed": failed,
        "requires_review": needs_review,
    }
    if quiet_reason is not None:
        summary["no_publish_reason"] = quiet_reason
    if tally.get("refused") and not published:
        summary["refused"] = True
        summary["refusal"] = tally.get("refusal", "")
    return summary


def _finish_backlog_run(store: StateStore, run: Any, notifier: Any,
                        persisted: list, pool: list, selections: list,
                        published: list, events: list, tally: dict,
                        quiet_reason: str | None,
                        claimed: list | None = None) -> WorkflowResult:
    """Aggregate per-opportunity outcomes into one run outcome.

    Priority: a human-review event outranks a failure, which outranks
    quiet. Published posts were already reported individually as they
    went out; a run that published stays a success even when a sibling
    selection failed — the failure is recorded on its phase and notified,
    but it must not rewrite the published posts as a failed run.
    """
    human = [event for event in events
             if event[0] is RunOutcome.REQUIRES_HUMAN_INTERVENTION]
    failed = [event for event in events
              if event[0] is RunOutcome.WORKFLOW_FAILED]
    if published:
        detail = _backlog_summary(
            store, persisted, pool, selections, published,
            len(failed), len(human), tally)
        if human or failed:
            first = (human + failed)[0]
            logger.warning(
                "Branding run %s published %d post(s) with %d failure(s): %s",
                run.run_id, len(published),
                len(human) + len(failed), first[2])
            record_phase_failure(store, run, first[1], first[2],
                                 "sibling_selection_failed",
                                 human=bool(human))
        return finish(
            store, run, RunOutcome.DO_NOT_PUBLISH,
            notifier=notifier,
            detail={**detail, "published": True,
                    "linkedin_post_id": detail["published_post_ids"][0]
                    if detail["published_post_ids"] else ""},
        )
    if human:
        outcome, phase, error = human[0]
        return finish(
            store, run, outcome,
            failed_phase=phase, error=error,
            error_category="publication_needs_review",
            notifier=notifier,
            detail=_backlog_summary(
                store, persisted, pool, selections, published,
                len(failed), len(human), tally),
        )
    if failed:
        outcome, phase, error = failed[0]
        return finish(
            store, run, outcome,
            failed_phase=phase, error=error,
            error_category="backlog_selection_failed",
            notifier=notifier,
            detail=_backlog_summary(
                store, persisted, pool, selections, published,
                len(failed), len(human), tally),
        )
    reason = quiet_reason or NoPublishReason.NO_VALUE.value
    result = finish(
        store, run, RunOutcome.DO_NOT_PUBLISH,
        notifier=notifier,
        detail=_backlog_summary(
            store, persisted, pool, selections, published, 0, 0,
            tally, reason),
        no_publish_reason=reason,
    )
    _report_no_publish(
        store, notifier, run.run_id,
        reason=reason,
        refused=bool(tally.get("refused")),
        refusal=tally.get("refusal"),
        considered=len(pool),
        selected=len(selections),
        deferred=_deferred_lines(store, claimed or []),
    )
    return result


def _deferred_lines(store: StateStore, claimed: list) -> tuple[str, ...]:
    """One notice line per claimed opportunity that stayed unpublished.

    Read from the stored rows — not from in-memory results — so the lines say
    what the run actually recorded (decision + rationale), whatever path each
    claim took. A row that cannot be read is skipped rather than guessed: a
    shorter list is honest, a fabricated line is not.
    """
    lines: list[str] = []
    for opportunity in claimed or []:
        try:
            row = store.get_opportunity(opportunity.opportunity_id)
        except Exception:  # noqa: BLE001 — informational only
            continue
        if row is None:
            continue
        decision = getattr(row, "last_decision", None) or "unpublished"
        rationale = (getattr(row, "last_error", None) or "").strip()
        if len(rationale) > 200:
            rationale = rationale[:197] + "..."
        entry = f"{row.topic}: {decision}"
        if rationale:
            entry += f" — {rationale}"
        lines.append(entry)
    return tuple(lines)


def _report_publication(store: StateStore, notifier: Any, run_id: str,
                        post_id: str) -> None:
    """Tell the user what went out under their name — exactly once.

    The content comes from the persisted write-ahead intent, not from the
    in-memory draft: the intent is what the publishing service actually
    sent, so the email and LinkedIn cannot silently diverge. A successful
    publish terminates ``DO_NOT_PUBLISH``, which the failure path waives by
    design; without this call nothing would report the post. A delivery
    failure here is logged, never raised: the post is already durably
    published, and failing the run over the email would lie about what
    happened.
    """
    from app.notify.models import PublishedPost

    try:
        intent = store.get_intent_for_run(run_id)
        notifier.notify_publication(
            PublishedPost(
                content=intent.content if intent is not None else "",
                post_id=post_id or None,
            ),
            run_id=run_id,
        )
    except Exception as exc:  # noqa: BLE001 — the publish already happened
        logger.warning(
            "Publication notification for run %s could not be delivered: %s",
            run_id, exc,
        )


def _report_no_publish(store: StateStore, notifier: Any, run_id: str, *,
                       reason: str | None = None,
                       refused: bool = False,
                       refusal: str | None = None,
                       considered: int | None = None,
                       selected: int | None = None,
                       deferred: tuple[str, ...] = ()) -> None:
    """Tell the user nothing went out — exactly once.

    The quiet-run counterpart of :func:`_report_publication`: ``finish()``
    never notifies a ``DO_NOT_PUBLISH`` run and ``notify_run`` waives it, so
    without this call a scheduled run that came back empty-handed would stay
    silent. ``reason`` is the run's persisted ``no_publish_reason`` verbatim;
    a duplicate refusal travels as ``refused`` plus its message instead,
    because it has no ``NoPublishReason`` by design. ``considered``,
    ``selected`` and ``deferred`` are the backlog snapshot the caller already
    holds (backlog path only); ``queued_remaining`` is counted here so every
    quiet notice says what is still waiting, whatever path produced it. A
    delivery failure here is logged, never raised: the run already finished
    ``DO_NOT_PUBLISH`` successfully, and failing it over the email would lie
    about what happened.
    """
    from app.notify.models import NoPublishNotice

    try:
        queued_remaining = store.count_backlog()
    except Exception:  # noqa: BLE001 — the count is informational only
        queued_remaining = None

    try:
        notifier.notify_no_publish(
            NoPublishNotice(reason=reason, refused=refused, refusal=refusal,
                            considered=considered, selected=selected,
                            queued_remaining=queued_remaining,
                            deferred=tuple(deferred)),
            run_id=run_id,
        )
    except Exception as exc:  # noqa: BLE001 — the run already finished
        logger.warning(
            "No-publish notification for run %s could not be delivered: %s",
            run_id, exc,
        )


def main(argv: list[str] | None = None) -> int:
    """Module entry point: ``python -m app.workflows.branding``."""
    del argv  # no flags: the run is fully described by its recorded outcome.
    setup_logging()
    try:
        result = run_branding()
    except WorkflowLocked as locked:
        print(f"branding locked out: {locked}")
        return EXIT_LOCKED
    print(
        f"branding run {result.run_id}: {result.outcome.value} "
        f"(exit {result.exit_code})"
    )
    return result.exit_code if isinstance(result.exit_code, int) else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
