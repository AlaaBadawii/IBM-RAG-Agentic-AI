"""Tests for evaluation metrics (Hit@K, MRR) — pure functions, no retrieval."""
from app.retrieval.evaluation import hit_at_k, load_gold_queries, reciprocal_rank
from app.retrieval.models import RetrievedDocument, RetrievalResult


def _result(sources_with_ranks):
    """Build a RetrievalResult from [(source, rank), ...]."""
    docs = [
        RetrievedDocument(content="x", score=1.0, source=src, rank=rank)
        for src, rank in sources_with_ranks
    ]
    return RetrievalResult(query="q", strategy="test", documents=docs)


def test_hit_at_k_true_when_relevant_in_top_k():
    result = _result([("a.md", 1), ("b.md", 2), ("relevant.md", 3)])
    assert hit_at_k(result, {"relevant.md"}, k=3) is True


def test_hit_at_k_false_when_relevant_beyond_k():
    result = _result([("a.md", 1), ("b.md", 2), ("relevant.md", 3)])
    assert hit_at_k(result, {"relevant.md"}, k=2) is False


def test_hit_at_k_false_when_nothing_relevant():
    result = _result([("a.md", 1), ("b.md", 2)])
    assert hit_at_k(result, {"relevant.md"}, k=5) is False


def test_hit_at_k_ignores_relevant_chunks_ranked_low():
    result = _result([("relevant.md", 1), ("b.md", 2)])
    assert hit_at_k(result, {"relevant.md"}, k=1) is True


def test_reciprocal_rank_first_position():
    result = _result([("relevant.md", 1), ("other.md", 2)])
    assert reciprocal_rank(result, {"relevant.md"}) == 1.0


def test_reciprocal_rank_third_position():
    result = _result([("a.md", 1), ("b.md", 2), ("relevant.md", 3)])
    assert reciprocal_rank(result, {"relevant.md"}) == 1 / 3


def test_reciprocal_rank_zero_when_missing():
    result = _result([("a.md", 1)])
    assert reciprocal_rank(result, {"relevant.md"}) == 0.0


def test_reciprocal_rank_uses_first_relevant():
    # Two relevant docs: rank 2 and rank 4 — RR must use rank 2.
    result = _result([("a.md", 1), ("rel1.md", 2), ("b.md", 3), ("rel2.md", 4)])
    assert reciprocal_rank(result, {"rel1.md", "rel2.md"}) == 0.5


def test_gold_queries_file_is_valid_and_varied():
    gold = load_gold_queries()
    assert 8 <= len(gold) <= 12
    queries = [g["query"] for g in gold]
    assert len(set(queries)) == len(queries)  # no duplicates
    for item in gold:
        assert item["relevant_sources"], f"no relevant sources for {item['query']}"
        assert all(isinstance(s, str) and s.endswith(".md") for s in item["relevant_sources"])
