"""Strategy 1: vector (semantic) retrieval over Chroma.

Mechanism, made explicit:

    query text
        -> embedding model (all-MiniLM-L6-v2)
        -> Chroma compares against all stored chunk embeddings (cosine)
        -> top_k nearest chunks, ranked by distance

Implementation note: we query the underlying Chroma collection directly
(`store._collection.query`) instead of LangChain's
`similarity_search_with_score`, because the raw collection API returns the
stored document IDS — and stable ids are what lets fusion/dedup recognize
"the same chunk" across strategies. The LangChain Document-returning API
discards them.
"""
import time

from app.config import TOP_K
from app.ingestion.pipeline import get_embeddings, get_vector_store
from app.logging_config import get_logger
from app.retrieval.models import RetrievedDocument, RetrievalResult

logger = get_logger(__name__)


class VectorRetriever:
    """Semantic similarity search over the ingested corpus."""

    def __init__(self, store=None, embeddings=None):
        self._store = store
        # When a store is injected, its embedding function is authoritative
        # (tests inject a store whose embedding_function is FakeEmbeddings).
        self._embeddings = embeddings

    @property
    def store(self):
        if self._store is None:
            self._store = get_vector_store()
        return self._store

    def _embed_query(self, query: str) -> list[float]:
        if self._embeddings is not None:
            return self._embeddings.embed_query(query)
        # Fall back to the store's own embedding function (correct even
        # when store and default embeddings differ).
        ef = self.store._embedding_function
        if ef is not None:
            return ef.embed_query(query)
        return get_embeddings().embed_query(query)

    def retrieve(self, query: str, top_k: int = TOP_K,
                 filter: dict | None = None) -> RetrievalResult:
        """Embed the query and search Chroma.

        Args:
            query: user question.
            top_k: number of results.
            filter: optional Chroma `where` filter (see metadata.py) —
                used directly by the metadata-aware strategy.
        """
        started = time.perf_counter()
        query_embedding = self._embed_query(query)
        response = self.store._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter,
            include=["documents", "metadatas", "distances"],
        )
        elapsed_ms = (time.perf_counter() - started) * 1000

        ids = response["ids"][0]
        docs = response["documents"][0]
        metas = response["metadatas"][0] or [{}] * len(docs)
        distances = response["distances"][0]

        documents = [
            RetrievedDocument(
                content=doc,
                score=float(distance),
                source=(meta or {}).get("source", "unknown"),
                metadata=meta or {},
                strategy="vector",
                chunk_id=chunk_id,
                rank=rank,
            )
            for rank, (chunk_id, doc, meta, distance) in enumerate(
                zip(ids, docs, metas, distances), start=1
            )
        ]
        return RetrievalResult(
            query=query,
            strategy="vector",
            documents=documents,
            diagnostics={
                "latency_ms": round(elapsed_ms, 1),
                "k_requested": top_k,
                "filter": filter,
                "score_semantics": "cosine distance (lower = more similar)",
            },
        )
