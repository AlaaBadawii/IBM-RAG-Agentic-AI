"""The publishing service — the only thing that may send a post.

    PublishingService.publish(PublishRequest, run_id) -> PublishReport

This is the layer ``PLAN.md`` Step 6 places between the Agent's decision and
the LinkedIn integration. It owns every publish state transition, and it is the
only reader of publishing history. Nothing above it touches ``StateStore``, and
nothing below it knows what a run is.

What it guarantees, in the order it enforces them:

1. **Nothing is sent that the duplicate checks refuse.** The three checks run
   first, and a refusal writes nothing and sends nothing.
2. **The intent is durable before the request exists.** The write-ahead intent
   is the only duplicate protection that can prevent a *call* rather than
   record one after the fact, because LinkedIn offers no read-back (§5.1).
3. **The attempt is marked before the request is sent**, so the two possible
   interruptions are distinguishable afterwards: an intent still at
   ``intent_created`` means no request was sent, and an intent at
   ``attempt_started`` with no publication means one may have been.
4. **The outcome is recorded from evidence, never assumed.** A post id means
   ``published``; a classified failure means ``failed``; a timeout, a dropped
   connection, or a success without an id means ``unknown_requires_review``.
5. **An ambiguity is never retried.** ``UNKNOWN`` is a state a person resolves,
   not a state another run tries again from.
6. **A store failure stops the publish.** The store is the system's durable
   memory; a run that cannot record what it observed must not go on to act.

What it does **not** claim: exactly-once delivery to LinkedIn. That guarantee is
not achievable without read-back and must not be promised. What the system
actually has is *at most one publication attempt per run reaching the final
publish gate* — enforced by ``ux_publish_intents_run`` in SQLite, not by this
module remembering to check — plus a durable intent, an explicit ambiguous
state, and a recovery path that fails closed.
"""
from datetime import datetime
from functools import partial
from typing import Callable

from app.integrations.linkedin import publish_to_linkedin
from app.integrations.linkedin.enums import PublicationOutcome
from app.integrations.linkedin.models import PublicationResult
from app.state.enums import PublishState
from app.state.models import Publication, PublishIntent
from app.state.store import StateStore, content_hash_of

from app.publishing.duplicates import DuplicateDetector, DuplicatePolicy, Embedder
from app.publishing.enums import InterruptionKind, PublishDecision
from app.publishing.history import PublishingHistory
from app.publishing.models import (
    DuplicateReport,
    InterruptedAttempt,
    PublishPreview,
    PublishReport,
    PublishRequest,
    RecoveryReport,
)

__all__ = [
    "MAX_PUBLISHES_PER_RUN",
    "PublishingService",
    "state_for_result",
]

#: The hard invariant of the roadmap (``PLAN.md`` §2). Named here so the code
#: that depends on it says so, but **enforced by the database**:
#: ``ux_publish_intents_run`` allows exactly one ``publish_intents`` row per
#: run, so a second attempt in the same run is rejected by SQLite before any
#: request is built. This constant is documentation, not a check.
MAX_PUBLISHES_PER_RUN = 1

#: Signature of the one thing this service calls to publish. The real
#: implementation is :func:`~app.integrations.linkedin.publish_to_linkedin`;
#: tests substitute a fake, which is what keeps every test offline.
Transport = Callable[[str], PublicationResult]


def state_for_result(result: PublicationResult) -> PublishState:
    """Translate the integration's outcome into the publish state machine.

    The mapping is deliberately narrow, and it is the whole reason the two
    vocabularies exist separately:

    * a post id means ``PUBLISHED`` — nothing else does;
    * ``UNKNOWN`` means the request may have been received, so a post may
      exist and the state must say so;
    * anything else is a definitive ``FAILED``.

    A claimed success with no post id is treated as ``UNKNOWN`` rather than
    ``PUBLISHED``: the store would refuse to record it as a publication anyway
    (its CHECK constraint requires an id), and the honest reading of "accepted,
    but nothing to point at" is exactly the ambiguity the state exists for.
    """
    if result.outcome is PublicationOutcome.PUBLISHED:
        # An id is the only evidence of a post. "Accepted, but nothing to
        # point at" is the ambiguity this state exists for — never a success,
        # and not a failure either, since something may well have been sent.
        return (PublishState.PUBLISHED if result.post_id
                else PublishState.UNKNOWN_REQUIRES_REVIEW)
    if result.outcome is PublicationOutcome.UNKNOWN:
        return PublishState.UNKNOWN_REQUIRES_REVIEW
    return PublishState.FAILED


class PublishingService:
    """Publishes at most one post per run, and remembers everything it did."""

    def __init__(self, store: StateStore, *,
                 transport: Transport | None = None,
                 embedder: Embedder | None = None,
                 policy: DuplicatePolicy | None = None,
                 detector: DuplicateDetector | None = None) -> None:
        self._store = store
        self._transport = transport or partial(publish_to_linkedin, store=store)
        self._detector = detector or DuplicateDetector(
            store, embedder=embedder, policy=policy
        )
        self._history = PublishingHistory(store)

    @property
    def history(self) -> PublishingHistory:
        """The read-only history interface.

        The Agent is handed *this*, never the store: every question it has
        about the past is a method here, which is what keeps generated posts
        out of the knowledge base (§6.1).
        """
        return self._history

    @property
    def duplicates(self) -> DuplicateDetector:
        """The duplicate policy this service enforces."""
        return self._detector

    # -- publishing ---------------------------------------------------------

    def preview_publish(self, request: PublishRequest, run_id: str, *,
                        now: datetime | None = None) -> PublishPreview:
        """Assemble exactly what ``publish()`` would send, without sending it.

        Same duplicate verdict, same content bytes and hash, same evidence —
        computed read-only, so the final external payload can be inspected
        (target account aside, which is resolved live) before the side
        effect exists. Creates no intents, touches no network, records
        nothing. ``would_publish`` is False exactly when ``publish()``
        would refuse at the duplicate gate; credential and transport
        outcomes are inherently live and are therefore not previewed.
        """
        duplicate_report = self._detector.check(request, now=now)
        return PublishPreview(
            content=request.content,
            content_hash=content_hash_of(request.content),
            topic=request.topic,
            evidence=request.evidence,
            duplicates=duplicate_report,
        )

    def publish(self, request: PublishRequest, run_id: str, *,
                now: datetime | None = None) -> PublishReport:
        """Attempt one publication, and record what happened to it.

        Returns a report rather than raising for anything LinkedIn did, because
        a refusal, a failure and an ambiguity are all normal outcomes a
        workflow has to branch on. Store failures still raise: they are the one
        thing the caller cannot be allowed to continue past.
        """
        duplicate_report = self._detector.check(request, now=now)
        if duplicate_report.must_not_publish:
            return PublishReport(
                decision=PublishDecision.REFUSED,
                run_id=run_id,
                message=(
                    f"refused before any request was sent: "
                    f"{duplicate_report.refusal_message}"
                ),
                duplicates=duplicate_report,
            )

        # Write-ahead: the intent exists before a request can exist. The
        # database refuses a second intent for this run
        # (MAX_PUBLISHES_PER_RUN) and a second unresolved one for this content
        # — both before the call, which is the only moment at which a
        # duplicate can still be prevented rather than recorded.
        intent = self._store.create_publish_intent(
            run_id,
            request.content,
            topic=request.topic,
            angle=request.angle,
            project=request.project,
        )
        intent = self._store.mark_attempt_started(intent.intent_id)

        result = self._transport(request.content)

        return self._resolve(intent, result, request, duplicate_report)

    def _resolve(self, intent: PublishIntent, result: PublicationResult,
                 request: PublishRequest,
                 duplicate_report: DuplicateReport) -> PublishReport:
        """Record the outcome of an attempt that was actually sent."""
        state = state_for_result(result)
        publication: Publication = self._store.record_publication(
            intent.intent_id,
            state,
            linkedin_post_id=result.post_id if state is PublishState.PUBLISHED
            else None,
            evidence_refs=request.evidence,
            embedding=duplicate_report.candidate_embedding,
        )
        return PublishReport(
            decision=PublishDecision(state.value),
            run_id=intent.run_id,
            message=result.message,
            intent_id=intent.intent_id,
            publication=publication,
            result=result,
            duplicates=duplicate_report,
        )

    # -- recovery -----------------------------------------------------------

    def recover_run(self, run_id: str) -> RecoveryReport:
        """Resolve every intent of ``run_id`` that never reached an outcome.

        This is what a crashed run leaves behind, and the two cases are
        resolved in opposite directions on purpose:

        * ``attempt_started`` with no publication — the request may have been
          received, so the only honest record is
          ``unknown_requires_review``, which blocks the content and asks for a
          person. It is **never** retried: retrying is how a duplicate post
          happens, and there is no read-back to check first.
        * ``intent_created`` — the attempt never started, so no request left
          the machine and no post can exist. Recording ``failed`` says exactly
          that, and releases the words for a later run.

        Recovery is idempotent: intents it has already resolved are terminal
        and are not returned by the store's unresolved query.
        """
        attempts: list[InterruptedAttempt] = []
        for intent in self._store.list_unresolved_intents(run_id):
            if intent.state is PublishState.ATTEMPT_STARTED:
                kind = InterruptionKind.ATTEMPTED_UNKNOWN
                resolved_to = PublishState.UNKNOWN_REQUIRES_REVIEW
                reason = (
                    "the LinkedIn attempt started and no outcome was recorded; "
                    "a post may exist, so this requires human confirmation and "
                    "is never retried automatically"
                )
            else:
                kind = InterruptionKind.NEVER_ATTEMPTED
                resolved_to = PublishState.FAILED
                reason = (
                    "the intent was written but the attempt never started, so "
                    "no request reached LinkedIn and no post exists"
                )

            publication = self._store.record_publication(
                intent.intent_id, resolved_to
            )
            attempts.append(
                InterruptedAttempt(
                    intent_id=intent.intent_id,
                    run_id=intent.run_id,
                    kind=kind,
                    prior_state=intent.state,
                    resolved_to=resolved_to,
                    reason=reason,
                    publication_id=publication.publication_id,
                )
            )

        return RecoveryReport(run_id=run_id, attempts=tuple(attempts))
