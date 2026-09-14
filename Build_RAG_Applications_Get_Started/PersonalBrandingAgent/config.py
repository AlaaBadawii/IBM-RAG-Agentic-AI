"""Backwards-compatible re-export of app.config.

The real configuration lives in app/config.py (see Phase 1 of PLAN.md);
this module only re-exports it so existing imports keep working.
"""
from app.config import (  # noqa: F401
    CHROMA_COLLECTION,
    CHROMA_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DATA_DIR,
    EMBEDDING_MODEL,
    EXCLUDE_READMES,
    GENERATION_PARAMS,
    HYBRID_CANDIDATES,
    MODEL_ID,
    MULTI_QUERY_COUNT,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    RERANKER_MODEL,
    RRF_K,
    TOP_K,
    require_openrouter_key,
)

# Kept for compatibility with the original config.py.
OPENAI_API_KEY = OPENROUTER_API_KEY
