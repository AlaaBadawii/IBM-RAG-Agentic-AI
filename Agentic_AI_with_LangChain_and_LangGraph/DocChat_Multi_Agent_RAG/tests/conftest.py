"""Offline-safe pytest configuration for the DocChat DocumentProcessor tests.

The logging module writes ``app.log`` relative to the working directory, so
the session starts inside a temporary directory before any project module is
imported. No real Docling model downloads or external services are needed:
every conversion is mocked except one small real `.md` conversion.
"""

import os
import sys
import tempfile
from pathlib import Path

_SESSION_TMPDIR = tempfile.mkdtemp(prefix="docchat-tests-")
os.chdir(_SESSION_TMPDIR)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402

from config.settings import settings  # noqa: E402


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    """Isolate the document cache so tests never touch the real cache."""
    target = tmp_path / "document_cache"
    monkeypatch.setattr(settings, "CACHE_DIR", str(target))
    return target


@pytest.fixture
def processor(cache_dir):
    from document_processor.file_handler import DocumentProcessor

    return DocumentProcessor()
