"""Narrative vs catalog evidence, decided from the chunk's own headings.

Retrieval ranks *chunks*, and a corpus document is chunked by size, not by
meaning. In this corpus a story or project file typically ends with a metadata
footer — an ``## Evidence`` list of paths, ``## Content Potential``,
``**Story strength:**`` and ``**Reason:**``. That footer repeats the
document's own vocabulary heavily, so it often scores *higher* than the prose
it summarises, and a budgeted pull that takes a document's top-ranked chunks
can hand the rest of the system a document's index card instead of its story.

The incident this module answers had exactly that shape: persisted opportunity
evidence was ``ci_failures_are_environment_not_code.md``'s tail chunk — the
path list and ``Story strength`` — and the writer, offered only metadata, had
nothing to say.

This module is the cheap, deterministic classification that lets the assembly
layers prefer a document's narrative chunks. It reads headings only: no model,
no score, no corpus knowledge beyond two small vocabularies. A chunk that
names no recognized heading is ``UNKNOWN`` — never ``CATALOG`` — so a document
whose structure this vocabulary does not know is treated exactly as before.

    classify_chunk(text)      -> EvidenceRole
    has_narrative(text)       -> bool
    is_catalog_only(text)     -> bool

Selection priority (see :func:`selection_priority`) is
``NARRATIVE < MIXED < UNKNOWN < CATALOG``: narrative first, catalog only when
nothing else from the document exists.
"""
import re
from enum import Enum

__all__ = [
    "CATALOG_HEADINGS",
    "COURSE_SECTION",
    "NARRATIVE_HEADINGS",
    "NON_CANDIDATE_SECTIONS",
    "SUBSTANTIVE_STATES",
    "EvidenceRole",
    "classify_chunk",
    "classify_item",
    "has_narrative",
    "is_catalog_only",
    "is_publishable_section",
    "selection_priority",
]


class EvidenceRole(str, Enum):
    """What a chunk mostly is: a story, an index card, both, or neither."""

    NARRATIVE = "narrative"
    """Carries at least one narrative heading and no catalog heading."""

    MIXED = "mixed"
    """Carries both narrative and catalog headings — e.g. a story chunk whose
    overlap reaches into the trailing ``## Evidence`` block."""

    CATALOG = "catalog"
    """Catalog headings only. An index card: provenance, potential, reasons."""

    UNKNOWN = "unknown"
    """No recognized heading. Deliberately not ``CATALOG`` — an unfamiliar
    document is left on its similarity ranking rather than demoted."""

    @property
    def carries_narrative(self) -> bool:
        """True for the two roles that can ground a written post."""
        return self in (EvidenceRole.NARRATIVE, EvidenceRole.MIXED)


#: Headings that introduce prose about the work itself — the story a post is
#: grounded in. Lower-cased, whitespace-collapsed, trailing punctuation
#: stripped before comparison (:func:`_normalize`).
NARRATIVE_HEADINGS = frozenset({
    "context",
    "background",
    "problem",
    "problem statement",
    "the problem",
    "challenge",
    "challenges",
    "what i did",
    "what i built",
    "what i changed",
    "what i tried",
    "what went wrong",
    "what i learned",
    "what i would do differently",
    "approach",
    "my approach",
    "design",
    "architecture",
    "implementation",
    "decision",
    "decisions",
    "key decisions",
    "technical decisions",
    "trade-offs",
    "tradeoffs",
    "solution",
    "the solution",
    "result",
    "results",
    "the result",
    "outcome",
    "outcomes",
    "impact",
    "lesson",
    "lessons",
    "engineering lesson",
    "engineering lessons",
    "learning",
    "learnings",
    "takeaway",
    "takeaways",
    "summary",
    "overview",
    "why this matters",
    "why it matters",
    "reflection",
    "hindsight",
    "diagnosis",
    "root cause",
    "the fix",
    "next steps",
},)

#: Headings that introduce the document's own catalogue: where its evidence
#: lives, how strong it is said to be, and what it might become. Useful for a
#: human, groundless for a post.
CATALOG_HEADINGS = frozenset({
    "evidence",
    "evidence index",
    "content potential",
    "story strength",
    "reason",
    "reasons",
    "references",
    "reference",
    "links",
    "link",
    "metadata",
    "files",
    "file",
    "paths",
    "path",
    "sources",
    "source",
    "source map",
    "tags",
    "hashtag",
    "hashtags",
    "keywords",
    "artifacts",
    "repository",
    "repo",
    "appendix",
    "citations",
    "citation",
    "related",
    "related work",
    "see also",
    "further reading",
    "assets",
    "attachments",
    "index",
    "project index",
},)


_MARKDOWN_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_BOLD_LABEL = re.compile(r"^\s*\*\*(.+?)\*\*\s*:?\s*(.*)$")
_BARE_LABEL = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 _\-]{1,40}):\s*(.*)$")


def _normalize(label: str) -> str:
    """Lower-case, strip markdown emphasis and trailing punctuation."""
    label = label.strip().strip("*_`").strip()
    label = label.rstrip(":").strip()
    return re.sub(r"\s+", " ", label).lower()


def _headings(text: str) -> list[str]:
    """Every heading-like label in one chunk, in order, normalized.

    Three shapes are recognized, because the corpus uses all three: markdown
    headings (``## Context``), bold labels (``**Story strength:**``) and bare
    ``Label:`` lines (``Reason: …``). A bare label is only accepted while it
    is short — at most four words — so ordinary prose that happens to contain
    a colon is not mistaken for structure.
    """
    labels: list[str] = []
    for line in text.splitlines():
        match = _MARKDOWN_HEADING.match(line)
        if match:
            raw = match.group(2)
        else:
            match = _BOLD_LABEL.match(line) or _BARE_LABEL.match(line)
            if not match:
                continue
            raw = match.group(1)
            if match.re is _BARE_LABEL and len(raw.split()) > 4:
                continue
        label = _normalize(raw)
        if label:
            labels.append(label)
    return labels


def classify_chunk(text: str) -> EvidenceRole:
    """Classify one chunk by the headings it carries.

    Conservative by construction: no recognized heading means ``UNKNOWN``,
    and only a chunk with catalog headings *and nothing else* is ``CATALOG``.
    """
    narrative = 0
    catalog = 0
    for label in _headings(text or ""):
        if label in NARRATIVE_HEADINGS:
            narrative += 1
        elif label in CATALOG_HEADINGS:
            catalog += 1

    if narrative and catalog:
        return EvidenceRole.MIXED
    if narrative:
        return EvidenceRole.NARRATIVE
    if catalog:
        return EvidenceRole.CATALOG
    return EvidenceRole.UNKNOWN


def classify_item(item) -> EvidenceRole:
    """Classify a retrieved document or context item (anything with
    ``content``), or a bare string."""
    if isinstance(item, str):
        return classify_chunk(item)
    return classify_chunk(getattr(item, "content", "") or "")


def has_narrative(item) -> bool:
    """True when the chunk can ground a post (NARRATIVE or MIXED)."""
    return classify_item(item).carries_narrative


def is_catalog_only(item) -> bool:
    """True only for a pure index card: catalog headings and no narrative."""
    return classify_item(item) is EvidenceRole.CATALOG


# ------------------------------------------------- publishability by section ---

#: Sections that are never LinkedIn publishing candidates. ``audit`` is the
#: corpus's own analysis *of* the knowledge base, which ``data/audit/README.md``
#: forbids using as a source of personal facts; ``unclassified`` has no
#: recognised provenance at all. Both remain available as context — they are
#: simply not something to publish *about*.
NON_CANDIDATE_SECTIONS = frozenset({"audit", "unclassified"})

#: The one section that is only sometimes publishable: a learning milestone is
#: worth a post when it is substantive (a completed course with real artifacts,
#: a declared learning record), not when it is a bare "in progress, 24%" line.
COURSE_SECTION = "in_progress_courses"

#: Evidence states that denote a *declared* achievement or learning record. An
#: item carrying one is substantive on its own; an item with none needs prose
#: (:func:`has_narrative`) to stand on.
SUBSTANTIVE_STATES = frozenset({
    "VERIFIED",
    "DOCUMENTED",
    "LEARNING",
    "ASPIRATIONAL",
})


def is_publishable_section(name: str, items) -> bool:
    """Whether a context section may become a publishing candidate.

    Derived from the corpus's own vocabulary, never from taste:

    * ``audit`` and ``unclassified`` are never candidates (policy:
      ``docs/operations/incident-generation-declined-2026-10-17.md`` §11.5);
    * ``in_progress_courses`` is a candidate only when at least one item is
      *substantive* — it declares an achievement state, or carries narrative
      prose. A course section with neither is the thin "in progress, no labs"
      shape the reasoner correctly declines;
    * every other section is a candidate, exactly as before.

    ``items`` may be anything :func:`has_narrative` accepts (a context item or
    a bare string); an item's ``evidence_state`` is read when present. An empty
    section is not publishable by definition — there is nothing to write from.
    """
    if name in NON_CANDIDATE_SECTIONS:
        return False
    material = list(items)
    if not material:
        return False
    if name != COURSE_SECTION:
        return True
    return any(_is_substantive(item) for item in material)


def _is_substantive(item) -> bool:
    """A declared achievement state, or prose a post can be grounded in."""
    state = getattr(item, "evidence_state", None)
    if isinstance(state, str) and state.upper() in SUBSTANTIVE_STATES:
        return True
    return has_narrative(item)


#: Lower sorts first when a document's own chunks are drawn. Narrative beats
#: mixed beats unknown beats catalog, so a document contributes its story
#: before its index card.
_PRIORITY = {
    EvidenceRole.NARRATIVE: 0,
    EvidenceRole.MIXED: 1,
    EvidenceRole.UNKNOWN: 2,
    EvidenceRole.CATALOG: 3,
}


def selection_priority(item) -> int:
    """The sort key that draws narrative chunks of a document first."""
    return _PRIORITY[classify_item(item)]
