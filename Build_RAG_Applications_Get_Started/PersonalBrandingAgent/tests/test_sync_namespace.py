"""Unit tests for the synchronization namespace (``PLAN.md`` Step 3).

``app/sync/namespace.py`` is a correctness device: it is what lets the corpus
and 29 registered sources share one Chroma collection without either being able
to damage the other (``app/sync/namespace.py``, module docstring). These tests
pin its two existing guarantees and the accessor Step 4 added, so a change to
the prefix or the separator fails here rather than in a run against real data.

``source_name_from_key`` is the one addition Step 4 made to Step 3. It is
tested alongside the functions it inverts because the round trip — not either
half — is the property the context layer depends on.
"""
import pytest

from app.errors import SyncError
from app.sync.namespace import (
    NAMESPACE_PREFIX,
    assert_namespace_safe,
    is_source_key,
    source_key,
    source_name_from_key,
    source_namespace,
)


def test_a_source_key_is_namespaced_and_names_its_source():
    key = source_key("quizey-v2", "src/api/main.py")
    assert key == f"{NAMESPACE_PREFIX}quizey-v2/src/api/main.py"
    assert is_source_key(key)
    assert source_name_from_key(key) == "quizey-v2"


def test_a_corpus_path_is_not_a_source_key_and_names_no_source():
    """``data/`` documents must not be able to look like a registered source.

    ``evidence/backend/fastapi.md`` is a curated claim; the context layer files
    it under the corpus, and a source name invented for it would let a corpus
    document masquerade as a synchronized repository.
    """
    for corpus_path in ("evidence/backend/fastapi.md", "completed_projects/quizey.md",
                        "README.md"):
        assert not is_source_key(corpus_path)
        assert source_name_from_key(corpus_path) is None


def test_the_source_name_is_recovered_without_swallowing_the_path():
    """The separator is what stops one source's namespace matching another's."""
    assert source_name_from_key("@source/ai-agents/x.md") == "ai-agents"
    assert source_name_from_key("@source/ai/x.md") == "ai"
    assert source_name_from_key(source_key("ai", "nested/deep/file.py")) == "ai"


def test_a_key_that_names_no_source_yields_none_rather_than_raising():
    """Total, because it runs over metadata that came from a retrieval result."""
    assert source_name_from_key("@source/") is None
    assert source_name_from_key("") is None


def test_the_published_guarantees_of_the_namespace_are_unchanged():
    """What Step 2 and Step 3 already relied on, restated as a regression."""
    assert source_namespace("ai") == "@source/ai/"
    # A name that would make the namespace ambiguous is refused, not escaped.
    for bad in ("", "   ", "a/b", "a\\b", "@source"):
        with pytest.raises(SyncError):
            assert_namespace_safe(bad)
    # A path that escapes its source root is not a candidate at all.
    for bad in ("/etc/passwd", "../outside.md", ""):
        with pytest.raises(SyncError):
            source_key("ai", bad)
