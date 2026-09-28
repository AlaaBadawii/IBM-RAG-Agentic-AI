"""The persistent content-opportunity backlog.

The live branding workflow discovers several topics worth posting about in
one assembled context but can only publish a bounded few per run. Without
this layer, every non-selected topic evaporates with the in-memory context
when the run ends. With it, each meaningful discovery becomes a durable row
with its own lifecycle, and a later run can publish an older queued
opportunity even when current retrieval no longer surfaces it.

Pipeline position (all of it orchestrated by ``app.workflows.branding``;
nothing here runs on its own)::

    persist_discoveries(store, context)   discovery → durable ``queued`` rows
    store.list_backlog()                  the actionable pool, oldest first
    store.claim_opportunities(run, limit) select ≤ MAX_PUBLISHES_PER_RUN
    build_opportunity_context(opportunity) reconstruct one claim's input
    ... the existing agent / publish path runs per claimed opportunity ...
    store.record_opportunity_decision()   why something did not publish yet
    store.finalize_opportunity()          published / rejected / review

Identity levels stay distinct, as Step 6 requires of publishing:

* opportunity identity — the ``fingerprint`` here (topic + evidence);
* generated-post identity — the content hash on the publish intent;
* published-post identity — the LinkedIn post id on the publication.

What this module never does: publish, verify, generate, notify, or touch
the M1–M5 tracked-work ledger (``developments`` / ``review_cursors``). That
ledger models per-development coverage; this backlog models per-opportunity
attention. They answer different questions and share only the store.
"""

from enum import Enum
from hashlib import sha256
from typing import Any, Sequence

from app.context.enums import EvidenceStatus
from app.context.models import (
    ContextCoverage,
    ContextItem,
    ContextSection,
    PersonalBrandingContext,
    SectionCoverage,
    SourceStateReport,
)
from app.context.taxonomy import state_rank
from app.logging_config import get_logger
from app.state.models import ContentOpportunity

__all__ = [
    "OpportunityDecision",
    "build_opportunity_context",
    "evidence_snapshot",
    "opportunity_fingerprint",
    "persist_discoveries",
]

logger = get_logger(__name__)


class OpportunityDecision(str, Enum):
    """Why an opportunity did or did not publish — the per-opportunity audit.

    Recorded on the row's ``last_decision`` (unconstrained TEXT, like the
    run-level ``no_publish_reason``: the vocabulary belongs to this layer,
    not to the store). ``QUEUED`` is the initial state, ``SELECTED`` marks a
    claim; every other value explains an outcome without relying on logs.
    """

    QUEUED = "queued"
    SELECTED = "selected"
    DEFERRED = "deferred"
    REJECTED = "rejected"
    VERIFICATION_FAILED = "verification_failed"
    DUPLICATE = "duplicate"
    PUBLISH_FAILED = "publish_failed"
    REQUIRES_REVIEW = "requires_review"
    PUBLISHED = "published"
    RECOVERED = "recovered"


def opportunity_fingerprint(topic: str,
                            evidence_identities: Sequence[tuple[str, str]],
                            project: str | None = None) -> str:
    """The stable identity of one opportunity.

    ``topic`` plus the sorted ``(source, content_hash)`` evidence pairs
    (plus the project when named): the same underlying opportunity
    rediscovered on a later run computes the same fingerprint, so
    persistence is idempotent. Materially different evidence — or a
    different topic over the same development — computes a different
    fingerprint and coexists as its own row, which is how one development
    yields several opportunities over time.

    A changed chunk has a new content hash by construction (chunk ids are
    ``<content_hash>:<index>``), so edited evidence correctly reads as a new
    opportunity rather than silently refreshing the old one.
    """
    parts = [(source.strip(), digest.strip())
             for source, digest in evidence_identities]
    canonical = "\n".join((
        topic.strip(),
        (project or "").strip(),
        *[f"{source}\x00{digest}" for source, digest in sorted(set(parts))],
    ))
    return sha256(canonical.encode("utf-8")).hexdigest()


def evidence_snapshot(item: Any) -> dict:
    """The reconstructable record of one evidence item.

    Everything the reasoning input needs later: provenance (source, chunk
    id, content hash), classification (evidence state, category, document
    type), and the chunk content itself. Labels (``E1``…) are deliberately
    *not* stored: they are positional within one run's prompt and are
    reassigned when the opportunity's context is rebuilt.
    """
    metadata = getattr(item, "metadata", None) or {}
    chunk_id = getattr(item, "chunk_id", "") or ""
    digest, _, _ = chunk_id.partition(":")
    return {
        "source": getattr(item, "source", "") or "",
        "chunk_id": chunk_id,
        "content_hash": (metadata.get("content_hash") or digest.strip()),
        "evidence_state": getattr(item, "evidence_state", None),
        "category": getattr(item, "category", "") or "",
        "document_type": getattr(item, "document_type", None),
        "content": getattr(item, "content", "") or "",
    }


def _section_items(context: Any) -> list[tuple[str, Any]]:
    """``(section_name, item)`` pairs for every evidence item, in order."""
    sections = getattr(context, "evidence_sections", None)
    if not sections:
        return []
    return [(section.name, item)
            for section in sections
            for item in (getattr(section, "items", None) or ())]


def persist_discoveries(store: Any, context: Any) -> list[ContentOpportunity]:
    """Persist every meaningful discovery of one assembled context.

    One row per non-empty evidence section (the same unit the reasoner is
    offered as a ``TopicCandidate``): transient or empty candidates are
    never persisted, because they cannot meaningfully become posts.
    Re-discovery is idempotent — the fingerprint UNIQUE constraint makes a
    repeat enqueue return the existing row without touching its lifecycle
    state, so persisting can never reset attempts, drop a claim, or revive
    a resolved opportunity.

    Defensive by design: anything that is not a real assembled context
    (no evidence sections) yields ``[]`` with no writes, so instrumented
    callers with stand-in contexts behave exactly as before.
    """
    pairs = _section_items(context)
    if not pairs:
        return []
    by_section: dict[str, list[Any]] = {}
    for name, item in pairs:
        by_section.setdefault(name, []).append(item)
    persisted: list[ContentOpportunity] = []
    for name, items in by_section.items():
        snapshots = [evidence_snapshot(item) for item in items]
        identities = [(snap["source"], snap["content_hash"])
                      for snap in snapshots
                      if snap["source"] and snap["content_hash"]]
        if not identities:
            # Provenance without a hash cannot be deduplicated or cited
            # later (``evidence_ref`` requires both); persisting it would
            # create a row that can never become a post.
            continue
        strength = min(state_rank(snap["evidence_state"])
                       for snap in snapshots)
        persisted.append(store.enqueue_opportunity(
            opportunity_fingerprint(name, identities),
            name,
            snapshots,
            evidence_strength=strength,
        ))
    if persisted:
        logger.info("Persisted %d content opportunitie(s) to the backlog",
                    len(persisted))
    return persisted


def build_opportunity_context(opportunity: ContentOpportunity
                              ) -> PersonalBrandingContext:
    """Reconstruct the reasoning input for one backlog opportunity.

    A single evidence section named by the opportunity's topic, holding the
    stored snapshot items in their stored order — the same shape
    ``topic_candidates`` offers the reasoner (one non-empty section), so the
    existing resolve/generate/verify contracts hold unchanged: the topic
    resolves, the labels re-derive positionally, and
    ``selected_evidence`` re-checks against this context. Guidance sections
    stay empty: positioning must never be read as proof, including here.

    This is why a queued opportunity remains actionable when current
    retrieval omits it — its input no longer depends on retrieval at all.
    """
    items = tuple(
        ContextItem(
            content=snap.get("content", ""),
            source=snap.get("source", ""),
            chunk_id=snap.get("chunk_id", ""),
            evidence_state=snap.get("evidence_state"),
            category=snap.get("category", ""),
            document_type=snap.get("document_type"),
            metadata={
                "content_hash": snap.get("content_hash", ""),
                "category": snap.get("category", ""),
            },
            strategy="backlog",
            rank=index + 1,
            score=0.0,
        )
        for index, snap in enumerate(opportunity.evidence)
    )
    states = frozenset(
        snap.get("evidence_state") for snap in opportunity.evidence
        if snap.get("evidence_state")
    )
    section = ContextSection(
        name=opportunity.topic,
        order=0,
        items=items,
        coverage=SectionCoverage(
            item_count=len(items),
            evidence_states_present=states,
            unclassified_count=sum(
                1 for snap in opportunity.evidence
                if not snap.get("evidence_state")
            ),
        ),
    )
    return PersonalBrandingContext(
        query=f"backlog opportunity {opportunity.topic}",
        strategy="backlog",
        evidence_status=(EvidenceStatus.SUFFICIENT if items
                         else EvidenceStatus.INSUFFICIENT),
        evidence_sections=(section,) if items else (),
        guidance_sections=(),
        coverage=ContextCoverage(
            evidence_item_count=len(items),
            guidance_item_count=0,
            populated_sections=(opportunity.topic,) if items else (),
            empty_sections=() if items else (opportunity.topic,),
            evidence_states_present=states,
            unclassified_count=section.coverage.unclassified_count,
        ),
        source_state=SourceStateReport(sources=()),
        diagnostics={
            "opportunity_id": opportunity.opportunity_id,
            "fingerprint": opportunity.fingerprint,
            "reconstructed_from": "content_opportunities",
        },
    )
