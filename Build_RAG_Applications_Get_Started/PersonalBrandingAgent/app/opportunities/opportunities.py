"""Publishing opportunities: from tracked change to ranked choice (M3).

Conceptual pipeline this module owns::

    uncovered ledger developments (M1 seeds: what is still owed attention)
  + fresh meaningful/milestone M2 changes (what just happened)
      → opportunities (one per development, not per file)
      → deterministic ranking (priority, then kind, then stable keys)
      → select one
      → targeted evidence retrieval for it

What it never does: decide worthiness beyond ranking (M3 ranks, the
downstream pipeline still declines freely), invent projects or developments
(everything resolves to a configured work and a ledger or detected change),
override coverage (covered developments are filtered, never scored), or
touch publishing state beyond an explicit ``mark_development_published``
helper the publishing path does not call yet.

Volume never enters: no chunk, file, line, or repository counts appear in
the model, the ranking, or the retrieval scope. A 5-file project outranks a
2,000-file repository whenever its priority and kind say so.

Directed mode (a later milestone) converges here by construction: it will
build an opportunity directly instead of ranking for one, and everything
below — targeted retrieval, reasoning, generation, verification, policy —
is already opportunity-shaped.
"""
from dataclasses import dataclass
from typing import Any

from app.opportunities.changes import (
    ChangeClassification,
    SourceChange,
    detect_changes,
)

__all__ = [
    "KIND_WEIGHT",
    "PRIORITY_RANK",
    "Opportunity",
    "build_opportunities",
    "mark_development_published",
    "retrieve_for_opportunity",
    "select_opportunity",
]

#: Priority order, lowest sorts first. From configuration, never code.
PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}

#: Kind order within one priority, highest sorts first. Fresh detected
#: changes outrank long-standing seeded objectives at equal priority, so a
#: seed can never squat on attention while new work waits; a high-priority
#: seed (the Abu Prompt introduction) still outranks normal-priority
#: detections, which is how a product objective wins without a special case.
KIND_WEIGHT = {"milestone": 3, "meaningful": 2, "seeded": 1}

#: M2 classifications that may become opportunities. Anything else —
#: unreviewed ranges, unchanged or minor content — is never an opportunity,
#: however large the repository behind it.
ELIGIBLE_CLASSIFICATIONS = frozenset({
    ChangeClassification.MEANINGFUL_CHANGE,
    ChangeClassification.MILESTONE,
})


@dataclass(frozen=True)
class Opportunity:
    """One development worth considering for publishing.

    ``basis`` says where it came from: ``'seeded'`` (an uncovered ledger
    development) or ``'detected'`` (a fresh M2 change). ``categories`` are
    corpus categories bounding its evidence; ``sources`` are sync-source
    names, which double as mirror-chunk categories (see
    ``app.retrieval.scope``). ``reasons`` is the inspectable ranking trail:
    why considered, why it outranks alternatives, what evidences newness,
    why it is not covered.
    """

    work_id: str
    work_display: str
    key: str
    title: str
    basis: str
    priority: str
    kind_weight: int
    classification: ChangeClassification | None
    categories: frozenset
    sources: tuple[str, ...]
    reasons: tuple[str, ...]
    change: SourceChange | None = None
    evidence_sources: frozenset = frozenset()
    """Exact corpus source paths bounding this development's evidence.

    When non-empty, targeted retrieval is restricted to these paths and
    nothing else — a development narrower than its category (the Abu Prompt
    introduction inside ``in_progress_projects``) cannot be outvoted by
    sibling threads. Empty means category-level targeting as before.
    """
    editorial_intent: str = ""
    """Writer objective for this development, verbatim.

    Carried, never interpreted: the generation layer renders it unchanged
    as a writing constraint (the documented purpose of
    ``PublishingConstraints.notes``). Empty for developments without one,
    which behave exactly as before.
    """

    @property
    def rank_key(self) -> tuple:
        """Sort order: priority, then kind, then stable keys. Deterministic
        across runs for identical inputs — no timestamps, no counts."""
        return (
            PRIORITY_RANK[self.priority],
            -self.kind_weight,
            self.work_id,
            self.key,
        )


def build_opportunities(store: Any, entries: list[dict],
                        *, registry: Any = None) -> list[Opportunity]:
    """Rank every eligible opportunity across all enabled tracked work.

    Seeded uncovered ledger developments and fresh eligible M2 changes both
    enter; covered developments, unreviewed ranges, and NO_CHANGE/MINOR
    content never do. Returns best-first; empty means nothing is owed
    attention, which is a normal answer.
    """
    from app.sources.registry import load_registry

    active_registry = registry if registry is not None else load_registry()
    found: list[Opportunity] = []
    for entry in entries:
        if not entry.get("enabled", True):
            continue
        work_id = entry["id"]
        if store.get_tracked_work(work_id) is None:
            raise ValueError(
                f"tracked work {work_id!r} is configured but not seeded; "
                f"seed the baseline first"
            )
        priority = entry.get("branding_priority", "normal")
        display = entry.get("display_name", work_id)
        found.extend(_seeded_opportunities(store, entry, priority, display))
        found.extend(_detected_opportunities(
            store, entry, priority, display, active_registry))
    return sorted(found, key=lambda opportunity: opportunity.rank_key)


def select_opportunity(store: Any, entries: list[dict], *,
                       registry: Any = None) -> Opportunity | None:
    """The single best opportunity, or None when nothing is owed attention."""
    ranked = build_opportunities(store, entries, registry=registry)
    return ranked[0] if ranked else None


def mark_development_published(store: Any, work_id: str, development_key: str,
                               publication_id: str) -> None:
    """Link a development to its publication, marking it covered.

    Explicit and separate from reviewing, selecting, or publishing itself:
    the publishing path does not call this yet, so coverage today changes
    only when someone says so. Verifies the publication exists rather than
    duplicating publication state.
    """
    if store.get_publication(publication_id) is None:
        raise ValueError(
            f"unknown publication {publication_id!r}: refusing to cover "
            f"{development_key!r} of {work_id!r} against nothing"
        )
    store.set_development_covered(
        work_id, development_key, covered=True,
        coverage_kind="published", publication_id=publication_id,
    )


def retrieve_for_opportunity(opportunity: Opportunity, *,
                             vector_store: Any = None,
                             strategy: str = "hybrid",
                             top_k: int = 20):
    """Evidence for one opportunity, and only it.

    Development-specific when the opportunity names exact sources: the
    scope admits those paths and nothing else, so no sibling thread can
    substitute itself. Otherwise the scope is the opportunity's mirror
    namespaces plus its corpus categories. An empty result is a normal
    answer — downstream generation declines on no evidence rather than
    falling back to unrelated content. Same retrievers, same fusion.
    Returns a normal ``RetrievalResult`` the context builder consumes
    unchanged.
    """
    from app.retrieval.engine import RetrievalEngine
    from app.retrieval.scope import CorpusScope

    if opportunity.evidence_sources:
        paths = frozenset(opportunity.evidence_sources)
        scope = CorpusScope(
            name=f"opportunity:{opportunity.work_id}:{opportunity.key}",
            predicate=lambda metadata: (metadata or {}).get("source") in paths,
            where={"source": {"$in": sorted(paths)}},
        )
    else:
        categories = (frozenset(opportunity.categories)
                      | frozenset(opportunity.sources))
        scope = CorpusScope(
            name=f"opportunity:{opportunity.work_id}:{opportunity.key}",
            predicate=lambda metadata: (metadata or {}).get("category") in categories,
            where={"category": {"$in": sorted(categories)}},
        )
    engine = RetrievalEngine(store=vector_store, scope=scope)
    return engine.retrieve(
        f"{opportunity.title} {opportunity.work_display} recent work achievements",
        strategy=strategy,
        top_k=top_k,
    )


def _seeded_opportunities(store: Any, entry: dict, priority: str,
                          display: str) -> list[Opportunity]:
    """Uncovered ledger developments as opportunities."""
    found = []
    for development in store.list_developments(entry["id"], uncovered_only=True):
        configured = _configured_development(entry, development.development_key)
        categories = frozenset((configured or {}).get("corpus_categories", ()))
        exact = frozenset((configured or {}).get("evidence_sources", ()))
        found.append(Opportunity(
            work_id=entry["id"], work_display=display,
            key=development.development_key, title=development.display_name,
            basis="seeded", priority=priority,
            kind_weight=KIND_WEIGHT["seeded"], classification=None,
            categories=categories,
            sources=tuple(entry.get("sources", ())),
            reasons=(
                f"uncovered development {development.development_key!r}",
                f"branding priority {priority}",
                "not covered by baseline or publication",
            )
            + (("evidence limited to "
                f"{len(exact)} configured source(s)",) if exact else ()),
            change=None,
            evidence_sources=exact,
            editorial_intent=((configured or {}).get("editorial_intent", "")
                              or ""),
        ))
    return found


def _detected_opportunities(store: Any, entry: dict, priority: str,
                            display: str,
                            registry: Any) -> list[Opportunity]:
    """Fresh eligible M2 changes, grouped one opportunity per source.

    One source's admitted changes are one development candidate: the files
    of a commit range describe one unit of work unless a human ledger says
    otherwise. Grouping is by (work, source), never by file count.
    """
    changeset = detect_changes(store, entry["id"], registry=registry)
    found = []
    for change in changeset.changes:
        if (change.unreviewed
                or change.classification not in ELIGIBLE_CLASSIFICATIONS):
            continue
        weight = KIND_WEIGHT[
            "milestone"
            if change.classification is ChangeClassification.MILESTONE
            else "meaningful"
        ]
        found.append(Opportunity(
            work_id=entry["id"], work_display=display,
            key=f"change:{change.source_name}:{change.after_revision[:12]}",
            title=f"{display} recent {change.source_name} work",
            basis="detected", priority=priority,
            kind_weight=weight, classification=change.classification,
            categories=frozenset(),
            sources=(change.source_name,),
            reasons=(
                f"{change.classification.value} change "
                f"{change.before_revision}..{change.after_revision}",
                f"{len(change.paths)} admitted path(s): "
                + ", ".join(sorted(p.path for p in change.paths)[:5]),
                f"branding priority {priority}",
                "new since the branding review cursor",
            ),
            change=change,
        ))
    return found


def _configured_development(entry: dict, key: str) -> dict | None:
    """The config block for one ledger development, if it has one."""
    for development in entry.get("developments", ()):
        if development.get("key") == key:
            return development
    return None
