"""Logging setup with secret redaction.

Rule: no secret value may ever reach a log line. A logging.Filter scans
formatted messages for known secret values (from env vars and the LinkedIn
token file) and replaces them with [REDACTED].
"""
import logging
import os
import sys

from app.paths import LOG_DIR

REDACTED = "[REDACTED]"
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class SecretRedactionFilter(logging.Filter):
    """Replace occurrences of any known secret value with [REDACTED].

    Works on the *value*, not the variable name, so a secret leaked into an
    f-string is still caught.
    """

    def __init__(self) -> None:
        super().__init__()
        self._secrets: list[str] = [
            v for v in (
                os.getenv("OPENAI_API_KEY"),
                os.getenv("OPENROUTER_API_KEY"),
                os.getenv("LINKEDIN_CLIENT_ID"),
                os.getenv("LINKEDIN_CLIENT_SECRET"),
            ) if v
        ]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for secret in self._secrets:
            if secret in message:
                message = message.replace(secret, REDACTED)
        record.msg = message
        record.args = ()
        return True


def get_logger(name: str) -> logging.Logger:
    """Return a logger with the redaction filter attached (idempotent)."""
    logger = logging.getLogger(name)
    if not any(isinstance(f, SecretRedactionFilter) for f in logger.filters):
        logger.addFilter(SecretRedactionFilter())
    return logger


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logging once: console + rotating file under logs/."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if root.handlers:  # already configured
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT))
    file_handler = logging.FileHandler(LOG_DIR / "app.log")
    file_handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(handler)
    root.addHandler(file_handler)
    root.setLevel(level)
    root.addFilter(SecretRedactionFilter())
