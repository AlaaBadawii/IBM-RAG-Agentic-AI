"""The bounded repair pass for stale opportunity snapshots (Phase 2).

The incident left opportunities whose frozen evidence was a document's
catalogue tail (``## Evidence`` path lists, ``Story strength``) — a snapshot
no writer can ground a post in. ``repair`` re-derives those snapshots from
the live chunk store without a model or network call, and never moves
lifecycle state.

All state is isolated per test (temporary stores); the production database
is never touched.
"""
import pytest

from app.opportunities.backlog import (
    EVIDENCE_SNAPSHOT_VERSION,
    opportunity_fingerprint,
)
from app.opportunities.repair import (
    apply_repairs,
    chroma_chunk_source,
    plan_repairs,
    rebuild_snapshot,
)
from app.state import OpportunityStatus, StateStore

NARRATIVE = (
    "## Context\nCI kept failing on a flaky environment step.\n"
    "## Problem\nRed builds blocked every merge.\n"
    "## What I Did\nI isolated the environment setup and pinned it.\n"
)
CATALOG = (
    "## Evidence\n- stories_lessons/ci.md\n- app/ci/config.py\n\n"
    "**Story strength:** 4/5\n**Reason:** strong, recent, verifiable.\n"
)
CATALOG_2 = (
    "## Content Potential\n- angle one\n- angle two\n\n"
    "**Story strength:** 4/5\n**Reason:** strong.\n"
)


def _chunk(source, digest, index, content):
    return {
        "source": source,
        "chunk_id": f"{digest}:{index}",
        "content": content,
        "metadata": {
            "source": source,
            "content_hash": digest,
            "category": "stories_lessons",
            "evidence_state": "DOCUMENTED",
        },
    }


def _source(*chunks):
    by_digest: dict[str, list[dict]] = {}
    for chunk in chunks:
        by_digest.setdefault(chunk["metadata"]["content_hash"], []).append(chunk)
    return lambda digest: by_digest.get(digest, [])


@pytest.fixture
def store(tmp_path):
    with StateStore(tmp_path / "repair.db") as state:
        yield state


def _enqueue_bad(store, source="stories_lessons/ci.md", digest="cafe"):
    evidence = [{
        "source": source,
        "chunk_id": f"{digest}:2",
        "content_hash": digest,
        "evidence_state": "DOCUMENTED",
        "category": "stories_lessons",
        "document_type": "lesson",
        "content": CATALOG,
    }]
    fingerprint = opportunity_fingerprint("Story", [(source, digest)])
    return store.enqueue_opportunity(fingerprint, "Story", evidence)


INCIDENT_SOURCE = _source(
    _chunk("stories_lessons/ci.md", "cafe", 0, NARRATIVE),
    _chunk("stories_lessons/ci.md", "cafe", 1, NARRATIVE),
    _chunk("stories_lessons/ci.md", "cafe", 2, CATALOG),
)


# --------------------------------------------------------------- rebuild ---

def test_rebuild_prefers_the_narrative_chunk_over_the_catalogue_tail():
    rebuilt = rebuild_snapshot(
        [{"content_hash": "cafe", "chunk_id": "cafe:2", "content": CATALOG}],
        INCIDENT_SOURCE)
    assert [s["chunk_id"] for s in rebuilt] == ["cafe:0", "cafe:1"]
    assert all("Evidence" not in s["content"] for s in rebuilt)


def test_rebuild_keeps_a_document_it_cannot_replace():
    stored = {"content_hash": "gone", "chunk_id": "gone:2", "content": CATALOG}
    rebuilt = rebuild_snapshot([stored], _source())
    assert rebuilt == [stored]


def test_rebuild_keeps_original_when_no_narrative_chunk_exists():
    only_catalogue = _source(
        _chunk("stories_lessons/ci.md", "cafe", 0, CATALOG),
        _chunk("stories_lessons/ci.md", "cafe", 1, CATALOG_2),
    )
    stored = {"content_hash": "cafe", "chunk_id": "cafe:0", "content": CATALOG}
    assert rebuild_snapshot([stored], only_catalogue) == [stored]


def test_rebuild_is_deterministic_and_deduplicated():
    stored = [
        {"content_hash": "cafe", "chunk_id": "cafe:2", "content": CATALOG},
        {"content_hash": "cafe", "chunk_id": "cafe:2", "content": CATALOG},
    ]
    rebuilt = rebuild_snapshot(stored, INCIDENT_SOURCE)
    assert [s["chunk_id"] for s in rebuilt] == ["cafe:0", "cafe:1"]


# ----------------------------------------------------------------- plan ---

def test_plan_finds_the_incident_row_and_names_the_change(store):
    row = _enqueue_bad(store)
    candidates = plan_repairs(store, INCIDENT_SOURCE)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.opportunity.opportunity_id == row.opportunity_id
    assert candidate.changed
    assert candidate.before_is_narrative is False
    assert candidate.before_chunk_ids == ("cafe:2",)
    assert candidate.after_chunk_ids == ("cafe:0", "cafe:1")


def test_plan_ignores_rows_already_at_the_current_policy(store):
    row = _enqueue_bad(store)
    store.refresh_opportunity_snapshot(
        row.opportunity_id, [dict(e) for e in row.evidence],
        snapshot_version=EVIDENCE_SNAPSHOT_VERSION)
    assert plan_repairs(store, INCIDENT_SOURCE) == []


def test_plan_never_touches_terminal_rows(store):
    row = _enqueue_bad(store)
    store.finalize_opportunity(row.opportunity_id, OpportunityStatus.REJECTED)
    assert plan_repairs(store, INCIDENT_SOURCE) == []


def test_plan_reports_an_unchanged_stale_row(store):
    # A row on the old policy whose document only ever had catalogue chunks.
    only_catalogue = _source(
        _chunk("stories_lessons/thin.md", "beef", 0, CATALOG),
        _chunk("stories_lessons/thin.md", "beef", 1, CATALOG_2),
    )
    _enqueue_bad(store, source="stories_lessons/thin.md", digest="beef")
    candidates = plan_repairs(store, only_catalogue)
    assert len(candidates) == 1
    assert not candidates[0].changed


# ---------------------------------------------------------------- apply ---

def test_apply_defaults_to_a_dry_run(store):
    row = _enqueue_bad(store)
    apply_repairs(store, INCIDENT_SOURCE)
    after = store.get_opportunity(row.opportunity_id)
    assert after.evidence[0]["chunk_id"] == "cafe:2"
    assert after.snapshot_version != EVIDENCE_SNAPSHOT_VERSION


def test_apply_rewrites_to_narrative_without_moving_lifecycle(store):
    row = _enqueue_bad(store)
    store.record_opportunity_decision(
        row.opportunity_id, "deferred", attempts_increment=1)

    applied = apply_repairs(store, INCIDENT_SOURCE, dry_run=False)

    assert len(applied) == 1 and applied[0].changed
    after = store.get_opportunity(row.opportunity_id)
    assert [e["chunk_id"] for e in after.evidence] == ["cafe:0", "cafe:1"]
    assert after.snapshot_version == EVIDENCE_SNAPSHOT_VERSION
    assert after.status is OpportunityStatus.QUEUED
    assert after.attempts == 1
    assert after.last_decision == "deferred"


def test_apply_skips_unchanged_rows(store):
    only_catalogue = _source(
        _chunk("stories_lessons/thin.md", "beef", 0, CATALOG),
        _chunk("stories_lessons/thin.md", "beef", 1, CATALOG_2),
    )
    row = _enqueue_bad(store, source="stories_lessons/thin.md", digest="beef")
    before_hash = store.get_opportunity(row.opportunity_id).snapshot_hash

    apply_repairs(store, only_catalogue, dry_run=False)

    after = store.get_opportunity(row.opportunity_id)
    assert after.snapshot_hash == before_hash
    assert after.snapshot_version != EVIDENCE_SNAPSHOT_VERSION


# ----------------------------------------------------------- chroma glue ---

class _FakeVectorStore:
    def __init__(self, stored):
        self._stored = stored

    def get(self, *, where, include):
        self.called_with = (where, include)
        return self._stored


def test_chroma_chunk_source_maps_a_store_result():
    stored = {
        "ids": ["cafe:0"],
        "documents": [NARRATIVE],
        "metadatas": [{"source": "stories_lessons/ci.md",
                       "content_hash": "cafe"}],
    }
    source = chroma_chunk_source(_FakeVectorStore(stored))
    rows = source("cafe")
    assert rows == [{
        "source": "stories_lessons/ci.md",
        "chunk_id": "cafe:0",
        "content": NARRATIVE,
        "metadata": {"source": "stories_lessons/ci.md",
                     "content_hash": "cafe"},
    }]


def test_chroma_chunk_source_swallows_store_failure():
    class _Broken:
        def get(self, *, where, include):
            raise RuntimeError("no collection")

    assert chroma_chunk_source(_Broken())("cafe") == []
    assert chroma_chunk_source(_FakeVectorStore({}))("") == []
