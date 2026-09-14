"""Exception hierarchy for the application.

Keeping errors typed lets CLIs and tests distinguish "configuration problem"
from "ingestion problem" from "retrieval problem" without string matching.
"""


class AppError(Exception):
    """Base class for all application errors."""


class ConfigError(AppError):
    """Raised when required configuration (e.g. an API key) is missing."""


class IngestionError(AppError):
    """Raised when the data/ -> Chroma pipeline fails."""


class RetrievalError(AppError):
    """Raised when a retrieval strategy fails (missing index, bad filter...)."""
