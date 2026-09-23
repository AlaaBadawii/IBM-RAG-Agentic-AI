"""Category-stratified retrieval: the priority order, enforced.

``app/retrieval/strata.py`` replaces one similarity-ranked query over the
curated corpus with a composition that follows the corpus's own stated
priority order (``portfolio.md`` §5). These tests pin the properties that make
that a guarantee rather than a tendency:

* every tier is drawn before any lower-priority material is considered;
* a tier's *documents* survive one file's chunk fan-out;
* certificates can only appear from an otherwise unfilled budget;
* guidance is drawn outside the evidence budget and classified as guidance.

Everything runs on a synthetic corpus with the repository's fake embeddings —
no model download, no network.
"""
from collections import Counter

import pytest

from app.retrieval.strata import (
    CONTEXT_BUDGET,
    FILL_STRATA,
    GUIDANCE_STRATA,
    LAST_RESORT_STRATA,
    TIER_STRATA,
    stratified_retrieve,
)
from app.sync.namespace import source_key
from tests.conftest import FakeEmbeddings

#: The tokens the synthetic corpus and the query share. ``FakeEmbeddings``
#: scores cosine by shared *tokens* and BM25 by term overlap, so a document's
#: rank here is decided by how much of this phrase it contains — deterministic,
#: and enough to reproduce the shape of the real corpus without a model.
SHARED = "recent projects built shipped lessons"

QUERY = SHARED

TARGET = "in_progress_projects/personal_branding_agent.md"

#: The file that must not be allowed to eat its tier. Long enough to be split
#: into several chunks, every one of them a strong match.
_DOMINANT = "\n\n".join(
    f"## Phase {i}\n\n{SHARED}. The work behind phase {i} and what it took."
    for i in range(
        1, 25
    )
)


def _doc(title: str, body: str) -> str:
    return f"# {title}\n\n{body}\n"


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    """A corpus holding every category the strata name, plus a mirror."""
    from langchain_chroma import Chroma

    from app.ingestion.pipeline import run_ingestion

    data = tmp_path_factory.mktemp("strata_data")
    files = {
        # --- tier 1 -------------------------------------------------------
        "completed_projects/alpha.md": _doc(
            "Alpha", f"{SHARED}. A finished platform, documented."),
        "completed_projects/beta.md": _doc(
            "Beta", f"{SHARED}. A finished service, documented."),
        "completed_projects/gamma.md": _doc(
            "Gamma", f"{SHARED}. A finished tool, documented."),
        "completed_projects/delta.md": _doc(
            "Delta", "An unrelated note about scheduling."),
        # --- tier 2 -------------------------------------------------------
        TARGET: _doc(
            "Personal branding agent",
            f"{SHARED}. The system that decides what to say about the work."),
        "in_progress_projects/dominant.md": _DOMINANT,
        "in_progress_projects/gamma.md": _doc(
            "Gamma ongoing", f"{SHARED}. Still under construction."),
        "in_progress_projects/delta.md": _doc(
            "Delta ongoing", "Something else entirely, no overlap."),
        # --- tier 3 -------------------------------------------------------
        "stories_lessons/alpha.md": _doc(
            "Alpha lesson", f"{SHARED}. What it taught me."),
        "stories_lessons/beta.md": _doc(
            "Beta lesson", f"{SHARED}. What it taught me too."),
        "stories_lessons/gamma.md": _doc(
            "Gamma lesson", "A lesson with no shared terms."),
        # --- fill ---------------------------------------------------------
        "evidence/alpha.md": _doc("Evidence alpha", f"{SHARED}. Cited."),
        "evidence/beta.md": _doc("Evidence beta", f"{SHARED}. Also cited."),
        "audit/alpha.md": _doc("Audit alpha", f"{SHARED}. Reviewed."),
        "audit/beta.md": _doc("Audit beta", "A review with no shared terms."),
        "in_progress_courses/alpha.md": _doc(
            "Course alpha", f"{SHARED}. In progress."),
        "in_progress_courses/beta.md": _doc(
            "Course beta", "Coursework with no shared terms."),
        # --- last resort --------------------------------------------------
        "certificates/alpha.md": _doc(
            "Certificate alpha", f"{SHARED}. Awarded."),
        "certificates/beta.md": _doc(
            "Certificate beta", f"{SHARED}. Also awarded."),
        "certificates/gamma.md": _doc(
            "Certificate gamma", f"{SHARED}. Awarded as well."),
        # --- guidance -----------------------------------------------------
        "vision_goals/my_vision.md": _doc(
            "Vision", "Where this is going."),
        "public_positioning/portfolio.md": _doc(
            "Positioning", "How this is described publicly."),
        "writing_style/alaa_writing_style.md": _doc(
            "Style", "How this is written."),
    }
    for rel, text in files.items():
        path = data / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    store = Chroma(
        collection_name="strata_tests",
        embedding_function=FakeEmbeddings(),
        persist_directory=str(tmp_path_factory.mktemp("chroma_strata")),
    )
    run_ingestion(data_dir=data, embeddings=FakeEmbeddings(), store=store)

    # A mirror whose text matches the query better than anything in the
    # corpus. Its `category` is a source name, so no stratum can reach it.
    store.add_texts(
        texts=[f"{SHARED} {SHARED} {SHARED} mirrored repository file"],
        metadatas=[{
            "source": source_key("quizey-v2", "src/api/main.py"),
            "category": "quizey-v2",
            "document_type": "unknown",
        }],
        ids=["mirror:0"],
    )
    return store


@pytest.fixture(scope="module")
def result(store):
    """The production composition, at the production budget."""
    return stratified_retrieve(QUERY, vector_store=store)


def _documents(result):
    return result.diagnostics["documents"]


def _roles(result):
    return [d["role"] for d in _documents(result)]


def _categories(result):
    return [d["category"] for d in _documents(result)]


def _chunks_of(result, source):
    return [d for d in result.documents if d.source == source]


# ------------------------------------------------------------- fixture guard ---

def test_the_fixture_really_does_let_one_file_dominate(store):
    """Without this, the fan-out test below would pass for the wrong reason."""
    from app.retrieval.scope import for_category

    stored = store.get(include=["metadatas"])
    dominant = [
        cid for cid, meta in zip(stored["ids"], stored["metadatas"])
        if (meta or {}).get("source") == "in_progress_projects/dominant.md"
    ]
    assert len(dominant) >= 3, (
        "dominant.md must be split into several chunks, or it cannot crowd "
        "its tier and the test proves nothing"
    )
    assert for_category("in_progress_projects").includes(
        {"category": "in_progress_projects"})


# ---------------------------------------------------------------- tier order ---

def test_documents_are_drawn_tier_by_tier_in_priority_order(result):
    """Completed, then in-progress, then lessons — and never interleaved.

    This is the ordering itself, read off the composition rather than the
    similarity ranking: no lower-priority document may appear before a
    higher-priority tier has had its slots.
    """
    tier_roles = [r for r in _roles(result) if r == "tier"]
    tier_categories = [
        c for c, r in zip(_categories(result), _roles(result)) if r == "tier"
    ]

    assert tier_categories == [
        "completed_projects", "completed_projects", "completed_projects",
        "in_progress_projects", "in_progress_projects", "in_progress_projects",
        "stories_lessons", "stories_lessons", "stories_lessons",
    ], f"tier order was {tier_categories}"
    assert tier_roles == ["tier"] * 9
    # And the tiers come first in the result, before any fill.
    assert _roles(result)[:9] == ["tier"] * 9


def test_every_tier_is_represented_even_though_it_is_not_what_scores_best(result):
    """The point of the change: project categories appear at all."""
    sources = [d.source for d in result.documents]
    assert any(s.startswith("completed_projects/") for s in sources)
    assert any(s.startswith("in_progress_projects/") for s in sources)
    assert any(s.startswith("stories_lessons/") for s in sources)


def test_the_target_document_reaches_the_context(result):
    """The document the whole change exists to surface."""
    assert any(d.source == TARGET for d in result.documents), (
        "personal_branding_agent.md is absent from the composed result"
    )


# ------------------------------------------------------------------ fan-out ---

def test_one_document_cannot_crowd_out_its_tier(result, store):
    """A tier's diversity is a property of the tier, not of its longest file.

    ``dominant.md`` supplies most of its category's matching chunks. A raw
    top-N chunk pull would return it repeatedly and never reach the other
    documents; the document-level draw must still yield three distinct files.
    """
    in_progress = [
        d["source"] for d in _documents(result) if d["category"] == "in_progress_projects"
    ]

    assert len(set(in_progress)) == 3, (
        f"the tier collapsed to {sorted(set(in_progress))}"
    )
    assert "in_progress_projects/dominant.md" in in_progress, (
        "the guard is vacuous unless the dominant file is actually selected"
    )


def test_each_document_contributes_at_most_its_share_of_chunks(result):
    """Chunks ride along with a document; they never buy extra documents."""
    per_source = Counter(d.source for d in result.documents)
    for stratum in TIER_STRATA:
        for source, count in per_source.items():
            if source.startswith(f"{stratum.category}/"):
                assert count <= stratum.chunks_per_document, (
                    f"{source} contributed {count} chunks, above the "
                    f"{stratum.chunks_per_document} a document may carry"
                )


# ------------------------------------------------------------------- budget ---

def test_the_budget_counts_documents_not_chunks(result):
    """A two-chunk document costs one slot, not two."""
    evidence = result.diagnostics["evidence_documents"]
    assert evidence == CONTEXT_BUDGET
    assert result.diagnostics["budget_unit"] == "documents"
    assert result.diagnostics["evidence_chunks"] >= evidence


def test_a_smaller_budget_yields_proportionally_fewer_documents(store):
    small = stratified_retrieve(QUERY, vector_store=store, budget=3)
    assert small.diagnostics["evidence_documents"] == 3
    assert _categories(small) == ["completed_projects"] * 3


# --------------------------------------------------------------- last resort ---

def test_certificates_are_absent_while_the_budget_can_be_filled_otherwise(result):
    """At the production budget, project and supporting evidence fill it."""
    assert "certificates" not in _categories(result)
    assert not [d for d in result.documents if d.source.startswith("certificates/")]
    assert not [d for d in _documents(result) if d["role"] == "last_resort"]


def test_certificates_appear_only_as_the_last_resort(store):
    """An unfillable budget falls back to certificates — after everything else."""
    generous = stratified_retrieve(QUERY, vector_store=store, budget=30)
    roles = [r for r in _roles(generous) if r in ("tier", "fill", "last_resort")]

    assert "certificates" in _categories(generous), (
        "an unfillable budget must still be filled"
    )
    priority = {"tier": 0, "fill": 1, "last_resort": 2}
    sequence = [priority[r] for r in roles]
    assert sequence == sorted(sequence), (
        f"roles must not go backwards: {roles}"
    )
    assert "fill" in roles and "last_resort" in roles


def test_the_fill_strata_never_name_certificates():
    """The exclusion is structural, not a runtime check that could be skipped."""
    assert "certificates" not in {s.category for s in FILL_STRATA}
    assert "certificates" not in {s.category for s in TIER_STRATA}
    assert {s.category for s in LAST_RESORT_STRATA} == {"certificates"}


# ----------------------------------------------------------------- guidance ---

def test_guidance_is_drawn_outside_the_evidence_budget(result):
    categories = {s.category for s in GUIDANCE_STRATA}
    assert categories == {"vision_goals", "public_positioning", "writing_style"}

    guidance = [d for d in result.documents if (d.metadata or {}).get("category") in categories]
    assert {d.source for d in guidance} == {
        "vision_goals/my_vision.md",
        "public_positioning/portfolio.md",
        "writing_style/alaa_writing_style.md",
    }
    # Not charged to the evidence budget, and not counted as evidence.
    assert result.diagnostics["guidance_documents"] == 3
    assert result.diagnostics["evidence_documents"] == CONTEXT_BUDGET


# ------------------------------------------------------------- the two scopes ---

def test_no_mirror_can_be_reached_by_any_stratum(result):
    """Each stratum's scope is a category, and a mirror's is a source name."""
    assert not [d for d in result.documents if d.source.startswith("@source/")]


# --------------------------------------------------------------- the result ---

def test_the_composition_travels_in_diagnostics(result):
    """A reader can see why each document is present without re-deriving it."""
    assert result.strategy == "stratified"
    assert result.diagnostics["budget_used"] == len(_documents(result))
    assert "policy override" in result.diagnostics["ordering_basis"]
    for entry in _documents(result):
        assert set(entry) == {"rank", "source", "category", "role"}
    assert [d["rank"] for d in _documents(result)] == list(
        range(1, len(_documents(result)) + 1)
    )


def test_the_result_ranks_every_document_over_the_whole_composition(result):
    assert [d.rank for d in result.documents] == list(
        range(1, len(result.documents) + 1)
    )


def test_the_context_builder_reads_it_as_ordinary_retrieval(result, state_store):
    """Stratified output is a normal RetrievalResult, in the right sections."""
    from app.context import build_context
    from app.context.enums import EvidenceStatus

    context = build_context(result, store=state_store)

    populated = [s.name for s in context.evidence_sections if s.coverage.item_count]
    assert {"completed_projects", "in_progress_projects", "stories_lessons"} <= set(populated)
    assert "certificates" not in populated
    assert context.evidence_status is EvidenceStatus.SUFFICIENT

    guidance = {s.name for s in context.guidance_sections if s.coverage.item_count}
    assert guidance == {"vision_goals", "public_positioning", "writing_style"}
    # Guidance is never evidence, however it was retrieved.
    assert not [i for s in context.guidance_sections for i in s.items
                if i.category and i.category not in {
                    "vision_goals", "public_positioning", "writing_style"}]


def test_the_query_is_ranked_per_stratum_not_globally(store):
    """Sanity on the composition: the same query, asked of each category."""
    only_completed = stratified_retrieve(QUERY, vector_store=store, budget=3)
    assert {d["category"] for d in _documents(only_completed)} == {
        "completed_projects"
    }


def test_an_empty_corpus_yields_an_empty_result_rather_than_an_error(tmp_path):
    """Absence is an answer. The corpus here holds nothing at all."""
    from langchain_chroma import Chroma

    empty = Chroma(
        collection_name="strata_empty",
        embedding_function=FakeEmbeddings(),
        persist_directory=str(tmp_path / "chroma_empty"),
    )
    result = stratified_retrieve(QUERY, vector_store=empty)

    assert result.documents == []
    assert result.diagnostics["evidence_documents"] == 0
    assert result.diagnostics["guidance_documents"] == 0
