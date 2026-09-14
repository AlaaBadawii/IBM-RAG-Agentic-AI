"""Tests for logging: secrets must never appear in log output."""
import logging

from app.logging_config import REDACTED, SecretRedactionFilter, get_logger, setup_logging


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
