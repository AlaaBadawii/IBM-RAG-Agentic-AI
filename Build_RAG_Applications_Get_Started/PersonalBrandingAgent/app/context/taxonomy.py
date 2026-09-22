"""Deriving sections and their strength from the corpus, not from taste.

Three orderings live here, and they answer three different questions:

    section       which part of *who the user is professionally* is this?
    section order when two sections both hold material, which is more credible?
    item order    within one section, which item is stronger?

Section names are the corpus's own ``category`` values. They are not invented
here and must not be renamed here: ``category`` comes from the file's path
(``app/ingestion/loader.py``) and is the one metadata field that is always
present, always derived, and never guessed. A section name that does not equal
a category would be a second taxonomy to keep in sync with the first.

The hierarchy below is transcribed from the corpus's own hierarchy documents,
which do not fully agree with each other. Where they disagree, the resolution
and its reason are recorded on the rank itself; the one real conflict — where
audit conclusions belong — is resolved in favour of ``data/audit/README.md``
and is written up in ``docs/architecture/rag-architecture.md``.
"""
from dataclasses import dataclass

__all__ = [
    "ALL_SECTIONS",
    "CORPUS_IDENTITY",
    "EVIDENCE_SECTIONS",
    "EVIDENCE_SECTION_BY_CATEGORY",
    "GUIDANCE_SECTIONS",
    "GUIDANCE_SECTION_BY_DOCUMENT_TYPE",
    "REPOSITORY_EVIDENCE_SECTION",
    "SECTION_ORDER",
    "STALE_STATE_RANK",
    "UNCLASSIFIED_SECTION",
    "UNCLASSIFIED_STATE_RANK",
    "EvidenceSection",
    "evidence_section_for",
    "guidance_section_for_document_type",
    "is_declared_state",
    "is_guidance_category",
    "section_rank",
    "state_rank",
]


# --------------------------------------------------------------- sections ---

REPOSITORY_EVIDENCE_SECTION = "repository_evidence"
"""The ``@source/<name>/…`` population: the user's actual repositories.

A single section rather than one per source. Twenty-nine sections would make
the context a directory listing, and the thing a generator needs to know is
*this is authored repository evidence* — which source it came from is on every
item, in ``ContextItem.source``.
"""

UNCLASSIFIED_SECTION = "unclassified"
"""Material the corpus's own categories do not recognise.

Permanent and normally empty. It exists so that an unrecognised ``category``
has somewhere honest to go: a retrieved document that simply vanishes during
assembly is evidence lost without a trace, which is the one failure this layer
must not have. It ranks last — provenance nothing can explain is the weakest
thing in the context, not the strongest.
"""

CORPUS_IDENTITY = "data"
"""How the hand-written corpus is named in the source-state report.

Not a registered source and not pretending to be one: ``data/`` is ingested by
the corpus pipeline, whereas ``sync_checkpoints`` tracks *registered sources*
only. The name is the directory's own.
"""


@dataclass(frozen=True)
class EvidenceSection:
    """One evidence-bearing section, and why it ranks where it does."""

    name: str
    category: str | None
    """The corpus ``category`` that feeds it, or ``None`` if it is not fed by
    a category (the repository-evidence population, and the catch-all)."""

    rank: int
    """Position in the evidence hierarchy. Lower is stronger; the numbering is
    dense and starts at 1 so a rank is also an index."""

    basis: str
    """The line in the corpus that establishes this rank.

    Present because the hierarchy is *the corpus's*, not this module's, and a
    reader must be able to check a rank against its source rather than trust
    it. Every string here names a real file and a real heading.
    """


#: Out of line because it is long, and because it is the one place the
#: corpus's documents contradict each other and the resolution needs its
#: reasoning visible next to the rank it produced.
_AUDIT_RANK_BASIS = (
    "data/audit/README.md §2, which lists the audit **last** of six sources of "
    "truth and states plainly that the audit 'must never become the source of "
    "truth for personal facts'. data/evidence/README.md ranks 'Audit "
    "conclusions' fourth, above portfolio and course material. The two "
    "disagree, so the resolution is made on the strength of the argument "
    "rather than on precedence: the audit is analysis *of* the KB, not a "
    "record of the user's work, and §13 of the same document forbids using it "
    "as a source of personal facts. Ranking it above the material it audits "
    "would let a summary outrank its own evidence, so it ranks last."
)


#: The evidence hierarchy, strongest first.
#:
#: Ranks 1 and 2 are the two populations' strongest material and the two
#: documents agree on them. Ranks 3–7 follow ``data/evidence/README.md`` where
#: it is finer-grained than ``data/audit/README.md`` (it ranks explicit project
#: documentation above course/certificate descriptions; the audit doc is silent
#: on their relative order, so the two do not conflict). Rank 8 is the one real
#: conflict — see :data:`_AUDIT_RANK_BASIS`.
EVIDENCE_SECTIONS: tuple[EvidenceSection, ...] = (
    EvidenceSection(
        name=REPOSITORY_EVIDENCE_SECTION,
        category=None,
        rank=1,
        basis=(
            "data/evidence/README.md §Evidence hierarchy 1, 'Current "
            "repository/source evidence'; data/audit/README.md §2.1, 'Actual "
            "project/source files and repository evidence'"
        ),
    ),
    EvidenceSection(
        name="evidence",
        category="evidence",
        rank=2,
        basis=(
            "data/audit/README.md §2.2, 'Evidence files under data/evidence/'; "
            "docs/architecture/rag-architecture.md §Evidence hierarchy 1, "
            "'Evidence files (data/evidence/)'"
        ),
    ),
    EvidenceSection(
        name="completed_projects",
        category="completed_projects",
        rank=3,
        basis=(
            "data/evidence/README.md §Evidence hierarchy 2, 'Explicit project "
            "documentation'; data/audit/README.md §2.3, 'Specific "
            "project/course/certificate records'"
        ),
    ),
    EvidenceSection(
        name="in_progress_projects",
        category="in_progress_projects",
        rank=4,
        basis=(
            "Same level as completed_projects, ranked below it because the "
            "evidence layer exists to 'distinguish demonstrated ability / "
            "documented experience / completed work from in-progress work' "
            "(data/evidence/README.md), and IN_PROGRESS is defined there as "
            "'work exists but is not complete'. The corpus keeps the two in "
            "separate categories, so this layer keeps them separate too."
        ),
    ),
    EvidenceSection(
        name="certificates",
        category="certificates",
        rank=5,
        basis=(
            "data/evidence/README.md §Evidence hierarchy 6, 'Course / "
            "certificate descriptions'; data/audit/README.md §2.3"
        ),
    ),
    EvidenceSection(
        name="in_progress_courses",
        category="in_progress_courses",
        rank=6,
        basis=(
            "Same level as certificates; ranked below it for the same reason "
            "in_progress_projects ranks below completed_projects."
        ),
    ),
    EvidenceSection(
        name="stories_lessons",
        category="stories_lessons",
        rank=7,
        basis=(
            "data/audit/README.md §2.4, 'Stories and lessons'; "
            "docs/architecture/rag-architecture.md §Evidence hierarchy 4"
        ),
    ),
    EvidenceSection(
        name="audit",
        category="audit",
        rank=8,
        basis=_AUDIT_RANK_BASIS,
    ),
    EvidenceSection(
        name=UNCLASSIFIED_SECTION,
        category=None,
        rank=9,
        basis=(
            "Not a rank the corpus states: no category, so no provenance this "
            "layer can explain. Weakest by construction, and normally empty."
        ),
    ),
)

SECTION_ORDER: tuple[str, ...] = tuple(s.name for s in EVIDENCE_SECTIONS)
"""Evidence sections in hierarchy order. Index is authoritative; the dense
``rank`` values are what make that true."""

EVIDENCE_SECTION_BY_CATEGORY: dict[str, str] = {
    section.category: section.name
    for section in EVIDENCE_SECTIONS
    if section.category is not None
}


# --------------------------------------------------------------- guidance ---

GUIDANCE_SECTIONS: tuple[str, ...] = (
    "vision_goals",
    "public_positioning",
    "writing_style",
)
"""Communication guidance. **Not evidence, and never ordered as if it were.**

Separate from the hierarchy above because they answer a different question:
*how should a supported fact be said*, not *is this fact supported*. A
generator that could read "preferred writing style" as "evidence that I built
X" is the specific failure ``PLAN.md`` Step 4 requires this layer to make
impossible, so the separation is structural — a different field on
:class:`~app.context.models.PersonalBrandingContext` — rather than a rule the
generator is asked to follow.

``vision_goals`` belongs here by the corpus's own instruction, not by
judgement: ``data/vision_goals/my_vision.md`` opens *"The Personal Branding
Agent must use this file for positioning decisions and must not infer goals
that are not documented here."*

The order is a fixed presentation order — what the user is aiming at, then how
they position themselves, then how they write. It carries **no** strength
claim: ranking guidance would assert a hierarchy the corpus never states.
"""

GUIDANCE_SECTION_BY_DOCUMENT_TYPE: dict[str, str] = {
    "vision": "vision_goals",
    "positioning": "public_positioning",
    "writing_style": "writing_style",
}
"""Secondary recognition path, from ``document_type``.

``document_type`` is itself derived from ``category``
(``app/ingestion/metadata.py``), so for the corpus today this agrees with the
category check and adds nothing. It is kept because it is the field that would
still be right if classification ever stopped being path-derived, and because
recognising guidance material is the one place a miss is dangerous: a
mislabelled positioning document would be counted as evidence.
"""


def is_guidance_category(category: str) -> bool:
    """True when a corpus category holds communication guidance, not evidence."""
    return category in GUIDANCE_SECTIONS


def guidance_section_for_document_type(document_type: str) -> str | None:
    """The guidance section a ``document_type`` implies, or ``None``."""
    return GUIDANCE_SECTION_BY_DOCUMENT_TYPE.get(document_type)


def evidence_section_for(category: str) -> str:
    """The evidence section a corpus category belongs to.

    An unrecognised category is not an error and is not dropped: it lands in
    :data:`UNCLASSIFIED_SECTION`, where it is visible and ranked last.
    """
    return EVIDENCE_SECTION_BY_CATEGORY.get(category, UNCLASSIFIED_SECTION)


def section_rank(section: str) -> int:
    """The hierarchy rank of an evidence section, or ``None`` if it is not one."""
    for candidate in EVIDENCE_SECTIONS:
        if candidate.name == section:
            return candidate.rank
    return -1


def section_rank(section: str) -> int:
    """The hierarchy rank of an evidence section, or ``-1`` if it is not one."""
    for candidate in EVIDENCE_SECTIONS:
        if candidate.name == section:
            return candidate.rank
    return -1


ALL_SECTIONS: tuple[str, ...] = SECTION_ORDER + GUIDANCE_SECTIONS


# ----------------------------------------------------------- item ordering ---

_EVIDENCE_STATE_ORDER: tuple[str, ...] = (
    "VERIFIED",
    "DOCUMENTED",
    "IN_PROGRESS",
    "LEARNING",
    "ASPIRATIONAL",
    "UNVERIFIED",
)
"""Evidence states, strongest first — the order of the table in
``data/evidence/README.md`` §Evidence states, which lists them from strongest
to weakest. ``STALE`` is deliberately absent; see below.

The two vocabularies are kept in step by ``tests/test_context.py``, which
asserts that this order plus ``STALE`` is exactly
``app.ingestion.metadata.EVIDENCE_STATES``. A state added to the corpus
tomorrow must not silently acquire a rank here.
"""

UNCLASSIFIED_STATE_RANK: int = len(_EVIDENCE_STATE_ORDER)
"""Where a document with no evidence state sorts: after every state the corpus
does declare, and before ``STALE``.

Weaker than a positive declaration, because the corpus said nothing about it —
``data/audit/README.md`` is explicit that *"A project file existing is not
automatically proof of every claim made about that project."* Stronger than
``STALE``, because ``STALE`` is the one state the corpus declares *no longer
valid*, and unknown is a better basis for caution than known-and-superseded.
"""

STALE_STATE_RANK: int = UNCLASSIFIED_STATE_RANK + 1

_STATE_RANKS: dict[str, int] = {state: i for i, state in enumerate(_EVIDENCE_STATE_ORDER)}
_STATE_RANKS["STALE"] = STALE_STATE_RANK


def state_rank(evidence_state: str | None) -> int:
    """Sort position of an evidence state within its section. Lower is stronger.

    Total: ``None``, an empty string, and any value outside the vocabulary all
    sort at :data:`UNCLASSIFIED_STATE_RANK`. A retrieval result must not be
    able to raise here, and an unrecognised state is not more trustworthy than
    a missing one.
    """
    if not evidence_state:
        return UNCLASSIFIED_STATE_RANK
    return _STATE_RANKS.get(evidence_state, UNCLASSIFIED_STATE_RANK)


def is_declared_state(evidence_state: str | None) -> bool:
    """True when this is a state the corpus actually declares.

    Membership of the vocabulary, which is a *different* question from
    :func:`state_rank` — ``STALE`` is declared and ranks last, so "declared"
    cannot be expressed as "ranks above unclassified". Both read the same
    ``_STATE_RANKS`` table, so a state cannot be declared here and unranked
    there.

    Used for coverage, where the question is "which kinds of support does this
    section actually name". A ``STALE`` item names one; an item with no state,
    or with a value the corpus does not define, does not.
    """
    return bool(evidence_state) and evidence_state in _STATE_RANKS
