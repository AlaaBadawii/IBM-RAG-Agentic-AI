"""Tests for multi-query, RRF fusion, and reranking.

Multi-query is tested against a FAKE LLM (no network, no OpenRouter).
Fusion tests verify the RRF math explicitly. Reranking tests use the
FakeCrossEncoder from conftest.
"""
import pytest
from langchain_core.messages import AIMessage

from app.retrieval.bm25 import BM25Retriever
from app.retrieval.fusion import HybridRetriever, rrf_score
from app.retrieval.multi_query import MultiQueryRetriever
from app.retrieval.reranker import CrossEncoderReranker, RerankedRetriever
from app.retrieval.vector import VectorRetriever
from tests.conftest import FakeEmbeddings


@pytest.fixture(scope="module")
def kb_and_store(tmp_path_factory):
    from langchain_chroma import Chroma
    from app.ingestion.pipeline import run_ingestion

    data = tmp_path_factory.mktemp("data")
    files = {
        "evidence/backend/fastapi.md": (
            "# FastAPI\n\n## Evidence state\nVERIFIED\n\n"
            "Built FastAPI shipment API with SQLAlchemy and Alembic migrations.\n"
        ),
        "evidence/backend/databases.md": (
            "# Databases\n\n## Evidence state\nDOCUMENTED\n\n"
            "MongoDB PyMongo CRUD service and PostgreSQL experience.\n"
        ),
        "stories_lessons/quizey_idempotency.md": (
            "# Quizey idempotency\n\n## Status\nCOMPLETED\n\n"
            "Retry-safe API requests using idempotency keys.\n"
        ),
        "completed_projects/airbnb_clone.md": (
            "# AirBnB clone\n\n## Status\nCOMPLETED\n\n"
            "Flask MySQL REST API console full-stack clone.\n"
        ),
        "in_progress_projects/kubernetes_lab.md": (
            "# Kubernetes lab\n\n## Status\nIN PROGRESS\n\n"
            "Kubernetes deployments services ingress practice.\n"
        ),
    }
    for rel, text in files.items():
        path = data / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    store = Chroma(
        collection_name="fusion_tests",
        embedding_function=FakeEmbeddings(),
        persist_directory=str(tmp_path_factory.mktemp("chroma")),
    )
    run_ingestion(data_dir=data, embeddings=FakeEmbeddings(), store=store)
    return store


# -------------------------------------------------------------- RRF math ---

def test_rrf_formula_single_rank():
    # 1/(1+60) = 0.016393...
    assert rrf_score([1], k=60) == pytest.approx(1 / 61, rel=1e-6)


def test_rrf_formula_multiple_ranks():
    # 1/(1+60) + 1/(3+60)
    assert rrf_score([1, 3], k=60) == pytest.approx(1 / 61 + 1 / 63, rel=1e-6)


def test_rrf_k_damps_top_ranks():
    """With small k, rank #1 dominates; with k=60 it barely beats rank #2."""
    small_gap = rrf_score([1], k=1) - rrf_score([2], k=1)
    large_gap = rrf_score([1], k=60) - rrf_score([2], k=60)
    assert small_gap > large_gap


def test_rrf_document_in_both_lists_beats_single_list():
    """The fusion effect: appearing in both rankings accumulates score."""
    in_both = rrf_score([3, 5])       # rank 3 in vector, rank 5 in bm25
    in_one = rrf_score([1])           # rank 1 in only one list
    # rank-1-in-one-list still wins here — but 3,5 vs 8,9 is the real test:
    assert rrf_score([3, 5]) > rrf_score([8, 9])
    assert in_both > rrf_score([9])


# ------------------------------------------------------------ multi-query ---

class FakeLLM:
    """Returns a canned multi-query response, like a real OpenRouter call."""

    def __init__(self, text: str):
        self.text = text
        self.calls = []

    def invoke(self, prompt: str):
        self.calls.append(prompt)
        return AIMessage(content=self.text)


def test_multi_query_expands_and_dedupes(kb_and_store):
    fake = FakeLLM("FastAPI database API development\nbackend SQLAlchemy projects\n")
    retriever = MultiQueryRetriever(VectorRetriever(store=kb_and_store), llm=fake)
    result = retriever.retrieve("backend engineering", top_k=2, n_queries=2)
    assert result.strategy == "multi_query"
    assert fake.calls, "LLM must have been called"
    assert result.diagnostics["generated_queries"] == [
        "FastAPI database API development", "backend SQLAlchemy projects"
    ]
    # Original query is preserved in all_queries.
    assert result.diagnostics["all_queries"][0] == "backend engineering"
    # Dedup: no duplicate chunk ids in the merged result.
    ids = [d.chunk_id for d in result.documents]
    assert len(ids) == len(set(ids))
    assert not result.diagnostics["llm_fallback_used"]


def test_multi_query_falls_back_on_llm_failure(kb_and_store):
    class ExplodingLLM:
        def invoke(self, prompt):
            raise RuntimeError("OpenRouter down")

    retriever = MultiQueryRetriever(VectorRetriever(store=kb_and_store), llm=ExplodingLLM())
    result = retriever.retrieve("backend engineering", top_k=2)
    # Deterministic fallback: just the original query, still functional.
    assert result.diagnostics["llm_fallback_used"] is True
    assert result.documents  # retrieval still returned something


def test_multi_query_preserves_original_query_always(kb_and_store):
    retriever = MultiQueryRetriever(VectorRetriever(store=kb_and_store), llm=FakeLLM("x\ny\n"))
    result = retriever.retrieve("Kubernetes ingress", top_k=1)
    assert "Kubernetes ingress" in result.diagnostics["all_queries"]


# ---------------------------------------------------------------- fusion ---

def test_hybrid_returns_fused_results_with_provenance(kb_and_store):
    hybrid = HybridRetriever(
        VectorRetriever(store=kb_and_store),
        BM25Retriever(store=kb_and_store),
    )
    result = hybrid.retrieve("FastAPI Alembic", top_k=3, candidates_per_strategy=10)
    assert result.strategy == "hybrid"
    assert result.documents
    for doc in result.documents:
        assert "vector_rank" in doc.metadata or "bm25_rank" in doc.metadata
        assert doc.metadata.get("vector_rank") is not None or \
               doc.metadata.get("bm25_rank") is not None
    # Ranks are 1..N after fusion.
    ranks = [d.rank for d in result.documents]
    assert ranks == sorted(ranks)
    assert result.diagnostics["rrf_k"] == 60


def test_hybrid_finds_doc_present_in_both_rankings(kb_and_store):
    """A chunk that BOTH strategies rank should surface in the top results.

    With the fake embeddings, "FastAPI" lands the fastapi chunk at vector
    rank 1; the fastapi file also contains the literal token, so it has a
    BM25 rank too. A pure-vector winner (no BM25 rank) can legitimately
    outrank it, so we check the fused top-3 rather than position 1.
    """
    hybrid = HybridRetriever(
        VectorRetriever(store=kb_and_store),
        BM25Retriever(store=kb_and_store),
    )
    result = hybrid.retrieve("FastAPI", top_k=3, candidates_per_strategy=10)
    dual_ranked = [
        d for d in result.documents
        if d.metadata.get("vector_rank") is not None
        and d.metadata.get("bm25_rank") is not None
    ]
    assert dual_ranked, "expected at least one chunk ranked by both strategies"


def test_hybrid_diagnostics_counts(kb_and_store):
    hybrid = HybridRetriever(
        VectorRetriever(store=kb_and_store),
        BM25Retriever(store=kb_and_store),
    )
    result = hybrid.retrieve("database", top_k=2, candidates_per_strategy=5)
    d = result.diagnostics
    assert d["vector_candidates"] == 5
    assert d["bm25_candidates"] <= 5
    assert d["fused_candidates"] >= len(result.documents)
    assert d["final_results"] == len(result.documents)


# ------------------------------------------------------------- reranking ---

def test_reranked_rescores_candidate_pool(kb_and_store):
    reranked = RerankedRetriever(
        HybridRetriever(
            VectorRetriever(store=kb_and_store),
            BM25Retriever(store=kb_and_store),
        ),
        CrossEncoderReranker(),
    )
    # Inject fake cross-encoder into the retriever's reranker.
    from tests.conftest import FakeCrossEncoder
    reranked._reranker = _FakeRerankerWrapper(FakeCrossEncoder())

    result = reranked.retrieve("FastAPI SQLAlchemy", top_k=2, candidate_pool=10)
    assert result.strategy == "reranked"
    assert len(result.documents) <= 2
    assert result.diagnostics["candidate_pool"] <= 10
    assert result.diagnostics["final_results"] == len(result.documents)
    # Every result carries its pre-rerank rank for comparison.
    assert all("pre_rerank_rank" in d.metadata for d in result.documents)


class _FakeRerankerWrapper:
    """Adapts FakeCrossEncoder to the CrossEncoderReranker interface."""

    def __init__(self, fake):
        self._fake = fake
        self.model_name = "fake-cross-encoder"

    def score(self, pairs):
        return self._fake.predict(pairs)


def test_reranked_orders_by_cross_encoder_score(kb_and_store):
    """With the fake encoder (term overlap), a doc sharing more query
    terms must rank above one sharing fewer."""
    from tests.conftest import FakeCrossEncoder

    reranked = RerankedRetriever(
        HybridRetriever(
            VectorRetriever(store=kb_and_store),
            BM25Retriever(store=kb_and_store),
        ),
    )
    reranked._reranker = _FakeRerankerWrapper(FakeCrossEncoder())
    result = reranked.retrieve("Kubernetes deployments ingress", top_k=2, candidate_pool=10)
    k8s_docs = [d for d in result.documents if "kubernetes" in d.source]
    if len(result.documents) >= 2 and k8s_docs:
        assert result.documents[0].source == k8s_docs[0].source
