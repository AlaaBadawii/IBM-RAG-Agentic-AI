"""Logging setup with secret redaction.

Rule: no secret value may ever reach a log line. A logging.Filter scans
formatted messages for known secret values (from env vars and the LinkedIn
token file) and replaces them with [REDACTED].

The same list is what values that never pass through a logger are scrubbed
with — a notification body, a recorded delivery error (``app/notify``). Two
lists would drift, and the one that drifts is the one that leaks, so
:func:`known_secrets` is the single definition and the filter is one consumer
of it.
"""
import json
import logging
import os
import sys

from app import paths
from app.paths import LOG_DIR

REDACTED = "[REDACTED]"
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

#: Environment variables whose *values* are secrets. Named here rather than
#: read inline so the set is visible in one place and a new credential cannot
#: be added to configuration without appearing in this table.
SECRET_ENV_VARS = (
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "LINKEDIN_CLIENT_ID",
    "LINKEDIN_CLIENT_SECRET",
    "SMTP_PASSWORD",
)


def token_file_secrets() -> list[str]:
    """Secret values held in the LinkedIn token file, if it is readable.

    The token is a secret the environment does not know about: it is written
    to disk by the OAuth script long after ``.env`` was last edited, so a
    filter built from environment variables alone would let it through. Read
    defensively — a missing or unreadable token file must never break logging,
    and it is a normal state (no credential has been created yet).
    """
    try:
        with open(paths.LINKEDIN_TOKEN_FILE, encoding="utf-8") as handle:
            tokens = json.load(handle)
    except (OSError, ValueError):
        return []
    if not isinstance(tokens, dict):
        return []
    return [
        value for key in ("access_token", "refresh_token", "id_token")
        if isinstance(value := tokens.get(key), str) and value
    ]


def known_secrets() -> list[str]:
    """Every secret value this process can recognise, as of right now.

    Read on each call rather than captured at import: a credential written to
    disk (or an environment variable patched in a test) has to be recognisable
    immediately afterwards, not at the next process start.
    """
    return [
        value for name in SECRET_ENV_VARS
        if (value := os.getenv(name))
    ] + token_file_secrets()


def redact(text: str, *extra: str | None) -> str:
    """Replace every known secret value in ``text`` with ``[REDACTED]``.

    Works on the *value*, not the variable name, so a secret interpolated into
    an f-string is still caught. ``extra`` carries secrets this process knows
    about but the environment does not — a password handed to a service
    directly rather than through configuration.
    """
    for secret in (*known_secrets(), *extra):
        if secret:
            text = text.replace(secret, REDACTED)
    return text


class SecretRedactionFilter(logging.Filter):
    """Replace occurrences of any known secret value with [REDACTED]."""

    def __init__(self) -> None:
        super().__init__()
        self._secrets: list[str] = known_secrets()

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
