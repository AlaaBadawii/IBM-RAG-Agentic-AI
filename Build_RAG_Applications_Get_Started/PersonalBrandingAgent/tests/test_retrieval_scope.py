"""The retrieval scope: the curated corpus, and only that.

Two populations share one Chroma collection — the hand-written ``data/``
corpus and the ``@source/*`` mirrors the synchronizer copies out of the
user's repositories — and the mirrors are 94% of it. These tests pin the
scope that keeps a branding decision's retrieval inside the first one.

Everything here runs on a synthetic store, so no model download and no
network. The one claim that can only be checked against the real corpus —
that the category allow-list selects exactly the non-mirror chunks — is
asserted as a *property* of the fixtures plus an explicit count below, and
was measured against the live store at 350 of 350 curated chunks in and 0 of
5,337 mirrors in.
"""
import pytest

from app.retrieval.bm25 import BM25Retriever
from app.retrieval.engine import RetrievalEngine
from app.retrieval.scope import CURATED, CURATED_CATEGORIES, is_curated_source
from app.retrieval.vector import VectorRetriever
from app.sync.namespace import source_key
from tests.conftest import FakeEmbeddings

MIRROR_TEXT = (
    "A raw repository file: retrieval pipelines, candidate projects, and "
    "professional achievement wiring for the shipment service."
)


@pytest.fixture(scope="module")
def mixed_store(tmp_path_factory):
    """One collection holding both populations, as production does."""
    from langchain_chroma import Chroma
    from app.ingestion.pipeline import run_ingestion

    data = tmp_path_factory.mktemp("scope_data")
    files = {
        "in_progress_projects/branding_agent.md": (
            "# Branding agent\n\n## Status\nIN PROGRESS\n\n"
            "I built a retrieval pipeline and an evidence verifier.\n"
        ),
        "completed_projects/quizey.md": (
            "# Quizey\n\n## Status\nCOMPLETED\n\n"
            "A quiz platform built with FastAPI and PostgreSQL.\n"
        ),
        "certificates/some_programme.md": (
            "# Some programme\n\n## Status\nCOMPLETED\n\n"
            "Professional achievement, completed and credentialled.\n"
        ),
    }
    for rel, text in files.items():
        path = data / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    store = Chroma(
        collection_name="scope_tests",
        embedding_function=FakeEmbeddings(),
        persist_directory=str(tmp_path_factory.mktemp("chroma_scope")),
    )
    run_ingestion(data_dir=data, embeddings=FakeEmbeddings(), store=store)

    # Two mirrors, whose `category` is the *source name* — exactly what the
    # synchronizer writes and what no corpus category can be.
    store.add_texts(
        texts=[MIRROR_TEXT, "Another mirrored file about the same project."],
        metadatas=[
            {"source": source_key("quizey-v2", "src/api/main.py"),
             "category": "quizey-v2", "document_type": "unknown"},
            {"source": source_key("ai-agents", "PROGRESS.md"),
             "category": "ai-agents", "document_type": "unknown"},
        ],
        ids=["mirror:0", "mirror:1"],
    )
    return store


def _sources(result):
    return [d.source for d in result.documents]


# ------------------------------------------------------------- the predicate ---

def test_a_mirror_key_is_not_curated():
    assert not is_curated_source(source_key("quizey-v2", "src/api/main.py"))


def test_a_corpus_path_is_curated():
    assert is_curated_source("in_progress_projects/branding_agent.md")


def test_the_curated_categories_are_the_corpus_section_names():
    """The allow-list is derived from the taxonomy, not spelled out again."""
    from app.context.taxonomy import EVIDENCE_SECTION_BY_CATEGORY, GUIDANCE_SECTIONS

    assert CURATED_CATEGORIES == (
        frozenset(EVIDENCE_SECTION_BY_CATEGORY) | frozenset(GUIDANCE_SECTIONS)
    )
    # The two sections that are not fed by a category are absent, and their
    # absence is what excludes the mirrors.
    assert "repository_evidence" not in CURATED_CATEGORIES
    assert "unclassified" not in CURATED_CATEGORIES


# ------------------------------------------------ the two representations ---

def test_the_where_clause_selects_exactly_what_the_predicate_selects(mixed_store):
    """The two halves of a scope must not be able to disagree.

    ``predicate`` reads the source key and ``where`` reads ``category``,
    because Chroma cannot filter on a prefix. That makes ``where`` a derived
    statement, and a derived statement is one that can drift. This asserts
    they agree over every chunk actually in the store.
    """
    stored = mixed_store.get(include=["metadatas"])
    categories = CURATED.where["category"]["$in"]

    for chunk_id, metadata in zip(stored["ids"], stored["metadatas"]):
        metadata = metadata or {}
        by_predicate = CURATED.includes(metadata)
        by_where = metadata.get("category") in categories
        assert by_predicate == by_where, (
            f"{chunk_id}: predicate={by_predicate} where={by_where} "
            f"(category={metadata.get('category')!r})"
        )


def test_the_scope_actually_separates_the_two_populations(mixed_store):
    """A guard on the fixture: it must hold both, or it proves nothing."""
    stored = mixed_store.get(include=["metadatas"])
    within = [m for m in stored["metadatas"] if CURATED.includes(m or {})]
    without = [m for m in stored["metadatas"] if not CURATED.includes(m or {})]

    assert len(within) == 3, "the three curated files"
    assert len(without) == 2, "the two mirrors"


# ------------------------------------------------------------- vector side ---

def test_scoped_vector_retrieval_never_returns_a_mirror(mixed_store):
    engine = RetrievalEngine(store=mixed_store, scope=CURATED)
    result = engine.retrieve(MIRROR_TEXT, strategy="vector", top_k=10)

    assert result.documents, "the curated chunks still match"
    assert not [s for s in _sources(result) if s.startswith("@source/")]


def test_unscoped_vector_retrieval_still_sees_the_mirrors(mixed_store):
    """The scope is a property of the caller, not of the store.

    Sync and general search must keep seeing everything; only the branding
    context asked for the narrower corpus.
    """
    engine = RetrievalEngine(store=mixed_store)
    result = engine.retrieve(MIRROR_TEXT, strategy="vector", top_k=10)

    assert any(s.startswith("@source/") for s in _sources(result))


# --------------------------------------------------------------- bm25 side ---

def test_scoped_bm25_indexes_only_the_curated_corpus(mixed_store):
    retriever = BM25Retriever(store=mixed_store, scope=CURATED)
    retriever._build_index()

    assert retriever._chunk_ids, "the curated corpus is not empty"
    assert not [c for c in retriever._chunk_ids if c == "mirror:0"]
    assert len(retriever._chunk_ids) == 3


def test_scoped_bm25_excludes_mirrors_even_when_they_are_the_only_match(mixed_store):
    """Exclusion, not deprioritisation: a mirror that matches perfectly and a
    curated chunk that does not match at all must not swap places."""
    retriever = BM25Retriever(store=mixed_store, scope=CURATED)
    result = retriever.retrieve("shipment service wiring", top_k=10)

    assert not [s for s in _sources(result) if s.startswith("@source/")]


def test_unscoped_bm25_still_indexes_everything(mixed_store):
    retriever = BM25Retriever(store=mixed_store)
    retriever._build_index()

    assert len(retriever._chunk_ids) == 5
    assert "mirror:0" in retriever._chunk_ids


def test_a_scope_that_matches_nothing_returns_nothing(mixed_store):
    """An empty scope is an answer, not a reason to fall back to everything.

    BM25 cannot be fitted on no documents; the failure to avoid is the one
    that would quietly hand back the whole collection instead.
    """
    from app.retrieval.scope import CorpusScope

    nothing = CorpusScope(name="empty", predicate=lambda meta: False, where=None)
    retriever = BM25Retriever(store=mixed_store, scope=nothing)

    assert retriever.retrieve("anything", top_k=5).documents == []
    assert retriever.rank_all("anything") == []


# ------------------------------------------------------- scope + strategy ---

@pytest.mark.parametrize("strategy", ["vector", "bm25", "hybrid"])
def test_every_scoped_strategy_stays_inside_the_scope(mixed_store, strategy):
    engine = RetrievalEngine(store=mixed_store, scope=CURATED)
    result = engine.retrieve(MIRROR_TEXT, strategy=strategy, top_k=10)

    assert not [s for s in _sources(result) if s.startswith("@source/")], (
        f"{strategy} leaked mirror content past the scope"
    )


def test_a_scoped_hybrid_uses_one_corpus_for_both_halves(mixed_store):
    """RRF compares ranks, so the halves must rank the same documents."""
    engine = RetrievalEngine(store=mixed_store, scope=CURATED)
    retriever = engine._get_bm25()
    result = engine.retrieve(MIRROR_TEXT, strategy="hybrid", top_k=10)

    assert result.diagnostics["bm25_candidates"] == len(retriever._chunk_ids)


def test_the_scope_combines_with_a_caller_filter_rather_than_replacing_it(mixed_store):
    """The metadata strategy's own filter must not cancel the scope."""
    engine = RetrievalEngine(store=mixed_store, scope=CURATED)
    result = engine.retrieve(
        "retrieval pipeline", strategy="metadata", top_k=10,
        filters={"category": "in_progress_projects"},
    )

    assert [d.source for d in result.documents] == [
        "in_progress_projects/branding_agent.md"
    ]
    effective = result.diagnostics["effective_filter"]
    assert effective["$and"][0] == CURATED.where


def test_the_scope_is_recorded_in_diagnostics(mixed_store):
    """A result says which corpus it came from, without inference."""
    scoped = RetrievalEngine(store=mixed_store, scope=CURATED)
    assert scoped.retrieve("x", strategy="vector").diagnostics["scope"] == "curated"
    assert RetrievalEngine(store=mixed_store).retrieve(
        "x", strategy="vector"
    ).diagnostics["scope"] is None


def test_a_retriever_exposes_its_scope(mixed_store):
    assert VectorRetriever(store=mixed_store, scope=CURATED).scope is CURATED
    assert VectorRetriever(store=mixed_store).scope is None
