"""Strategy 4: multi-query retrieval (OpenRouter LLM).

The vocabulary-gap problem: a user asks "What evidence supports my backend
engineering skills?" but the corpus says "FastAPI shipment API", "SQLAlchemy
models", "Alembic migrations". One embedding of the original query can miss
documents phrased differently.

Mechanism:

    original query
        -> LLM rewrites it into N different phrasings/angles
        -> vector retrieval for EACH query
        -> union of results, deduplicated by stable chunk identity
        -> ranked by best rank achieved across queries

The LLM is called through the OpenAI-compatible client pointed at
OpenRouter. A deterministic fallback (the original query only) keeps the
strategy usable when the API call fails.
"""
import time

from langchain_openai import ChatOpenAI

from app import config
from app.logging_config import get_logger
from app.retrieval.models import RetrievedDocument, RetrievalResult
from app.retrieval.vector import VectorRetriever

logger = get_logger(__name__)

_MULTI_QUERY_PROMPT = (
    "You are a search query rewriter for a personal knowledge base about "
    "an engineer's projects, certificates, evidence, and lessons.\n"
    "Rewrite the user's question as {n} alternative search queries, each "
    "phrased differently (different vocabulary, different angle).\n"
    "Return ONLY the queries, one per line, no numbering, no extra text.\n\n"
    "Question: {question}"
)


def _make_llm() -> ChatOpenAI:
    """OpenAI-compatible client pointed at OpenRouter (not Watsonx)."""
    return ChatOpenAI(
        api_key=config.require_openrouter_key(),
        base_url=config.OPENROUTER_BASE_URL,
        model=config.MODEL_ID,
        temperature=0.0,  # query rewriting wants determinism, not creativity
        max_tokens=300,
    )


class MultiQueryRetriever:
    """Expands one query into N queries via OpenRouter, then vector-retrieves
    each and merges the results."""

    def __init__(self, vector_retriever: VectorRetriever | None = None, llm=None):
        self._vector = vector_retriever or VectorRetriever()
        self._llm = llm  # injectable for tests (fake LLM)

    def _get_llm(self):
        return self._llm if self._llm is not None else _make_llm()

    def generate_queries(self, question: str, n: int = None) -> list[str]:
        """Ask the LLM for n query rewrites. Falls back to [question] on any
        failure — the strategy must degrade, never crash, without the API."""
        n = n or config.MULTI_QUERY_COUNT
        if self._llm is None:
            # Real path: needs a key. If absent, fall back deterministically.
            try:
                config.require_openrouter_key()
            except Exception:
                logger.warning("No OpenRouter key; multi-query falls back to original query")
                return [question]
        try:
            response = self._get_llm().invoke(
                _MULTI_QUERY_PROMPT.format(n=n, question=question)
            )
            text = response.content if hasattr(response, "content") else str(response)
            queries = [
                line.strip().lstrip("0123456789.-) ")
                for line in text.splitlines()
                if line.strip()
            ]
            # Keep only the first n lines; drop the question echoed back.
            queries = [q for q in queries if q.lower() != question.lower()][:n]
            if not queries:
                return [question]
            return queries
        except Exception as exc:
            logger.warning("Multi-query LLM call failed (%s); using original query", exc)
            return [question]

    def retrieve(self, query: str, top_k: int = None,
                 n_queries: int = None) -> RetrievalResult:
        top_k = top_k or config.TOP_K
        n_queries = n_queries or config.MULTI_QUERY_COUNT
        started = time.perf_counter()

        generated = self.generate_queries(query, n=n_queries)
        # The original query is always included — the LLM rewrites
        # supplement it, never replace it.
        all_queries = [query] + generated

        per_query: dict[str, list[RetrievedDocument]] = {}
        by_chunk: dict[str, tuple[int, RetrievedDocument]] = {}  # best rank per chunk

        for q in all_queries:
            result = self._vector.retrieve(q, top_k=top_k)
            per_query[q] = result.documents
            for doc in result.documents:
                key = doc.chunk_id or doc.source  # stable identity
                current = by_chunk.get(key)
                if current is None or doc.rank < current[0]:
                    by_chunk[key] = (doc.rank, doc)

        # Rank merged results by their best rank in any single query.
        merged = sorted(by_chunk.values(), key=lambda pair: pair[0])
        documents = []
        for final_rank, (best_rank, doc) in enumerate(merged, start=1):
            documents.append(
                RetrievedDocument(
                    content=doc.content,
                    score=doc.score,
                    source=doc.source,
                    metadata=doc.metadata,
                    strategy="multi_query",
                    chunk_id=doc.chunk_id,
                    rank=final_rank,
                )
            )
        elapsed_ms = (time.perf_counter() - started) * 1000
        return RetrievalResult(
            query=query,
            strategy="multi_query",
            documents=documents,
            diagnostics={
                "latency_ms": round(elapsed_ms, 1),
                "generated_queries": generated,
                "all_queries": all_queries,
                "unique_documents": len(documents),
                "llm_fallback_used": generated == [query],
                "score_semantics": "cosine distance (lower = more similar); rank = best rank across queries",
            },
        )
