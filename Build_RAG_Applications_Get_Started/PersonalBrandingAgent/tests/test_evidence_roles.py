"""Narrative vs catalog evidence roles, pinned to the incident's own chunks.

``app/context/evidence_roles.py`` exists because retrieval ranks chunks and
this corpus puts a metadata footer — ``## Evidence`` paths, ``## Content
Potential``, ``Story strength`` — at the end of every story. The footer repeats
the document's vocabulary, so it scores highest and a budgeted pull can hand
downstream layers an index card instead of the story.

The three chunk texts below are the real chunks of
``stories_lessons/ci_failures_are_environment_not_code.md`` that the incident
persisted as opportunity evidence. They are reproduced verbatim (trimmed) so a
regression in the classifier fails against the bytes that actually caused it.
"""
from app.context.evidence_roles import (
    EvidenceRole,
    classify_chunk,
    has_narrative,
    is_catalog_only,
    selection_priority,
)

CHUNK_0 = """# Most CI Failures Are Environment, Not Code

## Type

Debugging

## Context

A tiny Flask app used to practice CI with **Jenkins** and **GitHub Actions**.
The app and its tests were trivial; the pipeline kept failing anyway.

## Problem

The pipeline was red even though `pytest` passed locally.

## What I Did

Worked through the git history committing fix after fix.

## Decision / Insight
"""

CHUNK_1 = """## Decision / Insight

When CI is red, check **cwd, PATH, PYTHONPATH, and the environment** before
suspecting the app logic.

## Result

The pipeline turned green after aligning the invocation with how the imports
were written.

## Engineering Lesson

A failing pipeline is usually a signal about the environment, not the
correctness of the code.

## Why This Matters

Reliability and debugging judgment are core to the backend engineer Alaa wants
to become.

## Evidence
"""

CHUNK_2 = """## Evidence

- `/home/alaabadawii/DevOps/jenkins-practice/Jenkinsfile`
- `git log` inside `/home/alaabadawii/DevOps/jenkins-practice/`

## Content Potential

- Debugging story ("when CI is red, check the environment first")
- Short lesson on `python -m pytest` vs `pytest`

Story strength:
STRONG

Reason:
Concrete event, first-hand action, and an evidence trail in git history.
"""


# ------------------------------------------------------- the incident chunks ---

def test_the_metadata_tail_is_catalog_only():
    """The chunk the incident persisted and then could not write from."""
    assert classify_chunk(CHUNK_2) is EvidenceRole.CATALOG
    assert is_catalog_only(CHUNK_2)
    assert not has_narrative(CHUNK_2)


def test_the_story_chunk_carries_narrative():
    """The chunk that should have travelled instead."""
    role = classify_chunk(CHUNK_1)
    assert role in (EvidenceRole.NARRATIVE, EvidenceRole.MIXED)
    assert has_narrative(CHUNK_1)
    assert not is_catalog_only(CHUNK_1)


def test_the_opening_chunk_is_narrative():
    assert classify_chunk(CHUNK_0).carries_narrative
    assert not is_catalog_only(CHUNK_0)


# ------------------------------------------------------------ conservatism ---

def test_unrecognized_structure_is_unknown_never_catalog():
    """An unfamiliar document keeps its ranking; it is not demoted."""
    text = "# Some note\n\nJust prose with no recognized headings at all.\n"
    assert classify_chunk(text) is EvidenceRole.UNKNOWN
    assert not is_catalog_only(text)
    assert not has_narrative(text)


def test_a_bare_colon_does_not_make_a_heading():
    """Prose containing a colon is not structure."""
    text = "Here is what I learned: everything. And more: besides.\n"
    assert classify_chunk(text) is EvidenceRole.UNKNOWN


def test_empty_text_is_unknown():
    assert classify_chunk("") is EvidenceRole.UNKNOWN


# --------------------------------------------------------------- ordering ---

def test_selection_priority_orders_narrative_first():
    assert selection_priority(CHUNK_1) < selection_priority(CHUNK_2)
    assert selection_priority(CHUNK_0) < selection_priority(CHUNK_2)
    # An unknown chunk still outranks a pure index card.
    unknown = "no headings here at all"
    assert selection_priority(unknown) < selection_priority(CHUNK_2)


# --------------------------------------------------- document chunk selection ---

class _FakeStore:
    """A store that answers one ``content_hash`` query like Chroma does."""

    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def get(self, where=None, include=None):
        self.calls += 1
        return self.rows


def _document(chunk_id, content, *, source="stories_lessons/ci.md"):
    from app.retrieval.models import RetrievedDocument

    return RetrievedDocument(
        content=content,
        score=1.0,
        source=source,
        metadata={"content_hash": "hash-ci", "source": source},
        strategy="hybrid",
        chunk_id=chunk_id,
    )


def test_narrative_chunk_is_preferred_when_the_footer_scored_higher():
    """The incident shape: only the footer made the pool."""
    from app.retrieval.strata import _select_document_chunks

    pool = [
        _document("hash-ci:2", CHUNK_2),
        _document("hash-ci:2b", CHUNK_2),
    ]
    store = _FakeStore(rows={
        "ids": ["hash-ci:0", "hash-ci:1", "hash-ci:2"],
        "documents": [CHUNK_0, CHUNK_1, CHUNK_2],
        "metadatas": [{"content_hash": "hash-ci",
                       "source": "stories_lessons/ci.md"}] * 3,
    })

    selected = _select_document_chunks(store, pool, 2)

    assert store.calls == 1, "the document's siblings must be fetched once"
    assert {chunk.chunk_id for chunk in selected} == {"hash-ci:0", "hash-ci:1"}
    assert all(has_narrative(chunk) for chunk in selected)
    assert not any(is_catalog_only(chunk) for chunk in selected)


def test_no_sibling_fetch_when_the_pool_already_has_narrative():
    from app.retrieval.strata import _select_document_chunks

    pool = [_document("hash-ci:2", CHUNK_2), _document("hash-ci:1", CHUNK_1)]

    class _Exploding:
        def get(self, **kwargs):
            raise AssertionError("must not fetch when narrative is present")

    selected = _select_document_chunks(_Exploding(), pool, 2)

    assert [c.chunk_id for c in selected] == ["hash-ci:1", "hash-ci:2"]


def test_selection_never_exceeds_the_limit():
    from app.retrieval.strata import _select_document_chunks

    store = _FakeStore(rows={
        "ids": ["hash-ci:0", "hash-ci:1"],
        "documents": [CHUNK_0, CHUNK_1],
        "metadatas": [{"content_hash": "hash-ci",
                       "source": "stories_lessons/ci.md"}] * 2,
    })
    selected = _select_document_chunks(store, [_document("hash-ci:2", CHUNK_2)], 1)
    assert len(selected) == 1
    assert has_narrative(selected[0])


# ------------------------------------------------------- backlog does not freeze an index card ---

def test_persist_discoveries_drops_a_catalog_only_section(state_store):
    from types import SimpleNamespace

    from app.context.models import ContextItem
    from app.opportunities.backlog import persist_discoveries

    def item(chunk_id, content):
        return ContextItem(
            content=content,
            source="stories_lessons/ci.md",
            chunk_id=chunk_id,
            evidence_state=None,
            category="stories_lessons",
            document_type="lesson",
            metadata={"content_hash": "hash-ci",
                      "category": "stories_lessons"},
            strategy="hybrid",
            rank=1,
            score=0.0,
        )

    context = SimpleNamespace(evidence_sections=(
        SimpleNamespace(name="Story", items=(item("hash-ci:1", CHUNK_1),)),
        SimpleNamespace(name="Index", items=(item("hash-ci:2", CHUNK_2),)),
    ))

    persisted = persist_discoveries(state_store, context)

    assert [opportunity.topic for opportunity in persisted] == ["Story"]


# -------------------------------------------------- publishing candidacy ---

def _item(content, evidence_state=None, category="stories_lessons",
          chunk_id="hash-ci:0"):
    from app.context.models import ContextItem

    return ContextItem(
        content=content,
        source="data/stories_lessons/ci.md",
        chunk_id=chunk_id,
        evidence_state=evidence_state,
        category=category,
        document_type=None,
        metadata={"content_hash": "hash-ci", "category": category},
        strategy="vector",
        rank=1,
        score=0.0,
    )


def test_audit_and_unclassified_are_never_candidates():
    from app.context.evidence_roles import is_publishable_section

    assert not is_publishable_section("audit", [_item(CHUNK_1)])
    assert not is_publishable_section("unclassified", [_item(CHUNK_1)])
    assert is_publishable_section("stories_lessons", [_item(CHUNK_1)])


def test_an_empty_section_is_not_a_candidate():
    from app.context.evidence_roles import is_publishable_section

    assert not is_publishable_section("stories_lessons", [])


def test_a_thin_in_progress_course_is_not_a_candidate():
    from app.context.evidence_roles import is_publishable_section

    thin = _item("IBM RAG certificate — in progress, 24% complete.",
                 evidence_state=None, category="in_progress_courses")
    assert not is_publishable_section("in_progress_courses", [thin])
    in_progress = _item("IBM RAG certificate — in progress.",
                        evidence_state="IN_PROGRESS",
                        category="in_progress_courses")
    assert not is_publishable_section("in_progress_courses", [in_progress])


def test_a_substantive_course_is_a_candidate():
    from app.context.evidence_roles import is_publishable_section

    declared = _item("Completed the IBM multimodal course and built 3 apps.",
                     evidence_state="LEARNING", category="in_progress_courses")
    assert is_publishable_section("in_progress_courses", [declared])
    narrated = _item(CHUNK_1, evidence_state=None,
                     category="in_progress_courses")
    assert is_publishable_section("in_progress_courses", [narrated])


def test_topic_candidates_exclude_audit_and_thin_courses():
    from types import SimpleNamespace

    from app.agent.prompt import topic_candidates
    from app.context.models import SectionCoverage

    def section(name, item):
        return SimpleNamespace(
            name=name,
            items=(item,),
            coverage=SectionCoverage(
                item_count=1,
                evidence_states_present=frozenset(
                    {item.evidence_state} if item.evidence_state else set()),
                unclassified_count=0 if item.evidence_state else 1,
            ),
        )

    context = SimpleNamespace(evidence_sections=(
        section("audit", _item(CHUNK_1, category="audit")),
        section("in_progress_courses", _item(
            "in progress, 24%", category="in_progress_courses")),
        section("stories_lessons", _item(CHUNK_1)),
    ))

    assert [t.name for t in topic_candidates(context)] == ["stories_lessons"]


def test_persist_discoveries_drops_non_candidates(state_store):
    from types import SimpleNamespace

    from app.opportunities.backlog import persist_discoveries

    context = SimpleNamespace(evidence_sections=(
        SimpleNamespace(name="audit", items=(
            _item(CHUNK_1, category="audit"),)),
        SimpleNamespace(name="in_progress_courses", items=(
            _item("in progress, no labs", category="in_progress_courses"),)),
        SimpleNamespace(name="stories_lessons", items=(
            _item(CHUNK_1, chunk_id="hash-ci:1"),)),
    ))

    persisted = persist_discoveries(state_store, context)

    assert [o.topic for o in persisted] == ["stories_lessons"]
