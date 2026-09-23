"""Category-stratified retrieval for the branding context (``PLAN.md`` Step 4).

    stratified_retrieve(query)  ->  RetrievalResult  ->  build_context

**This ordering is a deliberate policy override of the similarity signal. It is
not a retrieval-quality fix.** Do not "correct" it by tuning similarity scores
back toward certificates. The evidence for that instruction is below, because
the next person to read this file will be looking at exactly the numbers that
seem to argue against it.

What it replaces, and why scoring could not be fixed instead
-----------------------------------------------------------
The branding context used to be one ``hybrid`` query over the whole curated
corpus (``app.retrieval.scope.CURATED``). Scoping the mirrors out was necessary
and is not in question — but it was not sufficient. Measured against the
350-chunk scoped corpus, with the production query, the top-5 came back as five
``certificates`` documents.

That is not a bug in fusion. It is what the corpus looks like when ranked by
similarity to the phrase *"recent professional work, projects, and achievements
worth sharing"*: certificates score high and cluster tightly (top 0.3451,
median 0.2586), while the project material scores lower and spreads wider
(``completed_projects`` top 0.2055, median 0.0986). Certificates' *median*
document outranks the best ``completed_projects`` document. No amount of query
wording changes that ordering, and the pool-size sweep made it worse rather
than better — raising ``HYBRID_CANDIDATES`` pushed the target's fused rank from
16 to 62 as the pool grew from 10 to 150, because RRF needs a document to rank
well in *both* strategies at once and the project material never does.

So the ordering is taken away from similarity and given to a stated priority.
The priority is the corpus's own, from ``data/public_positioning/portfolio.md``
§5: *"The strongest, evidence-backed narrative threads are the ones already
captured in ``completed_projects/``, ``in_progress_projects/``, and
``stories_lessons/``."* It also matches the evidence hierarchy the corpus
already encodes in ``app/context/taxonomy.py``, where project categories
outrank certificate categories.

What this module does *not* do
    It does not score anything. Every stratum is ranked by the existing
    retrievers, through the existing fusion, unmodified — the only difference
    is that each is asked a narrower question ("how does this category rank
    against the query?") via a per-category
    :class:`~app.retrieval.scope.CorpusScope`. This is a change in how the
    candidates are *composed*, not in how they are *scored*.

Document-level, not chunk-level
    A stratum draws **documents**, and only then chunks from those documents.
    A raw top-N chunk pull does not work here: ``quizey_v2.md`` holds 27 of
    ``in_progress_projects``' 56 chunks, and its eight highest-scoring chunks
    occupy over half of that category's fused pool. Pulling the top three
    chunks would return one file three times and never reach
    ``personal_branding_agent.md``, which sits at rank 3 of its category only
    after the fan-out is collapsed. Collapsing it first — best chunk per file,
    then that file's own strongest chunks — is what makes a tier's *diversity*
    a property of the tier rather than of whichever file is longest.

The budget counts documents, not chunks
    "Context budget" here means **documents**, because a document is the unit
    the tiers and the fill are specified in: three documents per tier, then
    whatever the budget has left. How many *chunks* ride along is a property of
    each document (:attr:`Stratum.chunks_per_document`), not a second budget to
    spend — charging for them would make a two-chunk document cost twice a
    one-chunk document and let a tier be truncated by its own formatting.
"""
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.config import HYBRID_CANDIDATES
from app.retrieval.engine import RetrievalEngine
from app.retrieval.models import RetrievalResult, RetrievedDocument
from app.retrieval.scope import for_category

__all__ = [
    "CONTEXT_BUDGET",
    "FILL_STRATA",
    "GUIDANCE_STRATA",
    "LAST_RESORT_STRATA",
    "Stratum",
    "TIER_STRATA",
    "stratified_retrieve",
]

#: How many *documents* the assembled context may hold. Guidance is counted
#: separately (see :data:`GUIDANCE_STRATA`).
#:
#: Twelve so the three tiers fit whole — three documents each, nine — and the
#: fill still gets three slots of its own. Chosen against the tier pull rather
#: than against the old top-k: the previous retrieval returned five *chunks*
#: from one ranking, where this spends its budget on diversity across three
#: tiers plus supporting evidence.
CONTEXT_BUDGET = 12

#: Role labels, recorded per document in ``diagnostics["documents"]`` so a
#: result says why each document is present without the reader re-deriving it.
TIER = "tier"
FILL = "fill"
LAST_RESORT = "last_resort"
GUIDANCE = "guidance"

#: The engine's fusion keeps at most ``HYBRID_CANDIDATES`` candidates per
#: strategy, so this is the whole fused list rather than a truncation of it.
_POOL = 2 * HYBRID_CANDIDATES


@dataclass(frozen=True)
class Stratum:
    """One category's claim on the context, and how much of it to draw.

    Attributes:
        category: the corpus ``category`` this stratum is drawn from.
        documents: how many distinct documents (files) to draw.
        chunks_per_document: how many of each drawn document's own strongest
            chunks to carry. More than one so an item is not judged on a
            fragment; low so one document cannot fill a tier.
        role: why this stratum is here — a tier, the fill, the last resort, or
            guidance. Recorded in diagnostics.
    """

    category: str
    documents: int
    chunks_per_document: int
    role: str

    def to_dict(self) -> dict[str, Any]:
        """The stratum as diagnostics record it."""
        return {
            "category": self.category,
            "documents": self.documents,
            "chunks_per_document": self.chunks_per_document,
            "role": self.role,
        }


TIER_STRATA: tuple[Stratum, ...] = (
    Stratum("completed_projects", documents=3, chunks_per_document=2, role=TIER),
    Stratum("in_progress_projects", documents=3, chunks_per_document=2, role=TIER),
    Stratum("stories_lessons", documents=3, chunks_per_document=2, role=TIER),
)
"""The tiers, in priority order, drawn before anything else.

Each tier is guaranteed its documents even when — *especially* when — the
similarity ranking would not have offered them. That guarantee is the whole
point: at rank 122 of 350, ``in_progress_projects/personal_branding_agent.md``
is invisible to a top-5 similarity query and reachable at rank 3 of its own
category.
"""

FILL_STRATA: tuple[Stratum, ...] = (
    Stratum("evidence", documents=CONTEXT_BUDGET, chunks_per_document=1, role=FILL),
    Stratum("audit", documents=CONTEXT_BUDGET, chunks_per_document=1, role=FILL),
    Stratum("in_progress_courses", documents=CONTEXT_BUDGET,
            chunks_per_document=1, role=FILL),
)
"""Remaining budget, from the corpus's supporting evidence.

``documents`` is a ceiling rather than a target — the shared budget decides how
many are actually carried, so each is set to the budget itself and the
shortfall does the limiting.

One chunk per document deliberately: the fill exists to widen the *number* of
things a decision can cite once the tiers have taken their slots, and taking
two chunks of one file would spend a slot on repetition.
"""

LAST_RESORT_STRATA: tuple[Stratum, ...] = (
    Stratum("certificates", documents=CONTEXT_BUDGET, chunks_per_document=1,
            role=LAST_RESORT),
)
"""Certificates, reachable only from an otherwise unfilled budget.

Not banned — a context that cannot be filled from project and supporting
evidence is better filled with something than left short, and the corpus does
document the certifications honestly. But certificates are the material that
already wins every similarity query, so leaving them in the fill would
reproduce the exact composition this module exists to change.
"""

GUIDANCE_STRATA: tuple[Stratum, ...] = (
    Stratum("vision_goals", documents=1, chunks_per_document=1, role=GUIDANCE),
    Stratum("public_positioning", documents=1, chunks_per_document=1, role=GUIDANCE),
    Stratum("writing_style", documents=1, chunks_per_document=1, role=GUIDANCE),
)
"""Communication guidance, drawn *outside* the evidence budget.

Kept separate for the reason ``app/context/builder.py`` keeps them separate:
these answer *how a supported fact should be said*, not *is this fact
supported*, and the budget above is a budget on evidence. They are retrieved
explicitly because the single similarity query no longer runs — without this,
the guidance sections would silently come back empty and a generator would
lose the user's stated positioning and style.
"""


def stratified_retrieve(
    query: str,
    *,
    vector_store: Any = None,
    budget: int = CONTEXT_BUDGET,
    strategy: str = "hybrid",
) -> RetrievalResult:
    """Compose one branding retrieval from the corpus's stated priority order.

    Args:
        query: the question each stratum is ranked against.
        vector_store: the Chroma store, injectable for tests. ``None`` opens
            the production store lazily, the convention every retriever here
            already follows. Not a
            :class:`~app.state.store.StateStore`, which is a different thing.
        budget: how many evidence *documents* the result may hold.
        strategy: the strategy each stratum is ranked with. ``hybrid`` in
            production; tests use cheaper ones.

    Returns:
        A :class:`~app.retrieval.models.RetrievalResult` shaped exactly like any
        other strategy's, so ``build_context`` consumes it unchanged. Its
        ``strategy`` reads ``"stratified"``; each document keeps whatever
        strategy ranked it inside its stratum. Every document carries ``rank``
        over the whole result, and the composition is in ``diagnostics``.

        A short corpus yields a short result rather than an error: a stratum
        that cannot fill its share contributes what exists, and the fill takes
        up the slack.
    """
    selection = _Selection()
    for stratum in TIER_STRATA:
        selection.admit(_documents_of(vector_store, query, stratum, strategy),
                        stratum.role, budget)

    if len(selection.sources) < budget:
        selection.admit(
            _fill_candidates(vector_store, query, FILL_STRATA, strategy),
            FILL, budget,
        )

    if len(selection.sources) < budget:
        selection.admit(
            _fill_candidates(vector_store, query, LAST_RESORT_STRATA, strategy),
            LAST_RESORT, budget,
        )

    evidence_documents = len(selection.sources)
    guidance = _guidance_documents(vector_store, query, strategy, selection.seen)

    ordered = selection.chunks + guidance
    for rank, document in enumerate(ordered, start=1):
        document.rank = rank

    return RetrievalResult(
        query=query,
        strategy="stratified",
        documents=ordered,
        diagnostics={
            "composition": selection.composition,
            "documents": selection.document_log,
            "evidence_documents": evidence_documents,
            "evidence_chunks": len(selection.chunks),
            "guidance_documents": len(guidance),
            "budget": budget,
            "budget_unit": "documents",
            "budget_used": evidence_documents,
            "strata": {
                "tiers": [s.to_dict() for s in TIER_STRATA],
                "fill": [s.to_dict() for s in FILL_STRATA],
                "last_resort": [s.to_dict() for s in LAST_RESORT_STRATA],
                "guidance": [s.to_dict() for s in GUIDANCE_STRATA],
            },
            "score_semantics": (
                "each stratum's own hybrid RRF rank; scores are comparable "
                "within a stratum only"
            ),
            "ordering_basis": (
                "portfolio.md §5 priority order — a deliberate policy override "
                "of the similarity signal, not a retrieval-quality measure"
            ),
        },
    )


# ------------------------------------------------------------- selection ---

@dataclass
class _Selection:
    """Accumulates the composed context and enforces the document budget.

    Kept as one object rather than four parallel lists threaded through every
    call, so the budget check and the dedup rule live in exactly one place —
    :meth:`admit` — and no stratum can bypass either.
    """

    chunks: list[RetrievedDocument] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    seen: set[str] = field(default_factory=set)
    composition: list[dict[str, Any]] = field(default_factory=list)
    document_log: list[dict[str, Any]] = field(default_factory=list)

    def admit(self, candidates: Iterable[RetrievedDocument], role: str,
              budget: int) -> None:
        """Take candidates until the document budget is full.

        A *new* source is what spends budget; further chunks of a document
        already admitted ride along with it. That is what keeps the tiers'
        guarantee independent of how a file happens to be chunked.

        A chunk with no ``chunk_id`` is never treated as a duplicate — the same
        rule ``app/context/builder.py`` uses, and for the same reason: an empty
        id is an absence of identity, not an identity shared by everything.
        """
        for document in candidates:
            if document.chunk_id and document.chunk_id in self.seen:
                continue
            is_new_document = document.source not in self.sources
            if is_new_document:
                if len(self.sources) >= budget:
                    return
                self.sources.append(document.source)
            if document.chunk_id:
                self.seen.add(document.chunk_id)
            self.chunks.append(document)
            self.composition.append({
                "rank": len(self.chunks),
                "source": document.source,
                "category": (document.metadata or {}).get("category") or "",
                "role": role,
            })
            if is_new_document:
                self.document_log.append({
                    "rank": len(self.sources),
                    "source": document.source,
                    "category": (document.metadata or {}).get("category") or "",
                    "role": role,
                })


# ------------------------------------------------------------- drawing ---

def _category_pool(vector_store, query: str, category: str,
                   strategy: str) -> list[RetrievedDocument]:
    """One category's chunks, in the engine's own rank order.

    The whole fused list, not a truncation of it: choosing documents from a
    truncated ranking would put the caller's ``top_k`` in charge of which
    *files* exist to choose from, which is the fan-out problem again in a
    different disguise.
    """
    engine = RetrievalEngine(store=vector_store, scope=for_category(category))
    return engine.retrieve(query, strategy=strategy, top_k=_POOL).documents


def _by_document(documents: Iterable[RetrievedDocument],
                 ) -> dict[str, list[RetrievedDocument]]:
    """Group ranked chunks by file, preserving first-seen order.

    The engine returns chunks best-first, so the first appearance of a source
    *is* that document's best chunk — which makes the group order a document
    ranking without a second scoring pass over anything.
    """
    grouped: dict[str, list[RetrievedDocument]] = {}
    for document in documents:
        grouped.setdefault(document.source, []).append(document)
    return grouped


def _documents_of(vector_store, query: str, stratum: Stratum,
                  strategy: str) -> list[RetrievedDocument]:
    """A stratum's documents, each with its own strongest chunks."""
    grouped = _by_document(_category_pool(vector_store, query, stratum.category,
                                          strategy))
    drawn: list[RetrievedDocument] = []
    for _source, chunks in list(grouped.items())[:stratum.documents]:
        drawn.extend(chunks[:stratum.chunks_per_document])
    return drawn


def _fill_candidates(vector_store, query: str, strata: tuple[Stratum, ...],
                     strategy: str) -> list[RetrievedDocument]:
    """Best chunk per document across the fill categories, best first.

    Ranked "by current ranking": each candidate carries the score its own
    stratum's fusion gave it, and the merged list is ordered by that score.
    Ties break on the stratum's position and then the source path, so the same
    corpus always composes the same context.
    """
    ranked: list[tuple[float, int, str, RetrievedDocument]] = []
    for position, stratum in enumerate(strata):
        grouped = _by_document(_category_pool(vector_store, query,
                                              stratum.category, strategy))
        for source, chunks in grouped.items():
            ranked.append((chunks[0].score, position, source, chunks[0]))
    ranked.sort(key=lambda entry: (-entry[0], entry[1], entry[2]))
    return [entry[3] for entry in ranked]


def _guidance_documents(vector_store, query: str, strategy: str,
                        seen: set[str]) -> list[RetrievedDocument]:
    """One document per guidance category, outside the evidence budget."""
    drawn: list[RetrievedDocument] = []
    for stratum in GUIDANCE_STRATA:
        for document in _documents_of(vector_store, query, stratum, strategy):
            if document.chunk_id:
                if document.chunk_id in seen:
                    continue
                seen.add(document.chunk_id)
            drawn.append(document)
    return drawn
