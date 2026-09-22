"""The 8-hour branding workflow (``PLAN.md`` Step 11).

Owns and sequences the existing branding pipeline — nothing more:

    context  →  decide  →  publish  →  record outcome + notify on failure

* ``context`` assembles the Step 4 branding context from retrieval and
  operational state.
* ``decide`` runs the Step 10 ``BrandingAgent`` (which drives Step 8
  generation and the Step 9 verification gates under Step 9's own stopping
  rule). The workflow branches on the returned ``AgentResult``; it never
  re-derives the decision.
* ``publish`` sends at most one post through the Step 6 publishing service.
  An ambiguous outcome is never retried — it escalates to a person.
* Every phase transition is recorded; a failure identifies its phase.
* A ``workflow_runs`` row tracks the run from start to its recorded outcome.
* The workflow — never the Agent — classifies the outcome and decides whether
  to notify. The Agent holds no notifier and makes no notification decision.
* This workflow **never ingests or syncs sources** — asserted structurally by
  the test suite, not just behaviourally.

Outcomes:

* ``DO_NOT_PUBLISH`` (exit 0): no opportunity, the Agent declined, the gate
  refused, or a post was published or refused as a duplicate. No *failure*
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

from app.errors import StateStoreError
from app.logging_config import get_logger
from app.notify.service import NotificationService
from app.state.enums import RunOutcome, Workflow
from app.state.store import StateStore
from app.workflows.common import (
    EXIT_OK,
    Escalation,
    WorkflowResult,
    finish,
    run_phase,
    start,
)

logger = get_logger(__name__)

#: The branding workflow's phases, in order. The workflow enters each one,
#: and each transition is recorded — so a run's trail is queryable afterwards.
BRANDING_PHASES = ("context", "decide", "publish")

__all__ = ["BRANDING_PHASES", "BrandingConfig", "main", "run_branding"]


def _default_assemble(store: StateStore):
    """The real context binding: retrieval, then the Step 4 assembler."""
    from app.context import build_context
    from app.retrieval.engine import RetrievalEngine

    result = RetrievalEngine().retrieve(
        "recent professional work, projects, and achievements worth sharing",
        strategy="hybrid",
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
    from app.publishing import PublishRequest, PublishingService, evidence_ref

    assert agent_result.draft is not None, (
        "the publish phase is entered only for a publishable agent result"
    )
    proposal = agent_result.proposal
    refs = tuple(
        evidence_ref(item.source, item.chunk_id)
        for item in (proposal.evidence if proposal is not None else ())
    )
    return PublishingService(store).publish(
        PublishRequest(
            content=agent_result.draft.content,
            topic=proposal.topic if proposal is not None else None,
            angle=proposal.angle if proposal is not None else None,
            project=proposal.project if proposal is not None else None,
            evidence=refs,
        ),
        run_id,
    )


def _default_history(store: StateStore):
    """The real history binding: the Step 6 read service (never the store)."""
    from app.publishing import PublishingHistory

    return PublishingHistory(store)


@dataclass
class BrandingConfig:
    """The branding workflow's seams. Defaults are the real layers; tests
    inject fakes. No real LinkedIn, SMTP, ingestion, or LLM call happens
    unless the default bindings are used."""

    store_factory: Callable[[], StateStore] = field(
        default_factory=StateStore
    )
    assemble_fn: Callable[[StateStore], Any] = field(
        default_factory=lambda: _default_assemble
    )
    agent_factory: Callable[[StateStore], Any] = field(
        default_factory=lambda: _default_agent
    )
    publish_fn: Callable[[Any, str, StateStore], Any] = field(
        default_factory=lambda: _default_publish
    )
    history_fn: Callable[[StateStore], Any] = field(
        default_factory=lambda: _default_history
    )
    notifier_factory: Callable[[StateStore], Any] = field(
        default_factory=lambda store: NotificationService(store)
    )


def run_branding(config: BrandingConfig | None = None) -> WorkflowResult:
    """Run one branding pass and return its structured result.

    At most one post is published per run: the Agent returns a single optional
    draft, and the publish phase is entered at most once. See the module
    docstring for the outcome table.
    """
    cfg = config or BrandingConfig()
    try:
        store = cfg.store_factory()
    except StateStoreError as exc:
        logger.error("Branding workflow could not open the state store: %s", exc)
        raise
    run = start(store, Workflow.BRANDING)
    notifier = cfg.notifier_factory(store)

    try:
        context = run_phase(
            store, run, "context", lambda: cfg.assemble_fn(store)
        )
        agent = cfg.agent_factory(store)
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
        return finish(
            store, run, RunOutcome.DO_NOT_PUBLISH,
            notifier=notifier,
            detail={
                "no_publish_reason": reason,
                "attempts_made": agent_result.attempts_made,
            },
        )

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
        return finish(
            store, run, RunOutcome.REQUIRES_HUMAN_INTERVENTION,
            failed_phase="publish", error=error,
            error_category="unresolved_ambiguity",
            notifier=notifier,
        )

    try:
        report = run_phase(
            store, run, "publish",
            lambda: cfg.publish_fn(agent_result, run.run_id, store),
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
        return finish(
            store, run, RunOutcome.DO_NOT_PUBLISH,
            notifier=notifier,
            detail={"refused": True, "refusal": report.message},
        )
    if report.published:
        post_id = report.linkedin_post_id or ""
        logger.info(
            "Branding run %s published post %s", run.run_id, post_id
        )
        _report_publication(notifier, agent_result, post_id, run.run_id)
        return finish(
            store, run, RunOutcome.DO_NOT_PUBLISH,
            notifier=notifier,
            detail={"published": True, "linkedin_post_id": post_id},
        )
    error = f"publication failed: {report.message}"
    logger.warning("Branding run %s: %s", run.run_id, error)
    return finish(
        store, run, RunOutcome.WORKFLOW_FAILED,
        failed_phase="publish", error=error,
        error_category="publication_failed",
        notifier=notifier,
    )


def _report_publication(notifier: Any, agent_result: Any, post_id: str,
                        run_id: str) -> None:
    """Tell the user what went out under their name — exactly once.

    A successful publish terminates ``DO_NOT_PUBLISH``, which the failure
    path waives by design; without this call nothing would report the post.
    A delivery failure here is logged, never raised: the post is already
    durably published, and failing the run over the email would lie about
    what happened.
    """
    from app.notify.models import PublishedPost

    try:
        notifier.notify_publication(
            PublishedPost(
                content=agent_result.draft.content if agent_result.draft else "",
                post_id=post_id or None,
            ),
            run_id=run_id,
        )
    except Exception as exc:  # noqa: BLE001 — the publish already happened
        logger.warning(
            "Publication notification for run %s could not be delivered: %s",
            run_id, exc,
        )


def main(argv: list[str] | None = None) -> int:
    """Module entry point: ``python -m app.workflows.branding``."""
    del argv  # no flags: the run is fully described by its recorded outcome.
    result = run_branding()
    print(
        f"branding run {result.run_id}: {result.outcome.value} "
        f"(exit {result.exit_code})"
    )
    return result.exit_code if isinstance(result.exit_code, int) else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
