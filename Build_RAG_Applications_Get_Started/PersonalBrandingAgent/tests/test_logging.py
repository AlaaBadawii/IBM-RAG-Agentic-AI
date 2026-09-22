"""Tests for logging: secrets must never appear in log output."""
import json
import logging

from app import paths
from app.logging_config import (
    REDACTED,
    SecretRedactionFilter,
    get_logger,
    setup_logging,
    token_file_secrets,
)


def _record(message: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg=message, args=(), exc_info=None,
    )


def test_redaction_filter_replaces_secret_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-or-v1-super-secret")
    redaction = SecretRedactionFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="Calling OpenRouter with key sk-or-v1-super-secret now",
        args=(), exc_info=None,
    )
    assert redaction.filter(record)
    assert "sk-or-v1-super-secret" not in record.getMessage()
    assert REDACTED in record.getMessage()


def test_the_linkedin_token_is_redacted_too(monkeypatch, tmp_path):
    """The token is a secret the environment never sees.

    It is written to disk by the OAuth script long after .env was last
    edited, so a filter built only from environment variables would let it
    through (PLAN.md Step 5, implementation approach 7).
    """
    token_file = tmp_path / "linkedin_tokens.json"
    token_file.write_text(json.dumps({"access_token": "the-live-token",
                                      "refresh_token": "the-refresh-token"}))
    monkeypatch.setattr(paths, "LINKEDIN_TOKEN_FILE", token_file)

    assert set(token_file_secrets()) == {"the-live-token", "the-refresh-token"}
    redaction = SecretRedactionFilter()
    record = _record("Authorization: Bearer the-live-token (refresh "
                     "the-refresh-token)")
    assert redaction.filter(record)
    assert "the-live-token" not in record.getMessage()
    assert "the-refresh-token" not in record.getMessage()


def test_a_missing_or_broken_token_file_never_breaks_logging(monkeypatch,
                                                            tmp_path):
    """Not having authorized yet is a normal state, not a logging failure."""
    monkeypatch.setattr(paths, "LINKEDIN_TOKEN_FILE", tmp_path / "absent.json")
    assert token_file_secrets() == []

    broken = tmp_path / "broken.json"
    broken.write_text("{ not json")
    monkeypatch.setattr(paths, "LINKEDIN_TOKEN_FILE", broken)
    assert token_file_secrets() == []

    SecretRedactionFilter()  # construction must not raise either


def test_the_smtp_password_is_redacted_too(monkeypatch):
    """Step 7 adds a credential to configuration; it must be covered like the rest.

    The app password authenticates the account that sends the alerts, so a
    filter that missed it would leak a live credential into the log the moment
    a mail server echoed it back.
    """
    from app.logging_config import known_secrets

    monkeypatch.setenv("SMTP_PASSWORD", "the-gmail-app-password")
    assert "the-gmail-app-password" in known_secrets()

    redaction = SecretRedactionFilter()
    record = _record("SMTPAuthenticationError: 535 rejected "
                     "the-gmail-app-password")
    assert redaction.filter(record)
    assert "the-gmail-app-password" not in record.getMessage()
    assert REDACTED in record.getMessage()


def test_redaction_filter_leaves_normal_messages():
    redaction = SecretRedactionFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="Ingested 71 files, 312 chunks", args=(), exc_info=None,
    )
    assert redaction.filter(record)
    assert record.getMessage() == "Ingested 71 files, 312 chunks"


def test_get_logger_attaches_filter_once():
    logger = get_logger("app.dedupe-check")
    first_count = len(logger.filters)
    get_logger("app.dedupe-check")  # second call must not duplicate filters
    assert len(logger.filters) == first_count


def test_setup_logging_is_idempotent():
    setup_logging()
    root = logging.getLogger()
    handler_count = len(root.handlers)
    setup_logging()  # second call must not add handlers again
    assert len(logging.getLogger().handlers) == handler_count
