"""Common retrieval result model.

Every strategy (vector, metadata, bm25, multi_query, hybrid, reranked)
returns a RetrievalResult. This uniform shape is what lets the comparison
playground and the evaluation harness compare strategies without knowing
their internals.

Score semantics warning (important for learning):
    Scores are NOT comparable across strategies.
    - vector:    cosine distance from Chroma (LOWER = more similar)
    - bm25:      unbounded lexical relevance score (HIGHER = better)
    - multi_query: same as vector, but rank comes from a fused order
    - hybrid:    RRF score (HIGHER = better, small values, rank-based)
    - reranked:  cross-encoder relevance (HIGHER = better, roughly 0-10)
    Compare rankings, never raw score numbers across strategies.
"""
from dataclasses import dataclass, field

STRATEGIES = ("vector", "metadata", "bm25", "multi_query", "hybrid", "reranked")


@dataclass
class RetrievedDocument:
    content: str
    score: float
    source: str                    # e.g. "evidence/backend/fastapi.md"
    metadata: dict = field(default_factory=dict)
    strategy: str = ""             # which strategy produced this result
    chunk_id: str = ""             # stable id, used for dedup
    rank: int = 0                  # 1-based rank within this result


@dataclass
class RetrievalResult:
    query: str
    strategy: str
    documents: list[RetrievedDocument] = field(default_factory=list)
    # Free-form diagnostics: generated queries, candidate counts,
    # per-document rank provenance for fusion, latency, etc.
    diagnostics: dict = field(default_factory=dict)
