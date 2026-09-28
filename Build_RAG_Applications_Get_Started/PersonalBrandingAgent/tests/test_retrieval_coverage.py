"""Coverage-aware retrieval ordering: novelty within a stratum.

``app/retrieval/strata.py`` composes the branding context from per-stratum
similarity rank with fixed document caps. That composition had no notion of
what the system already persisted — so a document that kept winning its
category kept its slot forever, and newly added material (e.g. the IBM
Multimodal certificate, builds, and lesson) never reached
``persist_discoveries`` no matter how substantive it was.

The fix is ordinal and local: within each evidence stratum, documents whose
source was never persisted as opportunity evidence sort ahead of covered
ones, stably. Same query, strata, budget, and exclusions; guidance never
takes the preference; an empty known-set is byte-identical to similarity
order. Nothing here names a topic — the mechanism keys on store coverage,
so it generalizes to any future certificate, project, or lesson.

Everything runs on a synthetic corpus with the repository's fake embeddings —
no model download, no network.
"""
from pathlib import Path

import pytest

from app.retrieval.strata import (
    CONTEXT_BUDGET,
    stratified_retrieve,
)
from app.state.store import StateStore
from tests.conftest import FakeEmbeddings

#: Generic production-shaped query terms. Shared by incumbents and newcomers
#: alike, so rank differences come from term *density*, not topic.
SHARED = "recent professional work projects achievements worth sharing"

QUERY = SHARED


def _doc(title: str, body: str) -> str:
    return f"# {title}\n\n{body}\n"


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    """Incumbents (dense query overlap) plus newcomers (sparser overlap,
    different vocabulary) in the same categories."""
    from langchain_chroma import Chroma

    from app.ingestion.pipeline import run_ingestion

    data = tmp_path_factory.mktemp("coverage_data")
    files = {
        # --- completed_projects: 3 incumbents crowd the 3-doc tier --------
        "completed_projects/alpha.md": _doc(
            "Alpha", f"{SHARED}. {SHARED}. A finished platform."),
        "completed_projects/beta.md": _doc(
            "Beta", f"{SHARED}. {SHARED}. A finished service."),
        "completed_projects/gamma.md": _doc(
            "Gamma", f"{SHARED}. {SHARED}. A finished tool."),
        "completed_projects/novel_build.md": _doc(
            "Novel build",
            f"{SHARED}. A newly added image captioning service with "
            f"provider abstraction and tests. {SHARED}."),
        "completed_projects/novel_app.md": _doc(
            "Novel app",
            f"{SHARED}. A newly added vision model web app. {SHARED}."),
        "completed_projects/novel_tool.md": _doc(
            "Novel tool",
            f"{SHARED}. A newly added developer tool with docs and tests. "
            f"{SHARED}."),
        # --- stories_lessons ---------------------------------------------
        "stories_lessons/alpha.md": _doc(
            "Alpha lesson", f"{SHARED}. {SHARED}. What it taught me."),
        "stories_lessons/beta.md": _doc(
            "Beta lesson", f"{SHARED}. {SHARED}. What it taught me too."),
        "stories_lessons/gamma.md": _doc(
            "Gamma lesson", f"{SHARED}. {SHARED}. Another lesson."),
        "stories_lessons/novel_lesson.md": _doc(
            "Novel lesson",
            "A newly added defensive-design lesson about untrusted model "
            "output. " + SHARED),
        # --- evidence fill ------------------------------------------------
        "evidence/alpha.md": _doc(
            "Evidence alpha", f"{SHARED}. {SHARED}. Cited."),
        "evidence/novel.md": _doc(
            "Novel evidence",
            "Newly added learning-versus-applied record. " + SHARED),
        # --- other fill categories ----------------------------------------
        "audit/alpha.md": _doc("Audit alpha", f"{SHARED}. Reviewed."),
        "in_progress_courses/alpha.md": _doc(
            "Course alpha", f"{SHARED}. In progress."),
        # --- in_progress_projects tier ------------------------------------
        "in_progress_projects/alpha.md": _doc(
            "Alpha ongoing", f"{SHARED}. {SHARED}. Under construction."),
        "in_progress_projects/beta.md": _doc(
            "Beta ongoing", f"{SHARED}. {SHARED}. Still building."),
        "in_progress_projects/gamma.md": _doc(
            "Gamma ongoing", f"{SHARED}. {SHARED}. Ongoing work."),
        # --- last resort ---------------------------------------------------
        "certificates/alpha.md": _doc(
            "Certificate alpha", f"{SHARED}. Awarded."),
        # --- irrelevant: no shared terms at all ----------------------------
        "completed_projects/offtopic.md": _doc(
            "Offtopic", "A note about office seating arrangements."),
        # --- guidance ------------------------------------------------------
        "vision_goals/my_vision.md": _doc("Vision", "Where this is going."),
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
        collection_name="coverage_tests",
        embedding_function=FakeEmbeddings(),
        persist_directory=str(tmp_path_factory.mktemp("chroma_coverage")),
    )
    run_ingestion(data_dir=data, embeddings=FakeEmbeddings(), store=store)
    return store


def _evidence_sources(result):
    return [d["source"] for d in result.diagnostics["documents"]]


def _tier_sources(result, category):
    return [d["source"] for d in result.diagnostics["documents"]
            if d["role"] == "tier" and d["category"] == category]


# ------------------------------------------------------------- A. novelty ---

def test_covered_incumbents_yield_tier_slots_to_novel_documents(store):
    """The Multimodal shape: once the incumbents are covered, the tier draws
    the newcomers instead of repeating the winners."""
    known = frozenset({
        "completed_projects/alpha.md",
        "completed_projects/beta.md",
        "completed_projects/gamma.md",
        "stories_lessons/alpha.md",
        "stories_lessons/beta.md",
        "stories_lessons/gamma.md",
        "evidence/alpha.md",
    })
    result = stratified_retrieve(QUERY, vector_store=store,
                                 known_sources=known)
    tier_projects = _tier_sources(result, "completed_projects")
    assert "completed_projects/novel_build.md" in tier_projects
    assert "completed_projects/novel_app.md" in tier_projects
    tier_stories = _tier_sources(result, "stories_lessons")
    assert "stories_lessons/novel_lesson.md" in tier_stories
    assert "evidence/novel.md" in _evidence_sources(result)

def test_second_run_surfaces_what_the_first_run_missed(store):
    """Rotation across runs: cover run one's sources, run two carries new
    documents — the property that lets future additions surface."""
    first = stratified_retrieve(QUERY, vector_store=store)
    first_sources = frozenset(_evidence_sources(first))
    assert "completed_projects/novel_build.md" not in first_sources
    second = stratified_retrieve(QUERY, vector_store=store,
                                 known_sources=first_sources)
    second_sources = _evidence_sources(second)
    assert "completed_projects/novel_build.md" in second_sources
    assert "completed_projects/novel_app.md" in second_sources


# ---------------------------------------------------------- B. diversity ---

def test_novelty_preserves_diversity_and_budgets(store):
    """The preference reorders within strata; it never collapses them: three
    tiers still draw, no source repeats, the budget still binds."""
    known = frozenset({
        "completed_projects/alpha.md",
        "completed_projects/beta.md",
        "completed_projects/gamma.md",
    })
    result = stratified_retrieve(QUERY, vector_store=store,
                                 known_sources=known)
    docs = result.diagnostics["documents"]
    sources = [d["source"] for d in docs]
    assert len(sources) == len(set(sources))
    assert len(docs) == CONTEXT_BUDGET
    categories = {d["category"] for d in docs}
    assert len(categories) >= 3
    for category in ("completed_projects", "in_progress_projects",
                     "stories_lessons"):
        assert len(_tier_sources(result, category)) == 3


# ---------------------------------------------------------- C. no change ---

def test_empty_known_sources_is_pure_similarity_order(store):
    """Without coverage the composition is exactly the old behavior:
    incumbents win, certificates stay last-resort, guidance stays outside."""
    defaulted = stratified_retrieve(QUERY, vector_store=store)
    explicit = stratified_retrieve(QUERY, vector_store=store,
                                   known_sources=frozenset())
    assert ([d["source"] for d in explicit.diagnostics["documents"]]
            == [d["source"] for d in defaulted.diagnostics["documents"]])
    tier_projects = _tier_sources(explicit, "completed_projects")
    assert set(tier_projects) == {
        "completed_projects/alpha.md",
        "completed_projects/beta.md",
        "completed_projects/gamma.md",
    }
    assert "certificates/alpha.md" not in _evidence_sources(explicit)
    assert explicit.diagnostics["guidance_documents"] == 3


# ------------------------------------------------------- D. weak stays out ---

def test_irrelevant_documents_are_not_conjured_by_novelty(store):
    """Novelty decides *which half* is drawn from; similarity still decides
    *within* each half. With enough matching novel documents to fill the
    tier, the zero-overlap document stays out — and the budget still binds."""
    known = frozenset({
        "completed_projects/alpha.md",
        "completed_projects/beta.md",
        "completed_projects/gamma.md",
    })
    result = stratified_retrieve(QUERY, vector_store=store,
                                 known_sources=known)
    tier_projects = _tier_sources(result, "completed_projects")
    assert set(tier_projects) == {
        "completed_projects/novel_build.md",
        "completed_projects/novel_app.md",
        "completed_projects/novel_tool.md",
    }
    assert "completed_projects/offtopic.md" not in _evidence_sources(result)
    assert len(result.diagnostics["documents"]) == CONTEXT_BUDGET


# --------------------------------------------------- E. no topic sensing ---

def test_novelty_keys_on_coverage_not_vocabulary(store):
    """The barely-overlapping newcomer still displaces dense incumbents once
    they are covered: the lesson shares one query phrase, the incumbents
    share it twice, yet coverage alone decides — no term, topic, or file
    name is special-cased."""
    known = frozenset({
        "stories_lessons/alpha.md",
        "stories_lessons/beta.md",
        "stories_lessons/gamma.md",
    })
    result = stratified_retrieve(QUERY, vector_store=store,
                                 known_sources=known)
    tier_stories = _tier_sources(result, "stories_lessons")
    # Without coverage the tier would be alpha/beta/gamma on similarity
    # alone; with it, the barely-overlapping newcomer takes the first slot.
    assert tier_stories[0] == "stories_lessons/novel_lesson.md"


# ------------------------------------------------------- store coverage ---

@pytest.fixture
def state_path(tmp_path):
    return tmp_path / "state_db" / "operational_state.db"


def _enqueue(store, fingerprint, topic, sources):
    return store.enqueue_opportunity(
        fingerprint, topic,
        [{"source": source, "chunk_id": f"hash{i}:0",
          "content_hash": f"hash{i}", "evidence_state": None,
          "category": topic, "document_type": None, "content": "x"}
         for i, source in enumerate(sources)],
        evidence_strength=0,
    )


def test_covered_evidence_sources_lists_every_row(state_path):
    """All rows count — queued, published, or rejected — because each row's
    snapshot records material one context already carried."""
    with StateStore(state_path) as store:
        assert store.covered_evidence_sources() == frozenset()
        _enqueue(store, "fp1", "evidence",
                 ["evidence/alpha.md", "evidence/beta.md"])
        _enqueue(store, "fp2", "completed_projects",
                 ["completed_projects/alpha.md"])
        covered = store.covered_evidence_sources()
    assert covered == frozenset({
        "evidence/alpha.md",
        "evidence/beta.md",
        "completed_projects/alpha.md",
    })


def test_covered_sources_drive_stratified_recall(store, state_path):
    """The store set plugs straight into retrieval: end-to-end wiring of the
    novelty preference without a model or a network."""
    with StateStore(state_path) as state:
        _enqueue(state, "fp1", "completed_projects",
                 ["completed_projects/alpha.md",
                  "completed_projects/beta.md",
                  "completed_projects/gamma.md"])
        known = state.covered_evidence_sources()
    result = stratified_retrieve(QUERY, vector_store=store,
                                 known_sources=known)
    assert "completed_projects/novel_build.md" in _tier_sources(
        result, "completed_projects")
