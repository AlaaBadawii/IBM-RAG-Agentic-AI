"""Which stored chunks a retrieval is allowed to draw candidates from.

The collection holds two populations that were never meant to compete:

    the hand-written corpus     350 chunks
        ``data/…`` — one person's curated claims about their own work.
        ``category`` is the corpus's own section name (``certificates``,
        ``in_progress_projects``, ``writing_style``, …), which is what
        ``app/context/taxonomy.py`` classifies and ranks.

    the synchronized mirrors    5,337 chunks
        ``@source/<name>/…`` — raw files copied out of the user's
        repositories by Step 3's synchronizer. ``category`` is the *source
        name* (``quizey-v2``, ``ibm-genai-coursework``, …), because the file
        was never classified into the corpus's taxonomy.

They share one collection, and that is deliberate — but sharing a collection
is not the same as competing for the same candidate slots. At 94% of the
store, the mirrors win every general-purpose query simply by weight, and the
curated material a branding decision is supposed to rest on never reaches
fusion at all. Measured: the fixed production query put 12 certificates and
zero project documents in its candidate pools.

A scope is the fix, and it is a *filter*, not a re-ranking. Deprioritising
the mirrors would still let them occupy the candidate slots that
``HYBRID_CANDIDATES`` budgets; excluding them is what gives the curated
corpus the whole pool.

Two representations, one meaning
    :attr:`CorpusScope.predicate` is the authoritative test, and it reads the
    **source key** — ``is_source_key``, the same predicate
    :func:`app.context.builder._classify` uses to route a document to
    ``repository_evidence``. The source key settles the question on its own,
    so nothing else has to agree with it.

    :attr:`CorpusScope.where` is the same restriction expressed as a Chroma
    ``where`` clause, because Chroma can only filter on metadata and has no
    ``not startswith`` operator. It therefore has to name the ten curated
    categories explicitly — a *derived* statement of the predicate, and
    therefore one that can drift.
    ``tests/test_retrieval_scope.py`` asserts the two agree over every chunk
    in a store, so a corpus that ever classified a file otherwise fails a
    test rather than silently changing which documents a decision saw. On the
    live store the equivalence was measured directly: 350 of 350 curated
    chunks pass both, 0 of 5,337 mirrors pass either.
"""
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from app.context.taxonomy import EVIDENCE_SECTION_BY_CATEGORY, GUIDANCE_SECTIONS
from app.sync.namespace import is_source_key

__all__ = [
    "CURATED",
    "CURATED_CATEGORIES",
    "CorpusScope",
    "for_category",
    "is_curated_source",
]


CURATED_CATEGORIES: frozenset[str] = frozenset(
    (*EVIDENCE_SECTION_BY_CATEGORY, *GUIDANCE_SECTIONS)
)
"""Every ``category`` the hand-written corpus uses, and nothing else.

Derived from the taxonomy rather than spelled out here: these *are* the
section names, and a second list in this module would be a second taxonomy to
keep in step with the first.

``repository_evidence`` and ``unclassified`` are absent by construction —
both have ``category=None`` in :data:`app.context.taxonomy.EVIDENCE_SECTIONS`,
because neither is fed by a category. Their absence is what excludes the
mirrors.
"""


def is_curated_source(source: str) -> bool:
    """True when a stored key is hand-written corpus, not a synchronized mirror."""
    return not is_source_key(source)


def _is_curated(metadata: Mapping[str, Any] | None) -> bool:
    """The predicate over a chunk's metadata, which is all retrieval has."""
    return is_curated_source((metadata or {}).get("source", ""))


@dataclass(frozen=True)
class CorpusScope:
    """A restriction on where a retrieval may look.

    Held by a retriever rather than passed to each call, so that every
    strategy built on that retriever honours it and none can be forgotten.

    Attributes:
        name: recorded in diagnostics, so a result says which corpus it came
            from without the reader having to infer it from the hits.
        predicate: the authoritative test, over chunk metadata.
        where: the same restriction as a Chroma ``where`` clause, or ``None``
            for a scope that cannot be expressed as one.
    """

    name: str
    predicate: Callable[[Mapping[str, Any] | None], bool]
    where: dict | None

    def includes(self, metadata: Mapping[str, Any] | None) -> bool:
        """True when this chunk is inside the scope."""
        return self.predicate(metadata)


CURATED: CorpusScope = CorpusScope(
    name="curated",
    predicate=_is_curated,
    where={"category": {"$in": sorted(CURATED_CATEGORIES)}},
)
"""The hand-written ``data/`` corpus, and only that.

Chroma's ``$in`` needs a plain list, so the frozenset is sorted on the way
in: a ``where`` clause that changed order between runs would make two
otherwise identical retrievals report different diagnostics.
"""


def for_category(category: str) -> CorpusScope:
    """A scope holding one corpus category, and only that.

    The stratified branding retrieval (:mod:`app.retrieval.strata`) ranks each
    stratum on its own, so it needs to ask "what does this category's material
    look like, scored against the query" rather than "what wins overall". A
    narrower scope is how it asks that without a second scoring path: the same
    retrievers, the same fusion, a smaller corpus.

    Unlike :data:`CURATED`, this scope cannot drift between its two
    representations — an equality predicate and an ``$eq`` clause state
    literally the same thing, whereas the curated allow-list had to *enumerate*
    what a prefix test could say in one step.
    """
    return CorpusScope(
        name=f"category:{category}",
        predicate=lambda metadata: (metadata or {}).get("category") == category,
        where={"category": {"$eq": category}},
    )
