"""Environment-based configuration.

All credentials and tunable knobs live here so the rest of the application never
reads the environment directly. ``load_config`` is called per request, so editing
``.env`` takes effect without restarting the app.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct"

# Keep the first version practical: every additional item lengthens both the
# lesson and the audio. Override with the MAX_VOCABULARY_ITEMS env var.
DEFAULT_MAX_VOCABULARY_ITEMS = 15
DEFAULT_REQUEST_TIMEOUT = 120


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or unusable."""


@dataclass(frozen=True)
class Config:
    """Resolved application configuration."""

    api_key: str
    base_url: str
    model: str
    max_vocabulary_items: int
    request_timeout: int


def _positive_int(raw: str | None, default: int) -> int:
    """Parse a positive integer from the environment, falling back to a default."""
    if not raw:
        return default
    try:
        value = int(raw.strip())
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def load_config() -> Config:
    """Read configuration from the environment, raising ConfigError if unusable."""
    load_dotenv()

    api_key = (os.getenv("LLM_API_KEY") or "").strip()
    if not api_key:
        raise ConfigError(
            "LLM_API_KEY is not set. Copy .env.example to .env and add your API key."
        )

    base_url = (os.getenv("LLM_BASE_URL") or "").strip().rstrip("/") or DEFAULT_BASE_URL
    model = (os.getenv("LLM_MODEL") or "").strip() or DEFAULT_MODEL

    return Config(
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_vocabulary_items=_positive_int(
            os.getenv("MAX_VOCABULARY_ITEMS"), DEFAULT_MAX_VOCABULARY_ITEMS
        ),
        request_timeout=_positive_int(
            os.getenv("LLM_REQUEST_TIMEOUT"), DEFAULT_REQUEST_TIMEOUT
        ),
    )
