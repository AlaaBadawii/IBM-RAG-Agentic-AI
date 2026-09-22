"""Assembling retrieved material into a branding context (``PLAN.md`` Step 4).

    RetrievalResult  ->  PersonalBrandingContext  ->  generation · verification

The layer between retrieval and generation that makes *"I found supporting
evidence"* distinguishable from *"I found something vaguely related"*. It
groups retrieved documents into named sections, orders them by the evidence
hierarchy the corpus itself defines, reports what each section actually holds,
and says outright when there is no evidence.

What it is not
    Not a summarizer, not a fact database, not a second retriever, not a
    replacement for ``data/``, and not a generator. It calls no model and
    writes nothing down. ``data/`` keeps its authority; this layer assembles
    what retrieval found there and adds no facts of its own.

The two failure semantics, which are the whole reason this module is explicit
-------------------------------------------------------------------------
**No documents is a result.** A :class:`RetrievalResult` with no documents
produces a complete context whose sections all exist and are empty and whose
``evidence_status`` is ``INSUFFICIENT``. It never returns ``{}``, ``None``, or
an object whose emptiness has to be inferred from a list — a shape a caller
could read as success.

**A retrieval failure is not.** This module performs no retrieval and catches
nothing, so an exception raised while producing the result propagates through
the caller that composed the two. That is the point of leaving it uncaught:
converting an infrastructure failure into an evidence-free context would tell
a generator "there is nothing to say about this topic" when the truth is "the
system is broken", and the two must never be reachable from one another.

The same reasoning applies to the operational store. If it cannot be read, the
error propagates rather than the context reporting ``UNKNOWN`` freshness:
"we could not find out" and "there is no record" are different answers.
"""
from app.context.enums import EvidenceStatus, FreshnessState
from app.context.models import (
    ContextCoverage,
    ContextItem,
    ContextSection,
    PersonalBrandingContext,
    SectionCoverage,
    SourceState,
    SourceStateReport,
)
from app.context.taxonomy import (
    ALL_SECTIONS,
    CORPUS_IDENTITY,
    GUIDANCE_SECTIONS,
    REPOSITORY_EVIDENCE_SECTION,
    SECTION_ORDER,
    evidence_section_for,
    guidance_section_for_document_type,
    is_declared_state,
    is_guidance_category,
)
from app.retrieval.models import RetrievalResult
from app.state.enums import SyncOutcome
from app.state.models import SyncCheckpoint
from app.state.store import StateStore
from app.sync.namespace import is_source_key, source_name_from_key

__all__ = ["build_context"]


def build_context(result: RetrievalResult,
                  store: StateStore | None = None) -> PersonalBrandingContext:
    """Assemble one branding context from one retrieval result.

    Args:
        result: what a retrieval strategy returned. Consumed, never re-run —
            every item in the context is a document this result carried.
        store: the operational store the source-state report reads
            synchronization checkpoints from. Injectable so a test can point
            at a temporary store; when omitted, the production store is opened
            lazily on first use, the same convention as
            :class:`~app.retrieval.engine.RetrievalEngine`.

    Returns:
        A context in which every section Step 4 defines is present — empty ones
        included — and ``evidence_status`` states plainly whether anything
        was found.

    Raises:
        Exception: anything the retrieval that produced ``result`` raised has
            already propagated before this is reached; nothing here catches
            it. ``StateStoreError`` if the operational store cannot be read.
    """
    placed = _place(result.documents)
    grouped = _group(placed)

    evidence_sections = _sections(grouped, SECTION_ORDER)
    guidance_sections = _sections(grouped, GUIDANCE_SECTIONS)

    evidence_count = sum(s.coverage.item_count for s in evidence_sections)
    return PersonalBrandingContext(
        query=result.query,
        strategy=result.strategy,
        # Only evidence-bearing sections count. A result holding nothing but a
        # writing-style document is INSUFFICIENT, which is exactly the case
        # this distinction exists to catch.
        evidence_status=(
            EvidenceStatus.SUFFICIENT if evidence_count
            else EvidenceStatus.INSUFFICIENT
        ),
        evidence_sections=evidence_sections,
        guidance_sections=guidance_sections,
        coverage=_coverage(evidence_sections, guidance_sections),
        source_state=_source_state(result.documents, store),
        diagnostics={
            "retrieval_strategy": result.strategy,
            "documents_retrieved": len(result.documents),
            "documents_placed": len(placed),
            "duplicates_skipped": len(result.documents) - len(placed),
            "retrieval": dict(result.diagnostics or {}),
        },
    )


# ------------------------------------------------------------- placement ---

def _place(documents) -> list[tuple[str, ContextItem]]:
    """Pair every document with its section, dropping exact duplicates.

    Duplicates are recognised by ``chunk_id``, which
    ``app/retrieval/models.py`` documents as the stable id "used for dedup": a
    strategy that merges two lists (hybrid RRF) can return the same chunk
    twice, and a context that listed it twice would report coverage of two
    items for one piece of evidence.

    A document with no ``chunk_id`` is never treated as a duplicate of another
    — an empty id is an absence of identity, not an identity shared by
    everything.
    """
    placed: list[tuple[str, ContextItem]] = []
    seen: set[str] = set()
    for document in documents:
        chunk = document.chunk_id
        if chunk:
            if chunk in seen:
                continue
            seen.add(chunk)
        placed.append((_classify(document), ContextItem.from_document(document)))
    return placed


def _classify(document) -> str:
    """The section one retrieved document belongs to.

    Classification is by **metadata only** — ``category``, ``document_type``
    and the source key. There is deliberately no text matching on the content:
    "this paragraph sounds like a writing-style rule" is a guess, and the one
    thing this function must never get wrong is whether something is evidence.
    ``category`` is the reliable signal (path-derived, and the only metadata
    field that is always present), so it is checked before ``document_type``,
    which is itself derived from it.

    The source key is checked first and settles the question on its own: a
    ``@source/<name>/…`` key means authored repository evidence, whatever its
    other metadata happens to say.
    """
    if is_source_key(document.source):
        return REPOSITORY_EVIDENCE_SECTION

    metadata = document.metadata or {}
    category = metadata.get("category") or ""

    if is_guidance_category(category):
        return category

    document_type = metadata.get("document_type")
    if document_type:
        section = guidance_section_for_document_type(document_type)
        if section is not None:
            return section

    # A category the corpus does not know is not dropped: it lands in
    # `unclassified`, visibly and last. Silently discarding retrieved material
    # is the one outcome this layer must never produce.
    return evidence_section_for(category)


def _group(placed) -> dict[str, list[ContextItem]]:
    """Bucket items by section and put every bucket in its final order.

    Every section is created up front, so an empty one is a section that was
    assembled and found nothing — not one that failed to appear.
    """
    grouped: dict[str, list[ContextItem]] = {name: [] for name in ALL_SECTIONS}
    for section, item in placed:
        grouped[section].append(item)
    for items in grouped.values():
        items.sort(key=_item_order)
    return grouped


def _item_order(item: ContextItem) -> tuple[int, str, str]:
    """Sort key within a section; see :attr:`ContextItem.ordering_key`.

    Named here rather than inlined so the one place ordering is decided is
    greppable — this function is the entire answer to "is the ordering stable?"
    """
    return item.ordering_key


def _sections(grouped, names) -> tuple[ContextSection, ...]:
    """Build an ordered list of sections from a bucket map."""
    return tuple(
        ContextSection(
            name=name,
            order=order,
            items=tuple(grouped[name]),
            coverage=_section_coverage(grouped[name]),
        )
        for order, name in enumerate(names)
    )


def _section_coverage(items: list[ContextItem]) -> SectionCoverage:
    """Count one section. States are a set; undeclared ones are counted apart."""
    states = {
        item.evidence_state for item in items
        if is_declared_state(item.evidence_state)
    }
    return SectionCoverage(
        item_count=len(items),
        evidence_states_present=frozenset(states),
        unclassified_count=sum(
            1 for item in items if not is_declared_state(item.evidence_state)
        ),
    )


def _coverage(evidence: tuple[ContextSection, ...],
              guidance: tuple[ContextSection, ...]) -> ContextCoverage:
    """Summarise the whole context, evidence and guidance held apart."""
    every = evidence + guidance
    populated = tuple(s.name for s in every if not s.coverage.is_empty)
    empty = tuple(s.name for s in every if s.coverage.is_empty)
    evidence_items = [item for s in evidence for item in s.items]
    states = {
        item.evidence_state for item in evidence_items
        if is_declared_state(item.evidence_state)
    }
    return ContextCoverage(
        evidence_item_count=len(evidence_items),
        guidance_item_count=sum(s.coverage.item_count for s in guidance),
        populated_sections=populated,
        empty_sections=empty,
        evidence_states_present=frozenset(states),
        unclassified_count=sum(
            1 for item in evidence_items if not is_declared_state(item.evidence_state)
        ),
    )


# ---------------------------------------------------------- source state ---

def _source_state(documents, store: StateStore | None) -> SourceStateReport:
    """How current the evidence behind this context is.

    Read from ``sync_checkpoints`` — the one authoritative record of how far
    each registered source has been synchronized, and the single thing the
    repository already maintains for this purpose. Nothing here consults a
    clock, a file's mtime, or the retrieval itself: a freshness claim this
    layer fabricated would be worse than no claim, because a generator would
    act on it.
    """
    identities = _identities(documents)
    if not identities:
        return SourceStateReport()
    checkpoints = _checkpoints(store)
    return SourceStateReport(
        sources=tuple(_state_for(identity, checkpoints) for identity in identities)
    )


def _identities(documents) -> tuple[str, ...]:
    """Which populations this context draws on, sorted and de-duplicated.

    One identity per *source*, not per document: a context citing four files
    from one repository has one freshness, and repeating it four times would
    bury the fact that the other source in the same context has never been
    synchronized at all.
    """
    found: set[str] = set()
    for document in documents:
        if is_source_key(document.source):
            # A key with no source name in it is malformed rather than
            # corpus material; it keeps its own key as an identity instead of
            # being silently attributed to `data/`.
            found.add(source_name_from_key(document.source) or document.source)
        else:
            found.add(CORPUS_IDENTITY)
    return tuple(sorted(found))


def _checkpoints(store: StateStore | None) -> dict[str, SyncCheckpoint]:
    """Every checkpoint, keyed by source name.

    Raises:
        StateStoreError: the store is unavailable. Deliberately not caught and
            not degraded to "unknown freshness" — see the module docstring.
    """
    if store is not None:
        return {c.source_name: c for c in store.list_checkpoints()}
    with StateStore() as opened:
        return {c.source_name: c for c in opened.list_checkpoints()}


def _state_for(identity: str,
               checkpoints: dict[str, SyncCheckpoint]) -> SourceState:
    """One population's freshness, from its checkpoint and nothing else."""
    if identity == CORPUS_IDENTITY:
        # Not a weakness in the data, a boundary in the design: `data/` is
        # ingested by the corpus pipeline, and synchronization tracks
        # registered *sources*. No checkpoint for it can exist, now or later.
        return SourceState(
            identity=identity,
            tracked=False,
            state=FreshnessState.UNKNOWN,
            note=(
                "the hand-written data/ corpus is ingested by the corpus "
                "pipeline; synchronization tracks registered sources only, so "
                "no checkpoint describes it"
            ),
        )

    checkpoint = checkpoints.get(identity)
    if checkpoint is None:
        return SourceState(
            identity=identity,
            tracked=True,
            state=FreshnessState.UNKNOWN,
            note="no synchronization has recorded a checkpoint for this source",
        )

    succeeded = checkpoint.last_outcome is SyncOutcome.SUCCEEDED
    return SourceState(
        identity=identity,
        tracked=True,
        state=(
            FreshnessState.SYNCHRONIZED if succeeded else FreshnessState.FAILED
        ),
        # Reported even on failure: the content indexed by the last successful
        # pass is still indexed, so the revision is a real fact about this
        # source even though it is not the current one.
        last_synced_at=checkpoint.last_synced_at,
        last_revision=checkpoint.last_revision,
        last_attempt_at=checkpoint.last_attempt_at,
        note=(
            "last synchronization succeeded"
            if succeeded else
            "the most recent synchronization attempt failed; the revision "
            "reported is from the last successful pass, and nothing newer is "
            "indexed"
        ),
    )
