"""The shape of an assembled branding context (``PLAN.md`` Step 4).

The whole point of this module is that the answer to *"what do I know about
this topic?"* is a structure with named parts, and not a string. Generation,
verification (Step 9) and the agent (Step 10) all have to be able to ask
questions of it:

    Is there evidence at all?          -> context.evidence_status
    Where did this claim come from?    -> section.items[i].source / .chunk_id
    How strong is it?                  -> item.evidence_state, section order
    Is anything missing?               -> context.coverage / section.coverage
    Which of this is advice, not fact? -> context.guidance_sections

Nothing here computes. :mod:`app.context.builder` decides, and these types only
carry the result — so a test can construct one directly and a later step can
assert on it without invoking retrieval.

Nothing here copies the retrieval models either. A
:class:`~app.retrieval.models.RetrievedDocument` is what retrieval produced;
a :class:`ContextItem` is that document *placed* — in a section, with the
provenance a verifier needs and an ordering key that does not depend on the
order the retriever happened to return things in.
"""
from dataclasses import dataclass, field

from app.context.enums import EvidenceStatus, FreshnessState
from app.context.taxonomy import state_rank
from app.retrieval.models import RetrievedDocument

__all__ = [
    "ContextCoverage",
    "ContextItem",
    "ContextSection",
    "PersonalBrandingContext",
    "SectionCoverage",
    "SourceState",
    "SourceStateReport",
]


@dataclass(frozen=True)
class ContextItem:
    """One retrieved document, placed in a section with its provenance intact.

    Every field is carried through from the retrieval result rather than
    summarised from it. ``content`` is the chunk as stored — this layer does
    not rewrite, truncate, or merge it, because the moment it does, the
    generator is reading this layer's prose instead of the corpus's, and a
    verifier can no longer check a claim against the text it came from.
    """

    content: str
    source: str
    """The stored key: ``evidence/backend/fastapi.md`` for the corpus, or
    ``@source/<name>/<path>`` for a registered source. The identity a verifier
    or an audit resolves, so it is never rewritten or shortened here."""

    chunk_id: str
    """``<content_hash>:<chunk index>``. Stable across re-ingestion, which is
    what lets Step 6 record *which chunk* a post was grounded in and a later
    run detect that the chunk has since changed."""

    evidence_state: str | None
    """``VERIFIED``/``DOCUMENTED``/… when the document declared one, else
    ``None``. ``None`` is preserved as ``None`` — the extraction rules in
    ``app/ingestion/metadata.py`` leave the field unset rather than guessing,
    and inventing a value here would undo that."""

    category: str
    document_type: str | None
    metadata: dict
    """The document's Chroma metadata verbatim, so nothing a future step needs
    has to be predicted by this one."""

    strategy: str
    """Which retrieval strategy produced it. Not used for ordering — where a
    fact is placed must not depend on how it was found — but kept because a
    verification failure is much easier to diagnose with it."""

    rank: int
    """1-based rank within the retrieval result that produced it. Provenance,
    not an ordering key; see :meth:`ordering_key`."""

    score: float
    """Strategy-specific score. **Not comparable across strategies**
    (``app/retrieval/models.py``), and deliberately not used for ordering
    here, for that reason among others."""

    @property
    def ordering_key(self) -> tuple[int, str, str]:
        """The key this item sorts by *inside its section*.

        ``(evidence state strength, source, chunk id)`` — strongest evidence
        first, then a total order that is identical no matter what order the
        retriever returned the documents in.

        Why not ``rank`` or ``score``: both describe *this retrieval run*, not
        the evidence. Ordering by them would make the context a function of the
        strategy and the input order, so the same evidence retrieved two ways
        would assemble into two different contexts, and a test could only ever
        assert on one of them. ``source`` and ``chunk_id`` are properties of
        the document, which is what makes the ordering reproducible.
        """
        return (state_rank(self.evidence_state), self.source, self.chunk_id)

    @classmethod
    def from_document(cls, document: RetrievedDocument) -> "ContextItem":
        """Place one retrieval result document. Pure field mapping."""
        metadata = document.metadata or {}
        return cls(
            content=document.content,
            source=document.source,
            chunk_id=document.chunk_id,
            evidence_state=metadata.get("evidence_state"),
            category=metadata.get("category", ""),
            document_type=metadata.get("document_type"),
            metadata=metadata,
            strategy=document.strategy,
            rank=document.rank,
            score=document.score,
        )


@dataclass(frozen=True)
class SectionCoverage:
    """What one section holds. Reported for every section, empty ones included.

    An empty section is reported rather than omitted because its *absence* and
    its *emptiness* mean different things: a section that does not exist is a
    layer that forgot to have it, whereas a section with ``item_count == 0`` is
    a layer saying "I know this exists and there is nothing here". Only the
    second is usable by a generator deciding whether to write about a topic.
    """

    item_count: int
    evidence_states_present: frozenset[str]
    """The *declared* evidence states in this section, each once. A set, not a
    list: the question it answers is "which kinds of support are here", and a
    duplicated ``DOCUMENTED`` answers it no better than one."""

    unclassified_count: int
    """Items with no declared evidence state.

    Counted rather than folded into ``evidence_states_present`` as a sentinel
    such as ``"UNKNOWN"``, which would put a value in a set of corpus states
    that the corpus does not define — and a later step comparing that set
    against ``app.ingestion.metadata.EVIDENCE_STATES`` would be misled by it.
    """

    @property
    def is_empty(self) -> bool:
        """True when the section holds nothing. Derived, so it cannot disagree
        with ``item_count``."""
        return self.item_count == 0


@dataclass(frozen=True)
class ContextSection:
    """One named section: either evidence, or communication guidance."""

    name: str
    order: int
    """Position within its own list — hierarchy rank for an evidence section,
    fixed presentation position for a guidance section. The two lists are
    never sorted against each other, because a guidance section has no rank to
    sort by (see :mod:`app.context.taxonomy`)."""

    items: tuple[ContextItem, ...]
    coverage: SectionCoverage


@dataclass(frozen=True)
class SourceState:
    """What the operational store knows about one population's currency."""

    identity: str
    """The registered source name, or
    :data:`~app.context.taxonomy.CORPUS_IDENTITY` for the hand-written
    corpus."""

    tracked: bool
    """Whether synchronization owns this population. False for the corpus,
    which no checkpoint can ever describe."""

    state: FreshnessState
    last_synced_at: str | None = None
    last_revision: str | None = None
    last_attempt_at: str | None = None
    note: str = ""

    @property
    def synchronized(self) -> bool:
        """True when a successful sync has ever recorded a revision."""
        return self.last_synced_at is not None and self.last_revision is not None


@dataclass(frozen=True)
class SourceStateReport:
    """How current the evidence behind this context is, per source.

    Carries no timestamp of its own and never consults a clock. Every value
    here was written by a synchronization that actually happened, or is absent
    because none did.
    """

    sources: tuple[SourceState, ...] = ()

    @property
    def synchronized_sources(self) -> tuple[SourceState, ...]:
        return tuple(s for s in self.sources if s.state is FreshnessState.SYNCHRONIZED)

    @property
    def failed_sources(self) -> tuple[SourceState, ...]:
        return tuple(s for s in self.sources if s.state is FreshnessState.FAILED)

    @property
    def unknown_sources(self) -> tuple[SourceState, ...]:
        return tuple(s for s in self.sources if s.state is FreshnessState.UNKNOWN)

    @property
    def is_known(self) -> bool:
        """True when at least one source has an authoritative freshness record."""
        return bool(self.synchronized_sources or self.failed_sources)

    def for_identity(self, identity: str) -> SourceState | None:
        for source in self.sources:
            if source.identity == identity:
                return source
        return None


@dataclass(frozen=True)
class ContextCoverage:
    """Coverage across the whole context, evidence and guidance counted apart.

    ``evidence_item_count`` excludes guidance items deliberately. A total that
    included them would let a topic with nothing but a writing-style document
    look populated, which is the confusion ``PLAN.md`` Step 4 exists to
    prevent.
    """

    evidence_item_count: int
    guidance_item_count: int
    populated_sections: tuple[str, ...]
    empty_sections: tuple[str, ...]
    evidence_states_present: frozenset[str]
    unclassified_count: int

    @property
    def total_item_count(self) -> int:
        return self.evidence_item_count + self.guidance_item_count


@dataclass(frozen=True)
class PersonalBrandingContext:
    """Everything Step 4 assembles, in one auditable object.

    Assembled by :func:`app.context.builder.build_context`, which is the only
    supported way to produce one from retrieval output. The constructor is
    public because a later step's test may want to state a context directly,
    not because callers should build one by hand.

    **Evidence and guidance are separate fields, not separate labels.** This is
    the structural half of "positioning must never be read as proof": a
    generator given ``context.guidance_sections`` is looking at a field whose
    contents cannot be counted as support, whatever it does with them.
    """

    query: str
    strategy: str
    evidence_status: EvidenceStatus
    evidence_sections: tuple[ContextSection, ...]
    guidance_sections: tuple[ContextSection, ...]
    coverage: ContextCoverage
    source_state: SourceStateReport

    diagnostics: dict = field(default_factory=dict)
    """Carried over from the retrieval result, plus this layer's own reasoning.
    Never read by the assembly logic; present so a surprising context can be
    explained after the fact."""

    @property
    def is_insufficient(self) -> bool:
        """True when no evidence was assembled.

        The explicit form of the check every downstream step needs. Reading
        ``not self.evidence_items()`` works too, but only this reads as a
        *domain result* rather than as a container that happens to be empty.
        """
        return self.evidence_status is EvidenceStatus.INSUFFICIENT

    @property
    def all_sections(self) -> tuple[ContextSection, ...]:
        """Every section, evidence first. For iteration and audit."""
        return self.evidence_sections + self.guidance_sections

    def section(self, name: str) -> ContextSection:
        """One section by name.

        Raises:
            KeyError: no such section. Every section this layer defines is
                always present — empty if it holds nothing — so an unknown name
                is a programming error rather than a missing-data condition.
        """
        for candidate in self.all_sections:
            if candidate.name == name:
                return candidate
        raise KeyError(
            f"no section {name!r} in this context; have "
            f"{[s.name for s in self.all_sections]}"
        )

    def evidence_items(self) -> tuple[ContextItem, ...]:
        """Every evidence item, in section order then in-section order."""
        return tuple(item for s in self.evidence_sections for item in s.items)

    def guidance_items(self) -> tuple[ContextItem, ...]:
        """Every guidance item, in section order then in-section order."""
        return tuple(item for s in self.guidance_sections for item in s.items)
