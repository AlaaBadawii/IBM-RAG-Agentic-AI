"""Strategy 5: hybrid retrieval via Reciprocal Rank Fusion (RRF).

Why not average raw scores? Vector scores are cosine distances in [0, ~2];
BM25 scores are unbounded positive numbers. Averaging them mixes units —
BM25 would dominate simply because its numbers are bigger.

RRF ignores raw scores and uses only RANKINGS:

    RRF(d) = sum over each ranking list L containing d of
             1 / (rank_L(d) + k)

with k (typically 60) damping the contribution of top ranks so that being
#1 in one list doesn't swamp being #3 in three lists. A document that
appears in BOTH the vector and BM25 rankings accumulates contributions —
that is the fusion effect.

Diagnostics expose per-document provenance: vector rank, BM25 rank, each
RRF contribution, and the final fused rank — so the playground can show
exactly *why* a document won.
"""
import time

from app.config import HYBRID_CANDIDATES, RRF_K, TOP_K
from app.logging_config import get_logger
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.models import RetrievedDocument, RetrievalResult
from app.retrieval.vector import VectorRetriever

logger = get_logger(__name__)


def rrf_score(ranks: list[int], k: int = RRF_K) -> float:
    """Pure RRF formula: sum of 1/(rank + k) over the given ranks.

    Args:
        ranks: 1-based positions of the document in each ranking list.
        k: damping constant (60 per Cormack et al. 2009).
    """
    return sum(1.0 / (rank + k) for rank in ranks)


class HybridRetriever:
    """Vector + BM25 candidates fused with RRF."""

    def __init__(self, vector_retriever: VectorRetriever | None = None,
                 bm25_retriever: BM25Retriever | None = None):
        self._vector = vector_retriever or VectorRetriever()
        self._bm25 = bm25_retriever or BM25Retriever(store=self._vector.store)

    def retrieve(self, query: str, top_k: int = TOP_K,
                 candidates_per_strategy: int = HYBRID_CANDIDATES) -> RetrievalResult:
        started = time.perf_counter()

        # 1. Candidate generation — recall stage. Each strategy contributes
        #    its own candidates; note top_k here is deliberately LARGER than
        #    the final top_k (high recall into fusion).
        vector_result = self._vector.retrieve(query, top_k=candidates_per_strategy)
        bm25_ranking = self._bm25.rank_all(query)

        vector_docs = vector_result.documents
        # BM25 ranking as RetrievedDocuments (top N).
        store_meta = {  # source+content -> metadata, from vector docs when available
            d.chunk_id: d for d in vector_docs
        }
        bm25_docs = []
        for rank, (score, idx) in enumerate(bm25_ranking[:candidates_per_strategy], start=1):
            meta = self._bm25._metas[idx]
            bm25_docs.append(
                RetrievedDocument(
                    content=self._bm25._docs[idx],
                    score=score,
                    source=meta.get("source", "unknown"),
                    metadata=meta,
                    strategy="bm25",
                    chunk_id=self._bm25._chunk_ids[idx],
                    rank=rank,
                )
            )

        # 2. Rank-based fusion — precision stage. RRF needs only rankings.
        vector_rank_by_id = {d.chunk_id: d.rank for d in vector_docs}
        bm25_rank_by_id = {d.chunk_id: d.rank for d in bm25_docs}
        doc_by_id = {}
        for d in vector_docs + bm25_docs:
            doc_by_id.setdefault(d.chunk_id, d)

        fused: list[RetrievedDocument] = []
        for chunk_id, doc in doc_by_id.items():
            v_rank = vector_rank_by_id.get(chunk_id)
            b_rank = bm25_rank_by_id.get(chunk_id)
            ranks = [r for r in (v_rank, b_rank) if r is not None]
            score = rrf_score(ranks)
            fused.append(
                RetrievedDocument(
                    content=doc.content,
                    score=score,
                    source=doc.source,
                    metadata={
                        **doc.metadata,
                        "vector_rank": v_rank,
                        "bm25_rank": b_rank,
                        "rrf_contributions": [
                            round(1.0 / (r + RRF_K), 6) for r in ranks
                        ],
                    },
                    strategy="hybrid",
                    chunk_id=chunk_id,
                    rank=0,
                )
            )
        fused.sort(key=lambda d: d.score, reverse=True)
        for final_rank, doc in enumerate(fused, start=1):
            doc.rank = final_rank
        fused = fused[:top_k]

        elapsed_ms = (time.perf_counter() - started) * 1000
        return RetrievalResult(
            query=query,
            strategy="hybrid",
            documents=fused,
            diagnostics={
                "latency_ms": round(elapsed_ms, 1),
                "vector_candidates": len(vector_docs),
                "bm25_candidates": len(bm25_docs),
                "fused_candidates": len(doc_by_id),
                "final_results": len(fused),
                "rrf_k": RRF_K,
                "candidates_per_strategy": candidates_per_strategy,
                "score_semantics": "RRF score (higher = better; sum of 1/(rank+60))",
            },
        )
