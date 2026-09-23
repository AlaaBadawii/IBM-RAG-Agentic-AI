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

    def __init__(self, store=None, embeddings=None, scope=None):
        self._store = store
        # When a store is injected, its embedding function is authoritative
        # (tests inject a store whose embedding_function is FakeEmbeddings).
        self._embeddings = embeddings
        # A restriction on which chunks this retriever may see at all. Held
        # rather than passed per call, so every caller of this retriever —
        # including the strategies that wrap it — inherits it.
        self._scope = scope

    @property
    def scope(self):
        """The corpus this retriever is restricted to, or ``None``."""
        return self._scope

    @property
    def store(self):
        if self._store is None:
            self._store = get_vector_store()
        return self._store

    def _effective_filter(self, filter: dict | None) -> dict | None:
        """The caller's filter, narrowed by this retriever's scope.

        The two are AND-ed rather than one replacing the other: a scope is a
        statement about which corpus is being searched, and a caller's filter
        is a statement about which documents within it are wanted. Dropping
        either would answer a different question than the one asked — and
        silently, since the results would still look plausible.
        """
        if self._scope is None or self._scope.where is None:
            return filter
        if filter is None:
            return self._scope.where
        return {"$and": [self._scope.where, filter]}

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
                used directly by the metadata-aware strategy. Combined with
                this retriever's scope when it has one.
        """
        started = time.perf_counter()
        effective_filter = self._effective_filter(filter)
        query_embedding = self._embed_query(query)
        response = self.store._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=effective_filter,
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
                "scope": self._scope.name if self._scope is not None else None,
                "effective_filter": effective_filter,
                "score_semantics": "cosine distance (lower = more similar)",
            },
        )
