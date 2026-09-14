"""Strategy 6: cross-encoder reranking.

Stage separation — the core lesson:

    retrieval (vector/BM25/hybrid) = HIGH RECALL
        cheap per document (embedding similarity / token counting),
        runs over the whole corpus, approximate relevance.

    reranking (cross-encoder) = HIGH PRECISION
        expensive per (query, document) PAIR — the model reads query and
        document together and scores their interaction. Running it over
        the entire corpus would be orders of magnitude slower, so we only
        rerank the top candidate pool from hybrid retrieval.

Pipeline:
    vector + BM25 -> RRF fused candidate pool (~20)
        -> cross-encoder scores each (query, chunk) pair
        -> reranked top 5
"""
import time

from app.config import RERANKER_MODEL, TOP_K
from app.logging_config import get_logger
from app.retrieval.fusion import HybridRetriever
from app.retrieval.models import RetrievedDocument, RetrievalResult

logger = get_logger(__name__)


class CrossEncoderReranker:
    """Local cross-encoder relevance scorer (sentence-transformers).

    The model is loaded lazily and cached; tests inject a fake with the
    same `predict(pairs) -> scores` interface.
    """

    def __init__(self, model_name: str = RERANKER_MODEL):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            logger.info("Loading cross-encoder %s", self.model_name)
            self._model = CrossEncoder(self.model_name)
        return self._model

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        """Score (query, document) pairs; higher = more relevant."""
        if not pairs:
            return []
        return [float(s) for s in self._load().predict(pairs)]


class RerankedRetriever:
    """Hybrid retrieval + cross-encoder reranking of the candidate pool."""

    def __init__(self, hybrid_retriever: HybridRetriever | None = None,
                 reranker: CrossEncoderReranker | None = None):
        self._hybrid = hybrid_retriever or HybridRetriever()
        self._reranker = reranker or CrossEncoderReranker()

    def retrieve(self, query: str, top_k: int = TOP_K,
                 candidate_pool: int = 20) -> RetrievalResult:
        started = time.perf_counter()

        # Stage 1: recall — pull a larger candidate pool via hybrid RRF.
        hybrid_result = self._hybrid.retrieve(
            query, top_k=candidate_pool,
            candidates_per_strategy=max(10, candidate_pool // 2),
        )
        candidates = hybrid_result.documents

        # Stage 2: precision — cross-encoder over (query, chunk) pairs ONLY.
        pairs = [(query, doc.content) for doc in candidates]
        scores = self._reranker.score(pairs)

        reranked = [
            RetrievedDocument(
                content=doc.content,
                score=score,
                source=doc.source,
                metadata={
                    **{k: v for k, v in doc.metadata.items()
                       if k not in ("vector_rank", "bm25_rank", "rrf_contributions")},
                    "pre_rerank_rank": doc.rank,
                },
                strategy="reranked",
                chunk_id=doc.chunk_id,
                rank=0,
            )
            for doc, score in zip(candidates, scores)
        ]
        reranked.sort(key=lambda d: d.score, reverse=True)
        for rank, doc in enumerate(reranked[:top_k], start=1):
            doc.rank = rank
        reranked = reranked[:top_k]

        elapsed_ms = (time.perf_counter() - started) * 1000
        return RetrievalResult(
            query=query,
            strategy="reranked",
            documents=reranked,
            diagnostics={
                "latency_ms": round(elapsed_ms, 1),
                "candidate_pool": len(candidates),
                "final_results": len(reranked),
                "reranker_model": self._reranker.model_name,
                "rank_changes": [
                    {
                        "source": d.source,
                        "pre": d.metadata.get("pre_rerank_rank"),
                        "post": d.rank,
                    }
                    for d in reranked
                ],
                "score_semantics": "cross-encoder relevance (higher = better)",
            },
        )
