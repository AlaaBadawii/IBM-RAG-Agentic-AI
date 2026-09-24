"""Value objects of the publishing service (``PLAN.md`` Step 6).

Same rule as every other model module in this repository: these carry a
decision or a record, never behaviour that touches the network or the store.
A test can build one directly, and a caller can hold one without triggering
anything.

Three groups live here:

* what goes in — :class:`PublishRequest`, and :func:`evidence_ref` for turning
  the context layer's provenance into the ``source path + content hash`` pair
  the store records;
* what the duplicate checks found — :class:`DuplicateFinding` /
  :class:`DuplicateReport`;
* what came out — :class:`PublishReport` for one attempt,
  :class:`PublicationSummary` and the usage rows for history,
  :class:`RecoveryReport` for an interrupted run.
"""
from dataclasses import dataclass, field
from typing import Any

from app.integrations.linkedin.models import PublicationResult
from app.state.enums import PublishState
from app.state.models import EvidenceRef, Publication, PublicationRecord

from app.publishing.enums import (
    DuplicateKind,
    InterruptionKind,
    PublishDecision,
)

__all__ = [
    "DuplicateFinding",
    "DuplicateReport",
    "EvidenceUsage",
    "InterruptedAttempt",
    "PublicationSummary",
    "PublishPreview",
    "PublishReport",
    "PublishRequest",
    "RecoveryReport",
    "UsageCount",
    "evidence_ref",
]


def evidence_ref(source_path: str, chunk_id: str) -> EvidenceRef:
    """Build an evidence reference from a context item's provenance.

    ``app/context`` identifies a document by ``<content_hash>:<chunk index>``
    (``ContextItem.chunk_id``); the store records the two parts separately, so
    that a later audit can ask "is this still the content the post was grounded
    in?" after the corpus has been resynchronized (Step 3).

    The hash is required, not optional. An evidence reference without one would
    record *that* a post cited something while making it impossible to tell
    later whether that something had changed — which is the one question the
    reference exists to answer.
    """
    source = (source_path or "").strip()
    if not source:
        raise ValueError("an evidence reference needs a source path")
    digest, _, _ = (chunk_id or "").partition(":")
    digest = digest.strip()
    if not digest:
        raise ValueError(
            f"evidence reference for {source!r} carries no content hash "
            f"(chunk id {chunk_id!r})"
        )
    return EvidenceRef(source_path=source, content_hash=digest)


@dataclass(frozen=True)
class PublishRequest:
    """One candidate post, offered to the publishing service.

    The service is handed a decision that has already been made — text, and
    the labels the caller wants recorded with it. It has no view on whether
    the post is good, grounded, or worth sending: that belongs to the Agent
    (Step 10) and the verification gates (Step 9).
    """

    content: str
    topic: str | None = None
    angle: str | None = None
    project: str | None = None
    evidence: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("a publish request needs non-empty content")
        for ref in self.evidence:
            if not ref.source_path.strip() or not ref.content_hash.strip():
                raise ValueError(
                    "every evidence reference must carry a source path and a "
                    f"content hash; got {ref!r}"
                )


@dataclass(frozen=True)
class PublishPreview:
    """Exactly what ``publish()`` would send, without sending it.

    Same duplicate verdict, same content bytes, same evidence — computed
    read-only so an operator (or a test) can inspect the final external
    payload before the side effect exists. ``would_publish`` is False
    exactly when ``publish()`` would refuse; nothing here creates intents,
    touches the network, or records anything.
    """

    content: str
    content_hash: str
    topic: str | None = None
    evidence: tuple = ()
    duplicates: Any = None

    @property
    def would_publish(self) -> bool:
        """True when the duplicate policy lets this through."""
        return self.duplicates is not None and not self.duplicates.must_not_publish


@dataclass(frozen=True)
class DuplicateFinding:
    """One reason the service refused to publish.

    ``kind`` says which check found it; the rest is what that check knows. The
    fields are optional because the three checks genuinely know different
    things: a similarity is only meaningful for a near duplicate, a use count
    only for overuse.
    """

    kind: DuplicateKind
    detail: str
    subject: str | None = None
    """What was repeated: a content hash, a topic, a project, an evidence path."""
    uses: int | None = None
    """How many stored publications already used it (overuse only)."""
    similarity: float | None = None
    """Cosine similarity against the closest published post (near only)."""
    publication_id: str | None = None
    intent_id: str | None = None

    def __str__(self) -> str:  # for messages that have to be read by a person
        return f"{self.kind.value}: {self.detail}"


@dataclass(frozen=True)
class DuplicateReport:
    """The result of all three duplicate checks over one candidate.

    ``unchecked`` gives the reasons a check the policy requires could not run —
    an embedder that failed, say. It is kept separate from ``findings`` because
    "nothing matched" and "nothing was compared" must never look the same to a
    caller deciding whether to publish, and it is why :attr:`must_not_publish`
    covers both.
    """

    findings: tuple[DuplicateFinding, ...] = ()
    compared_publications: int = 0
    """How many stored publications the near-duplicate check actually compared
    against. Zero with no ``unchecked`` entry means there was no history yet."""
    unchecked: tuple[str, ...] = ()
    candidate_embedding: bytes | None = field(default=None, repr=False)
    """The candidate's vector, packed for storage. Opaque to callers."""

    @property
    def blocked(self) -> bool:
        """True when a check found a duplicate or an overused reference."""
        return bool(self.findings)

    @property
    def must_not_publish(self) -> bool:
        """True when publishing would be unsafe or unverified.

        A check that could not run is not evidence of duplication, but it *is*
        the absence of the check the policy requires — and the failure this
        whole step exists to prevent is a repeated post, which cannot be
        undone. So it fails closed.
        """
        return self.blocked or bool(self.unchecked)

    @property
    def refusal_message(self) -> str:
        """A one-line explanation, or an empty string when nothing blocked."""
        parts = [str(finding) for finding in self.findings]
        parts += list(self.unchecked)
        return "; ".join(parts)


@dataclass(frozen=True)
class PublishReport:
    """The outcome of one call to the publishing service.

    Holds the durable ``publication`` when one was written, the integration's
    ``result`` when a request was actually sent, and the ``duplicates`` report
    when the request was refused before anything was written. Nothing here is
    inferred: a field is populated because that thing happened.
    """

    decision: PublishDecision
    run_id: str
    message: str
    intent_id: str | None = None
    publication: Publication | None = None
    result: PublicationResult | None = None
    duplicates: DuplicateReport | None = None

    @property
    def published(self) -> bool:
        return self.decision is PublishDecision.PUBLISHED

    @property
    def refused(self) -> bool:
        """True when nothing was written and no request was sent."""
        return self.decision is PublishDecision.REFUSED

    @property
    def requires_review(self) -> bool:
        """True when a post may exist and a person has to decide."""
        return self.decision is PublishDecision.UNKNOWN_REQUIRES_REVIEW

    @property
    def linkedin_post_id(self) -> str | None:
        return self.publication.linkedin_post_id if self.publication else None

    @property
    def requires_human_intervention(self) -> bool:
        """True when the decision cannot be resolved by another run.

        Either the outcome is ambiguous (a post may exist) or LinkedIn refused
        for a reason only re-authorization fixes.
        """
        if self.requires_review:
            return True
        return bool(self.result and self.result.requires_human_intervention)

    @property
    def expiry_warning(self) -> str | None:
        """The credential warning the integration carried back, if any."""
        return self.result.expiry_warning if self.result else None


@dataclass(frozen=True)
class PublicationSummary:
    """One publication, as publishing history.

    The published *text* is not here. History says what went out, when, where
    it landed, and what it was grounded in; handing generated prose back out
    of the history service is the feedback loop ``PLAN.md`` §6.1 exists to
    prevent.
    """

    publication_id: str
    run_id: str
    published_at: str
    content_hash: str
    linkedin_post_id: str | None = None
    topic: str | None = None
    angle: str | None = None
    project: str | None = None
    evidence: tuple[EvidenceRef, ...] = ()

    @classmethod
    def from_record(cls, record: PublicationRecord) -> "PublicationSummary":
        """Project a stored publication record into history."""
        return cls(
            publication_id=record.publication_id,
            run_id=record.run_id,
            published_at=record.recorded_at,
            content_hash=record.content_hash,
            linkedin_post_id=record.linkedin_post_id,
            topic=record.topic,
            angle=record.angle,
            project=record.project,
            evidence=tuple(record.evidence),
        )


@dataclass(frozen=True)
class UsageCount:
    """How often one topic or project has been published about.

    ``publication_ids`` is what makes the count attributable: every use can be
    traced to a stored publication, so no count here is an inference.
    """

    value: str
    uses: int
    last_used_at: str
    publication_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceUsage:
    """How often one piece of evidence has been cited by a published post.

    Identified by ``(source_path, content_hash)`` — never by path alone, since
    the same path holds different content after a resynchronization.
    """

    source_path: str
    content_hash: str
    uses: int
    last_used_at: str
    publication_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class InterruptedAttempt:
    """One unresolved intent found by recovery, and what was recorded for it."""

    intent_id: str
    run_id: str
    kind: InterruptionKind
    prior_state: PublishState
    resolved_to: PublishState
    reason: str
    publication_id: str | None = None

    @property
    def requires_review(self) -> bool:
        """True when a post may exist and only a person can confirm it."""
        return self.kind is InterruptionKind.ATTEMPTED_UNKNOWN


@dataclass(frozen=True)
class RecoveryReport:
    """What recovery did to a run's unresolved intents.

    Recovery never retries. It records what the durable state implies and hands
    the ambiguity to a person, because LinkedIn offers no read-back to resolve
    it with (``PLAN.md`` §5.1).
    """

    run_id: str
    attempts: tuple[InterruptedAttempt, ...] = ()

    @property
    def recovered(self) -> int:
        return len(self.attempts)

    @property
    def requires_review(self) -> tuple[InterruptedAttempt, ...]:
        return tuple(a for a in self.attempts if a.requires_review)

    @property
    def released(self) -> tuple[InterruptedAttempt, ...]:
        """Attempts that provably never reached LinkedIn, so their content is
        free to be used by a later run."""
        return tuple(a for a in self.attempts if not a.requires_review)

    @property
    def blocked(self) -> bool:
        return bool(self.requires_review)

    @property
    def message(self) -> str:
        if not self.attempts:
            return "no interrupted publish attempts to recover"
        review = len(self.requires_review)
        return (
            f"recovered {len(self.attempts)} interrupted publish attempt(s); "
            f"{review} may have reached LinkedIn and require human review"
        )
