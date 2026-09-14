"""Strategy 3: BM25 lexical retrieval (rank_bm25).

Why BM25 exists alongside vector search:

    Vector search: meaning / semantic similarity
        "backend architecture" matches "how I layered a FastAPI service"
        even though no word repeats.

    BM25: exact terminology / lexical matching
        "PyMongo" matches the chunks that literally contain "PyMongo",
        with scoring informed by term frequency, inverse document
        frequency, and document length normalization.

BM25 here runs over the SAME chunks stored in Chroma (fetched once via
Chroma.get), so vector and BM25 are always comparing the same universe of
documents — that's what makes RRF fusion meaningful.

Score semantics: BM25 scores are unbounded positive numbers (higher =
better) and are NOT comparable to cosine distances or cross-encoder
scores. Compare rankings only.
"""
import re
import time
from functools import lru_cache

from rank_bm25 import BM25Okapi

from app.config import TOP_K
from app.logging_config import get_logger
from app.retrieval.models import RetrievedDocument, RetrievalResult
from app.retrieval.vector import VectorRetriever

logger = get_logger(__name__)

def _rank_scores(scores: list[float]) -> list[tuple[float, int]]:
    """Order (score, corpus_index) best-first, keeping nonzero scores only.

    Zero scores mean the query shares no term with the chunk — genuinely
    irrelevant, safe to drop. Negative scores (see note in retrieve) stay.
    """
    return sorted(
        ((score, i) for i, score in enumerate(scores) if score != 0),
        key=lambda pair: pair[0],
        reverse=True,
    )


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens — simple, deterministic, no stopwords.

    Deliberately visible: tokenization is the load-bearing choice in BM25.
    """
    return _TOKEN_PATTERN.findall(text.lower())


class BM25Retriever:
    """BM25 over the ingested corpus chunks."""

    def __init__(self, store=None):
        self._store = store
        self._bm25 = None

    @property
    def store(self):
        if self._store is None:
            self._store = VectorRetriever().store
        return self._store

    def _build_index(self):
        """Fetch all chunks from Chroma and index them with BM25."""
        result = self.store.get(include=["documents", "metadatas"])
        self._chunk_ids = list(result["ids"])
        self._docs = list(result["documents"])
        self._metas = [m or {} for m in result["metadatas"]]
        self._tokens = [tokenize(doc) for doc in self._docs]
        self._bm25 = BM25Okapi(self._tokens)
        logger.info("BM25 index built over %d chunks", len(self._docs))

    def retrieve(self, query: str, top_k: int = TOP_K) -> RetrievalResult:
        started = time.perf_counter()
        if self._bm25 is None:  # never built (or invalidate() was called)
            self._build_index()
        scores = self._bm25.get_scores(tokenize(query))
        elapsed_ms = (time.perf_counter() - started) * 1000

        # NOTE: BM25 scores can be NEGATIVE for terms that appear in (nearly)
        # every document — IDF goes to zero/negative when a term is
        # corpus-wide. Such chunks are still lexically matched, just weakly;
        # keep them but rank below positive scores.
        ranked = _rank_scores(scores)[:top_k]

        documents = []
        for rank, (score, i) in enumerate(ranked, start=1):
            meta = self._metas[i]
            documents.append(
                RetrievedDocument(
                    content=self._docs[i],
                    score=float(score),
                    source=meta.get("source", "unknown"),
                    metadata=meta,
                    strategy="bm25",
                    chunk_id=self._chunk_ids[i],
                    rank=rank,
                )
            )
        return RetrievalResult(
            query=query,
            strategy="bm25",
            documents=documents,
            diagnostics={
                "latency_ms": round(elapsed_ms, 1),
                "corpus_chunks": len(self._docs),
                "chunks_with_nonzero_score": int((scores > 0).sum()),
                "score_semantics": "BM25 lexical score (higher = better, unbounded)",
            },
        )

    def invalidate(self) -> None:
        """Force index rebuild on next retrieve (after re-ingestion)."""
        self._index = None
        self._bm25 = None

    # Exposed for hybrid retrieval: full scored ranking, no top_k cut.
    def rank_all(self, query: str) -> list[tuple[float, int]]:
        """Return (score, corpus_index) for every chunk with score > 0,
        best first — used by fusion to build the BM25 ranking list."""
        if self._bm25 is None:
            self._build_index()
        scores = self._bm25.get_scores(tokenize(query))
        return _rank_scores(scores)
