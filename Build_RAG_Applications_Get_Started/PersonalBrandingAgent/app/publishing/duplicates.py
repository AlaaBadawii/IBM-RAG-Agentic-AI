"""The three duplicate checks — deliberately three, not one.

``PLAN.md`` Step 6 requires three *distinct* forms, because they need three
different kinds of data and answer three different questions:

============================  =========================  ==========================
Check                         Data                       Question it answers
============================  =========================  ==========================
:func:`exact_duplicate`       content hash               "have these exact words
                                                         already been sent, or
                                                         might they have been?"
:func:`near_duplicates`       embeddings of recent       "is this a reworded
                              published posts            version of something I
                                                         just posted?"
:func:`overuse`               stored topic, project and  "have I already leaned on
                              evidence references        this topic, project or
                                                         piece of evidence?"
============================  =========================  ==========================

They are not merged into one similarity score. Text similarity cannot answer
*"have I overused this project?"* — two posts about the same project share
almost no words — and a hash equality check cannot tell you that a paragraph
was merely rephrased. A single blended score would be worse than either, and
would make a refusal impossible to explain.

:class:`DuplicateDetector` runs all three and returns one
:class:`~app.publishing.models.DuplicateReport`, which is the only place they
are combined — and even there they stay separate findings.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol, Sequence

from app.state.enums import PublishState
from app.state.models import (
    PublicationRecord,
    to_iso,
    utc_now,
)
from app.state.store import StateStore, content_hash_of

from app.publishing.enums import DuplicateKind
from app.publishing.models import DuplicateFinding, DuplicateReport, PublishRequest
from app.publishing.vectors import cosine_similarity, pack_embedding, unpack_embedding

__all__ = [
    "DEFAULT_COMPARISON_WINDOW",
    "DEFAULT_MAX_EVIDENCE_USES",
    "DEFAULT_MAX_PROJECT_USES",
    "DEFAULT_MAX_TOPIC_USES",
    "DEFAULT_NEAR_DUPLICATE_THRESHOLD",
    "DEFAULT_OVERUSE_WINDOW_DAYS",
    "DuplicateDetector",
    "DuplicatePolicy",
    "exact_duplicate",
    "near_duplicates",
    "overuse",
]

#: Cosine similarity at or above which two posts are treated as the same post
#: reworded. High on purpose: the cost of a false positive is a post that never
#: goes out (recoverable), the cost of a false negative is a public repetition
#: (not recoverable).
DEFAULT_NEAR_DUPLICATE_THRESHOLD = 0.90

#: How far back overuse counts look. Long enough to catch "the third post about
#: this project this fortnight", short enough that a topic revisited after a
#: month is not treated as repetitive.
DEFAULT_OVERUSE_WINDOW_DAYS = 14.0

#: How many times a topic, project or piece of evidence may appear in published
#: posts inside the window before the next one is refused.
DEFAULT_MAX_TOPIC_USES = 3
DEFAULT_MAX_PROJECT_USES = 3
DEFAULT_MAX_EVIDENCE_USES = 3

#: How many recent publications the near-duplicate check compares against. A
#: bound does not weaken the check: repetition is a property of *recent*
#: posts, and an unbounded scan would grow with the history forever.
DEFAULT_COMPARISON_WINDOW = 50


class Embedder(Protocol):
    """The one method the near-duplicate check needs from an embedding stack.

    Structural on purpose. The project's existing embedding objects
    (``langchain``-style, as used by ingestion and retrieval, and the fakes in
    ``tests/conftest.py``) already satisfy it, so this step adds no new
    abstraction over them and no new dependency.
    """

    def embed_query(self, text: str) -> list[float]:
        """Embed one piece of text."""


@dataclass(frozen=True)
class DuplicatePolicy:
    """The thresholds the three checks are applied with.

    Defaults live here rather than in ``app/config.py``, following
    ``StateStore``'s lock TTL: nothing outside this step consumes them yet, and
    a configuration key that only one caller reads is a key that drifts.
    """

    near_duplicate_threshold: float = DEFAULT_NEAR_DUPLICATE_THRESHOLD
    overuse_window_days: float = DEFAULT_OVERUSE_WINDOW_DAYS
    max_topic_uses: int = DEFAULT_MAX_TOPIC_USES
    max_project_uses: int = DEFAULT_MAX_PROJECT_USES
    max_evidence_uses: int = DEFAULT_MAX_EVIDENCE_USES
    comparison_window: int = DEFAULT_COMPARISON_WINDOW

    def __post_init__(self) -> None:
        if not 0.0 < self.near_duplicate_threshold <= 1.0:
            raise ValueError(
                "the near-duplicate threshold must be in (0, 1]; a threshold "
                "of 0 would refuse every post"
            )
        if self.overuse_window_days <= 0:
            raise ValueError("the overuse window must be a positive number of days")
        for name in ("max_topic_uses", "max_project_uses", "max_evidence_uses",
                     "comparison_window"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be at least 1")


def exact_duplicate(store: StateStore, content: str) -> DuplicateFinding | None:
    """Check 1 — the same text has already been sent, or might have been.

    Reads one row by content hash. A ``failed`` intent is not a duplicate: an
    attempt LinkedIn definitively rejected leaves the words free to be used
    again, which is the same rule the store's unique index enforces. Everything
    else — published, ambiguous, or merely written — is a refusal, because
    there is no way to prove the words never went out.
    """
    digest = content_hash_of(content)
    intent = store.find_intent_by_content_hash(digest)
    if intent is None:
        return None

    state = intent.state
    if state is PublishState.PUBLISHED:
        detail = (
            f"this exact text was already published (publication for intent "
            f"{intent.intent_id}); publishing it again would duplicate a post"
        )
    elif state is PublishState.UNKNOWN_REQUIRES_REVIEW:
        detail = (
            f"an earlier attempt at this exact text has an unresolved outcome "
            f"(intent {intent.intent_id}); a post may already exist"
        )
    else:
        detail = (
            f"this exact text already has an unresolved publish intent "
            f"(intent {intent.intent_id}, state {state.value})"
        )
    return DuplicateFinding(
        kind=DuplicateKind.EXACT,
        detail=detail,
        subject=digest,
        intent_id=intent.intent_id,
    )


def near_duplicates(candidate: Sequence[float],
                    records: Sequence[PublicationRecord], *,
                    threshold: float = DEFAULT_NEAR_DUPLICATE_THRESHOLD
                    ) -> list[DuplicateFinding]:
    """Check 2 — reworded versions of recently published posts.

    Compares the candidate's vector against the stored vector of every recent
    published post that has one. A post with no stored vector is skipped rather
    than embedded on the fly: the count of comparisons actually made is
    reported by the caller, so "found nothing" is never confused with
    "compared nothing".
    """
    findings: list[DuplicateFinding] = []
    for record in records:
        stored = unpack_embedding(record.embedding)
        if stored is None:
            continue
        similarity = cosine_similarity(candidate, stored)
        if similarity is None or similarity < threshold:
            continue
        findings.append(
            DuplicateFinding(
                kind=DuplicateKind.NEAR,
                detail=(
                    f"{similarity:.3f} similar to an already published post "
                    f"(publication {record.publication_id}); it reads as the "
                    f"same post reworded"
                ),
                subject=record.topic,
                similarity=similarity,
                publication_id=record.publication_id,
            )
        )
    return findings


def overuse(records: Sequence[PublicationRecord], request: PublishRequest, *,
            policy: DuplicatePolicy) -> list[DuplicateFinding]:
    """Check 3 — topics, projects and evidence that have been leaned on.

    Three counts over the same recent window, each from stored references:
    the topic and project recorded on the intents, and the
    ``(source path, content hash)`` references recorded with each publication.

    The evidence count is per reference, not per path: after a
    resynchronization the same path may hold different content, and reusing a
    *changed* source is not the repetition this check is about.
    """
    findings: list[DuplicateFinding] = []

    if request.topic:
        matching = [r for r in records if r.topic == request.topic]
        if len(matching) >= policy.max_topic_uses:
            findings.append(
                DuplicateFinding(
                    kind=DuplicateKind.TOPIC_OVERUSE,
                    detail=(
                        f"topic {request.topic!r} has already been published "
                        f"about {len(matching)} time(s) in the last "
                        f"{policy.overuse_window_days:g} days"
                    ),
                    subject=request.topic,
                    uses=len(matching),
                    publication_id=matching[0].publication_id,
                )
            )

    if request.project:
        matching = [r for r in records if r.project == request.project]
        if len(matching) >= policy.max_project_uses:
            findings.append(
                DuplicateFinding(
                    kind=DuplicateKind.PROJECT_OVERUSE,
                    detail=(
                        f"project {request.project!r} has already been the "
                        f"subject of {len(matching)} post(s) in the last "
                        f"{policy.overuse_window_days:g} days"
                    ),
                    subject=request.project,
                    uses=len(matching),
                    publication_id=matching[0].publication_id,
                )
            )

    for ref in request.evidence:
        matching = [r for r in records if ref in r.evidence]
        if len(matching) >= policy.max_evidence_uses:
            findings.append(
                DuplicateFinding(
                    kind=DuplicateKind.EVIDENCE_OVERUSE,
                    detail=(
                        f"evidence {ref.source_path!r} (content "
                        f"{ref.content_hash[:12]}…) has already grounded "
                        f"{len(matching)} published post(s) in the last "
                        f"{policy.overuse_window_days:g} days"
                    ),
                    subject=ref.source_path,
                    uses=len(matching),
                    publication_id=matching[0].publication_id,
                )
            )

    return findings


class DuplicateDetector:
    """Applies all three checks, in the order that costs least first.

    The exact check is a single indexed lookup and runs first; the near check
    costs one embedding call and runs only if the exact check passed; the
    overuse counts run over the same fetched window as the near check. A
    candidate that is refused never reaches an embedding call it did not need.

    An embedder is **optional**. With one configured, the near-duplicate check
    is part of the policy, and a failure to run it refuses the publish — the
    check the policy requires did not happen, and a repeated post cannot be
    undone. With no embedder configured, near-duplicate detection is simply not
    part of the policy and the report says so (``compared_publications`` is 0
    and the request is not refused for it); the caller that wants the check
    supplies an embedder.
    """

    def __init__(self, store: StateStore, *,
                 embedder: Embedder | None = None,
                 policy: DuplicatePolicy | None = None) -> None:
        self._store = store
        self._embedder = embedder
        self._policy = policy or DuplicatePolicy()

    @property
    def policy(self) -> DuplicatePolicy:
        return self._policy

    @property
    def can_detect_near_duplicates(self) -> bool:
        """True when an embedder was configured for this detector."""
        return self._embedder is not None

    def check(self, request: PublishRequest, *,
              now: datetime | None = None) -> DuplicateReport:
        """Run the three checks over one candidate. Reads only."""
        exact = exact_duplicate(self._store, request.content)
        if exact is not None:
            # Nothing else can change the answer, and no embedding call is
            # worth spending on a request that is already refused.
            return DuplicateReport(findings=(exact,))

        moment = now or utc_now()
        since = to_iso(moment - timedelta(days=self._policy.overuse_window_days))
        records = self._store.list_publication_records(
            since=since, outcome="published"
        )
        recent = records[: self._policy.comparison_window]

        findings = list(overuse(records, request, policy=self._policy))
        unchecked: list[str] = []
        candidate_vector: Sequence[float] | None = None
        compared = 0

        if self._embedder is not None:
            try:
                candidate_vector = self._embedder.embed_query(request.content)
            except Exception as exc:  # noqa: BLE001 - any failure to embed
                # The check the policy requires did not run. Refusing is the
                # only safe answer: the alternative is publishing without the
                # repetition guard, which is not recoverable.
                unchecked.append(
                    f"the near-duplicate check could not run "
                    f"({type(exc).__name__}: {exc})"
                )
            else:
                with_vectors = [r for r in recent if r.embedding is not None]
                compared = len(with_vectors)
                findings.extend(
                    near_duplicates(
                        candidate_vector, recent,
                        threshold=self._policy.near_duplicate_threshold,
                    )
                )

        packed = None
        if candidate_vector is not None:
            packed = pack_embedding(candidate_vector)

        return DuplicateReport(
            findings=tuple(findings),
            compared_publications=compared,
            unchecked=tuple(unchecked),
            candidate_embedding=packed,
        )
