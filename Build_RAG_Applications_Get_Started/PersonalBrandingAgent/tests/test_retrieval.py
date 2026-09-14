"""Tests for retrieval strategies: vector, metadata filtering, BM25.

Uses the FakeEmbeddings-based store over a small synthetic corpus, so no
model download or network is needed. The synthetic corpus mirrors the
shape of the real one (categories, headings, evidence states).
"""
import pytest

from app.retrieval.bm25 import BM25Retriever, tokenize
from app.retrieval.metadata import FILTERABLE_FIELDS, MetadataRetriever, build_filter
from app.retrieval.models import RetrievalResult
from app.retrieval.vector import VectorRetriever
from tests.conftest import FakeEmbeddings


@pytest.fixture(scope="module")
def synthetic_kb(tmp_path_factory):
    """A miniature knowledge base with real corpus conventions."""
    data = tmp_path_factory.mktemp("data")
    files = {
        "evidence/backend/fastapi.md": (
            "# FastAPI evidence\n\n## Evidence state\nVERIFIED\n\n"
            "I built a FastAPI shipment API with layered architecture, "
            "SQLAlchemy models, and Alembic migrations.\n"
        ),
        "evidence/backend/databases.md": (
            "# Databases\n\n## Evidence state\nDOCUMENTED\n\n"
            "MongoDB with PyMongo, MySQL, PostgreSQL, SQLite experience.\n"
        ),
        "evidence/ai/rag_learning.md": (
            "# RAG learning\n\n## Evidence state\nLEARNING\n\n"
            "Studying retrieval augmented generation, embeddings, Chroma.\n"
        ),
        "completed_projects/airbnb_clone.md": (
            "# AirBnB clone\n\n## Status\nCOMPLETED\n\n"
            "Full-stack clone with Flask, MySQL, REST API, console.\n"
        ),
        "stories_lessons/quizey_idempotency.md": (
            "# Quizey idempotency\n\n## Status\nCOMPLETED\n\n"
            "Retry-safe request handling lesson: idempotency keys in the API.\n"
        ),
        "in_progress_projects/kubernetes_lab.md": (
            "# Kubernetes lab\n\n## Status\nIN PROGRESS\n\n"
            "Learning Kubernetes deployments, services, ingress.\n"
        ),
    }
    for rel, text in files.items():
        path = data / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return data


@pytest.fixture(scope="module")
def ingested_store(synthetic_kb, tmp_path_factory):
    from langchain_chroma import Chroma
    from app.ingestion.pipeline import run_ingestion

    store = Chroma(
        collection_name="retrieval_tests",
        embedding_function=FakeEmbeddings(),
        persist_directory=str(tmp_path_factory.mktemp("chroma")),
    )
    run_ingestion(data_dir=synthetic_kb, embeddings=FakeEmbeddings(), store=store)
    return store


# ----------------------------------------------------------------- vector ---

def test_vector_retrieval_returns_top_k(ingested_store):
    retriever = VectorRetriever(store=ingested_store)
    result = retriever.retrieve("FastAPI backend architecture", top_k=3)
    assert result.strategy == "vector"
    assert len(result.documents) <= 3
    assert all(d.strategy == "vector" for d in result.documents)
    assert all(d.source for d in result.documents)
    assert "latency_ms" in result.diagnostics


def test_vector_retrieval_ranks_semantically_related(ingested_store):
    retriever = VectorRetriever(store=ingested_store)
    result = retriever.retrieve("databases and storage", top_k=2)
    sources = [d.source for d in result.documents]
    assert "evidence/backend/databases.md" in sources


def test_vector_result_shape(ingested_store):
    result = VectorRetriever(store=ingested_store).retrieve("anything", top_k=2)
    assert isinstance(result, RetrievalResult)
    assert result.diagnostics["score_semantics"].startswith("cosine distance")


# ---------------------------------------------------------------- metadata ---

def test_metadata_filter_restricts_results(ingested_store):
    retriever = MetadataRetriever(VectorRetriever(store=ingested_store))
    result = retriever.retrieve(
        "evidence", top_k=10,
        filters={"category": "evidence", "evidence_state": "VERIFIED"},
    )
    assert result.strategy == "metadata"
    assert result.documents
    assert all(
        d.metadata.get("category") == "evidence"
        and d.metadata.get("evidence_state") == "VERIFIED"
        for d in result.documents
    )


def test_metadata_filter_can_exclude_everything(ingested_store):
    retriever = MetadataRetriever(VectorRetriever(store=ingested_store))
    result = retriever.retrieve(
        "anything", top_k=5,
        filters={"category": "evidence", "evidence_state": "VERIFIED", "domain": "ai"},
    )
    # No VERIFIED evidence in the ai domain in the synthetic corpus.
    assert result.documents == []


def test_build_filter_and_logic():
    chroma = build_filter({"category": "evidence", "domain": "backend"})
    assert chroma == {
        "$and": [
            {"category": {"$eq": "evidence"}},
            {"domain": {"$eq": "backend"}},
        ]
    }


def test_build_filter_single_clause():
    assert build_filter({"category": "evidence"}) == {"category": {"$eq": "evidence"}}


def test_build_filter_empty():
    assert build_filter({}) is None


def test_build_filter_rejects_unknown_fields():
    with pytest.raises(ValueError, match="Unknown filter"):
        build_filter({"evidenceState": "VERIFIED"})  # typo: camelCase


def test_filterable_fields_cover_metadata_dimensions():
    for field in ("category", "domain", "status", "evidence_state",
                  "document_type", "project"):
        assert field in FILTERABLE_FIELDS


# -------------------------------------------------------------------- bm25 ---

def test_bm25_exact_terminology(ingested_store):
    retriever = BM25Retriever(store=ingested_store)
    result = retriever.retrieve("PyMongo", top_k=3)
    assert result.strategy == "bm25"
    assert result.documents
    # The doc that literally contains "PyMongo" must rank at the top.
    assert result.documents[0].source == "evidence/backend/databases.md"


def test_bm25_no_match_returns_empty(ingested_store):
    result = BM25Retriever(store=ingested_store).retrieve("zzzznonexistent", top_k=3)
    assert result.documents == []
    assert result.diagnostics["chunks_with_nonzero_score"] == 0


def test_bm25_rank_all_orders_by_score(ingested_store):
    retriever = BM25Retriever(store=ingested_store)
    ranked = retriever.rank_all("FastAPI Alembic migrations")
    assert ranked  # non-empty
    scores = [score for score, _ in ranked]
    assert scores == sorted(scores, reverse=True)


def test_tokenize():
    assert tokenize("FastAPI-Alembic, migrations!") == ["fastapi", "alembic", "migrations"]
    assert tokenize("") == []


# ----------------------------------------------------------------- engine ---

def test_engine_facade_dispatches_all_strategies(ingested_store):
    from app.retrieval.engine import RetrievalEngine
    from app.retrieval.models import STRATEGIES

    engine = RetrievalEngine(store=ingested_store)
    for strategy in STRATEGIES:
        result = engine.retrieve("FastAPI", strategy=strategy, top_k=3)
        assert result.strategy == strategy, f"strategy {strategy} mislabeled"
        assert isinstance(result.documents, list)


def test_engine_rejects_unknown_strategy(ingested_store):
    from app.errors import RetrievalError
    from app.retrieval.engine import RetrievalEngine

    engine = RetrievalEngine(store=ingested_store)
    with pytest.raises(RetrievalError, match="Unknown strategy"):
        engine.retrieve("q", strategy="semantic")


def test_engine_metadata_strategy_passes_filters(ingested_store):
    from app.retrieval.engine import RetrievalEngine

    engine = RetrievalEngine(store=ingested_store)
    result = engine.retrieve(
        "evidence", strategy="metadata", top_k=5,
        filters={"category": "evidence", "evidence_state": "VERIFIED"},
    )
    assert result.diagnostics["filters_applied"] == {
        "category": "evidence", "evidence_state": "VERIFIED"
    }
    assert result.documents


def test_engine_retrieve_all_runs_every_strategy(ingested_store):
    from app.retrieval.engine import RetrievalEngine

    engine = RetrievalEngine(store=ingested_store)
    # multi_query without an injected LLM falls back gracefully.
    results = engine.retrieve_all("databases", top_k=2)
    assert set(results.keys()) == {
        "vector", "metadata", "bm25", "multi_query", "hybrid", "reranked"
    }


# --------------------------------------------------------------- compare ----

def test_compare_derive_filter_deterministic():
    from app.retrieval.compare import derive_filter
    assert derive_filter("Show me verified evidence about backend") == {
        "category": "evidence", "evidence_state": "VERIFIED"
    }
    assert derive_filter("a lesson about Kubernetes") == {
        "category": "stories_lessons"
    }
    assert derive_filter("random words here") == {"category": "evidence"}


def test_compare_cli_runs_all_strategies(ingested_store, capsys):
    from app.retrieval.compare import main

    code = main(["FastAPI databases", "--top-k", "2"])
    assert code == 0
    out = capsys.readouterr().out
    assert "STRATEGY: VECTOR" in out
    assert "STRATEGY: BM25" in out
    assert "SUMMARY" in out
    assert "WHY THE RESULTS DIFFER" in out


def test_compare_cli_rejects_unknown_strategy(ingested_store, capsys):
    from app.retrieval.compare import main

    code = main(["q", "--strategies", "nope"])
    assert code == 2
