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
import re

from dotenv import load_dotenv

from app.errors import ConfigError
from app.paths import CHROMA_DIR, DATA_DIR, ENV_FILE, PROJECT_ROOT

# Load .env from the project root regardless of the current working directory.
load_dotenv(ENV_FILE)


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value else default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {os.getenv(name)!r}") from exc


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {os.getenv(name)!r}") from exc


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

# --- LinkedIn integration (PLAN.md Step 5) --------------------------------
# The API version is *configuration*, not a literal in a request header.
# LinkedIn retires versions on a rolling cadence (roughly twelve months), so a
# version that works today stops working without any code change on our side.
# The default is the value the integration was proven against; bump it in .env
# rather than editing the client, and it is recorded on every attempt so a
# failure can be traced to the version that produced it.
LINKEDIN_API_VERSION = _env_str("LINKEDIN_API_VERSION", "202607")
if not re.fullmatch(r"\d{6}", LINKEDIN_API_VERSION):
    raise ConfigError(
        f"LINKEDIN_API_VERSION must look like YYYYMM, got {LINKEDIN_API_VERSION!r}"
    )

# Every LinkedIn request is bounded. There is no "no timeout" path: an
# unattended workflow that blocks forever on a socket is indistinguishable
# from one that has crashed, except that it holds the run lock (Step 12).
LINKEDIN_TIMEOUT_SECONDS = _env_float("LINKEDIN_TIMEOUT_SECONDS", 30.0)

# How long before expiry the credential starts being reported as
# EXPIRING_SOON. The token lives ~60 days, so two weeks of warning is several
# hundred scheduled runs of lead time — long enough to re-authorize by hand,
# which is the only remedy available while refresh is unverified (§5.2).
LINKEDIN_EXPIRY_WARNING_DAYS = _env_int("LINKEDIN_EXPIRY_WARNING_DAYS", 14)

# LinkedIn's own limit on post commentary length. Validated before the request
# so an oversized draft is classified as a validation failure instead of
# costing a round trip and a 400.
LINKEDIN_MAX_COMMENTARY_CHARS = _env_int("LINKEDIN_MAX_COMMENTARY_CHARS", 3000)

# OAuth application credentials. Present only so a refresh *can* be attempted
# if the stored credential ever carries a refresh token; publishing itself
# needs neither. Empty defaults: their absence is not an import-time error, it
# is an authentication failure the caller is told about.
LINKEDIN_CLIENT_ID = _env_str("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = _env_str("LINKEDIN_CLIENT_SECRET", "")

# --- Email notification (PLAN.md Step 7) ----------------------------------
# The transport is decided (SMTP, §12.1 decision 3); the *addresses* are not,
# and they are also not secrets the repository may hold. Every value here has
# an empty or neutral default, so the application imports and runs without any
# mail configuration — a run that never fails needs no notifier, and a run
# that fails without a notifier says so in its delivery record instead of
# crashing (app/notify/config.py). Validation is therefore lazy, like
# require_openrouter_key() below.
SMTP_HOST = _env_str("SMTP_HOST", "")
SMTP_PORT = _env_int("SMTP_PORT", 587)
SMTP_SENDER = _env_str("SMTP_SENDER", "")
SMTP_RECIPIENT = _env_str("SMTP_RECIPIENT", "")
SMTP_USERNAME = _env_str("SMTP_USERNAME", "")
# An app password for a Gmail account is a credential like any other: it comes
# from configuration and is redacted by the logging filter (see
# logging_config.known_secrets).
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD") or ""

#: How the connection is secured. ``starttls`` is submission on 587, ``ssl`` is
#: implicit TLS on 465, ``none`` is an unencrypted relay (a local one, or a
#: test double). Constrained here so a typo is a configuration error at import
#: rather than a silently unencrypted connection at send time.
SMTP_TLS_CHOICES = ("starttls", "ssl", "none")
SMTP_TLS = _env_str("SMTP_TLS", "starttls").strip().lower()
if SMTP_TLS not in SMTP_TLS_CHOICES:
    raise ConfigError(
        f"SMTP_TLS must be one of {', '.join(SMTP_TLS_CHOICES)}, got {SMTP_TLS!r}"
    )

# Every SMTP connection is bounded, for the same reason every LinkedIn request
# is: an unattended workflow blocked on a socket is indistinguishable from one
# that has crashed. A notification is best-effort infrastructure and may never
# hold a run open.
SMTP_TIMEOUT_SECONDS = _env_float("SMTP_TIMEOUT_SECONDS", 30.0)

# Noise control (PLAN.md Step 7): a failure that recurs every run must not
# produce an email every run. The *first* occurrence always notifies; repeats
# of the same failure inside this window do not.
SMTP_REPEAT_AFTER_HOURS = _env_float("SMTP_REPEAT_AFTER_HOURS", 24.0)


def require_openrouter_key() -> str:
    """Return the OpenRouter API key or raise ConfigError.

    Only multi-query retrieval needs the LLM; everything else works
    offline, so the key is validated lazily rather than at import time.
    """
    if not OPENROUTER_API_KEY:
        raise ConfigError(
            "OpenRouter API key missing: set OPENROUTER_API_KEY "
            "(OPENAI_API_KEY is accepted as an alias) in .env with an "
            "OpenRouter key (sk-or-v1-…). Needed for multi-query retrieval, "
            "generation, verification judging, and Agent reasoning; all other "
            "strategies run fully local."
        )
    return OPENROUTER_API_KEY
