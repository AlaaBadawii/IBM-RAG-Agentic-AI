"""Central configuration.

All values come from environment variables (loaded from PROJECT_ROOT/.env)
with explicit defaults, so tests and local dev work without secrets.

Secrets note:
    The OpenRouter key is read from OPENAI_API_KEY for backwards
    compatibility with the original repo config, and optionally from
    OPENROUTER_API_KEY. It is *the OpenRouter key* — the name is historical,
    the client is OpenAI-compatible talking to OpenRouter
    (https://openrouter.ai/api/v1). Never log it (see logging_config).
"""
import os

from dotenv import load_dotenv

from app.errors import ConfigError
from app.paths import CHROMA_DIR, DATA_DIR, PROJECT_ROOT

# Load .env from the project root regardless of the current working directory.
load_dotenv(PROJECT_ROOT / ".env")


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value else default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {os.getenv(name)!r}") from exc


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# --- LLM (OpenRouter, OpenAI-compatible client) ---------------------------
# The key name OPENAI_API_KEY is kept for compatibility; it holds an
# OpenRouter key (sk-or-v1-...). OPENROUTER_API_KEY is also accepted.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
OPENROUTER_BASE_URL = _env_str("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL_ID = _env_str("MODEL_ID", "deepseek/deepseek-v4-flash")
# OpenAI-compatible generation parameters (NOT Watsonx-style max_new_tokens).
GENERATION_PARAMS = {
    "max_tokens": _env_int("MAX_TOKENS", 800),
    "temperature": float(_env_str("TEMPERATURE", "0.7")),
}

# --- Embeddings / reranking (local, no API cost) --------------------------
EMBEDDING_MODEL = _env_str(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
RERANKER_MODEL = _env_str(
    "RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
)

# --- Vector store ---------------------------------------------------------
CHROMA_DIR = CHROMA_DIR
CHROMA_COLLECTION = _env_str("CHROMA_COLLECTION", "personal_kb")

# --- Ingestion ------------------------------------------------------------
DATA_DIR = DATA_DIR
CHUNK_SIZE = _env_int("CHUNK_SIZE", 1000)
CHUNK_OVERLAP = _env_int("CHUNK_OVERLAP", 200)
# README.md files inside data/ are category *indexes* that duplicate the
# content-file summaries. Default policy: exclude them from the corpus.
# Flip with EXCLUDE_READMES=false to see how index noise affects retrieval.
EXCLUDE_READMES = _env_bool("EXCLUDE_READMES", True)

# --- Retrieval defaults ---------------------------------------------------
TOP_K = _env_int("TOP_K", 5)
# Hybrid retrieval: candidates pulled from EACH strategy before RRF fusion.
HYBRID_CANDIDATES = _env_int("HYBRID_CANDIDATES", 10)
# RRF constant: RRF(d) = sum over lists of 1 / (rank + K). 60 is the standard
# value from the original RRF paper (Cormack et al., 2009).
RRF_K = _env_int("RRF_K", 60)
# Multi-query: how many rewritten queries the LLM should generate.
MULTI_QUERY_COUNT = _env_int("MULTI_QUERY_COUNT", 4)


def require_openrouter_key() -> str:
    """Return the OpenRouter API key or raise ConfigError.

    Only multi-query retrieval needs the LLM; everything else works
    offline, so the key is validated lazily rather than at import time.
    """
    if not OPENROUTER_API_KEY:
        raise ConfigError(
            "OpenRouter API key missing: set OPENAI_API_KEY (or "
            "OPENROUTER_API_KEY) in .env. Only needed for multi-query "
            "retrieval; all other strategies run fully local."
        )
    return OPENROUTER_API_KEY
