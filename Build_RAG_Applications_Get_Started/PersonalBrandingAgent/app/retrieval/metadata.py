"""Strategy 2: metadata-aware retrieval.

Deterministic, explicit filters — no LLM guessing. The caller states the
constraints; we translate them to Chroma `where` filters and combine them
with semantic search. The demo point:

    semantic relevance (what the text means)
        +
    structured filtering (what the document provably IS)

E.g. "verified evidence about backend engineering" becomes
    {"category": "evidence", "domain": "backend", "evidence_state": "VERIFIED"}
and then a vector search restricted to that slice of the corpus.
"""
from app.config import TOP_K
from app.retrieval.models import RetrievalResult
from app.retrieval.vector import VectorRetriever

# Fields a caller may filter on, mapped to Chroma metadata keys.
FILTERABLE_FIELDS = ("category", "domain", "status", "evidence_state",
                     "document_type", "project")


class MetadataRetriever:
    """Vector retrieval + explicit metadata constraints."""

    def __init__(self, vector_retriever: VectorRetriever | None = None):
        self._vector = vector_retriever or VectorRetriever()

    def retrieve(self, query: str, top_k: int = TOP_K,
                 filters: dict | None = None) -> RetrievalResult:
        """Run semantic search restricted by explicit metadata filters.

        Args:
            filters: only the keys in FILTERABLE_FIELDS are allowed;
                unknown keys raise ValueError (fail loudly rather than
                silently ignoring a typo like 'evidenceState').
        """
        chroma_filter = build_filter(filters or {})
        result = self._vector.retrieve(query, top_k=top_k, filter=chroma_filter)
        result.strategy = "metadata"
        for doc in result.documents:
            doc.strategy = "metadata"
        result.diagnostics = {
            **result.diagnostics,
            "filters_applied": filters or {},
            "chroma_where": chroma_filter,
            "note": "vector search restricted to documents matching all filters",
        }
        return result


def build_filter(filters: dict) -> dict | None:
    """Translate caller filters to a Chroma `where` clause.

    Multiple filters are AND-ed ($and). Values are matched exactly —
    metadata-aware retrieval is about precision, not fuzzy matching.
    """
    if not filters:
        return None
    unknown = set(filters) - set(FILTERABLE_FIELDS)
    if unknown:
        raise ValueError(
            f"Unknown filter field(s): {sorted(unknown)}. "
            f"Allowed: {FILTERABLE_FIELDS}"
        )
    clauses = [{key: {"$eq": value}} for key, value in filters.items()]
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}
