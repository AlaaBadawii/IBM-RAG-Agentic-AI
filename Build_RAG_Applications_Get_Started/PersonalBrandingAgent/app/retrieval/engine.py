"""Retrieval engine — one facade over all strategies.

    engine.retrieve(query, strategy="vector", top_k=5, filters=None)

Strategies: vector | metadata | bm25 | multi_query | hybrid | reranked.

The facade hides construction of the individual retrievers (and their
shared Chroma store) while keeping each result's diagnostics available.
This is deliberately NOT an agent: the caller picks the strategy
explicitly. When an Agent is added later, it will choose strategies for
reasons — and this interface is what it will call.
"""
from app.config import TOP_K
from app.errors import RetrievalError
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.fusion import HybridRetriever
from app.retrieval.metadata import MetadataRetriever
from app.retrieval.models import STRATEGIES, RetrievalResult
from app.retrieval.multi_query import MultiQueryRetriever
from app.retrieval.reranker import RerankedRetriever
from app.retrieval.vector import VectorRetriever


class RetrievalEngine:
    """Single entry point for all retrieval strategies."""

    def __init__(self, store=None, llm=None, reranker=None):
        """All collaborators are injectable for tests; production wiring
        happens lazily on first use."""
        self._store = store
        self._llm = llm
        self._reranker = reranker
        self._vector = None
        self._bm25 = None

    def _get_vector(self) -> VectorRetriever:
        if self._vector is None:
            self._vector = VectorRetriever(store=self._store)
        return self._vector

    def _get_bm25(self) -> BM25Retriever:
        if self._bm25 is None:
            self._bm25 = BM25Retriever(store=self._get_vector().store)
        return self._bm25

    def retrieve(self, query: str, strategy: str = "vector",
                 top_k: int = TOP_K, filters: dict | None = None) -> RetrievalResult:
        """Run one retrieval strategy.

        Args:
            query: the question.
            strategy: one of STRATEGIES.
            top_k: number of documents to return.
            filters: metadata filters (only used by the 'metadata' strategy).
        """
        if strategy not in STRATEGIES:
            raise RetrievalError(
                f"Unknown strategy {strategy!r}. Choose from: {', '.join(STRATEGIES)}"
            )
        if strategy == "vector":
            return self._get_vector().retrieve(query, top_k=top_k)
        if strategy == "metadata":
            retriever = MetadataRetriever(self._get_vector())
            return retriever.retrieve(query, top_k=top_k, filters=filters)
        if strategy == "bm25":
            return self._get_bm25().retrieve(query, top_k=top_k)
        if strategy == "multi_query":
            retriever = MultiQueryRetriever(self._get_vector(), llm=self._llm)
            return retriever.retrieve(query, top_k=top_k)
        if strategy == "hybrid":
            return HybridRetriever(self._get_vector(), self._get_bm25()).retrieve(
                query, top_k=top_k
            )
        if strategy == "reranked":
            hybrid = HybridRetriever(self._get_vector(), self._get_bm25())
            reranked = RerankedRetriever(hybrid, reranker=self._reranker)
            return reranked.retrieve(query, top_k=top_k)
        raise RetrievalError(f"Unhandled strategy {strategy!r}")  # unreachable

    def retrieve_all(self, query: str, top_k: int = TOP_K,
                     filters: dict | None = None,
                     strategies: tuple = STRATEGIES) -> dict[str, RetrievalResult]:
        """Run every strategy on the same query (for comparison/eval)."""
        return {
            strategy: self.retrieve(query, strategy=strategy, top_k=top_k, filters=filters)
            for strategy in strategies
        }
