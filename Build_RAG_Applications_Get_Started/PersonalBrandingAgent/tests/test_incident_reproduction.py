"""The 2026-10-17 incident, reproduced against its own bytes, and closed.

The incident was a chain, and a regression in any link reopens it:

1. retrieval ranked the metadata footer of a story above the story, so the
   persisted opportunity held only an index card;
2. the fingerprint froze that card forever, so a rebuild never happened;
3. the writer could not produce a post from a list of file paths and declined.

Each unit test owns a link. This one walks the chain end to end on the three
real chunks of ``stories_lessons/ci_failures_are_environment_not_code.md`` —
the chunks the incident actually persisted — so the fix is proven against the
input that broke it, offline and without publishing.
"""
from types import SimpleNamespace

from app.agent.prompt import resolve_topic
from app.context.evidence_roles import has_narrative, is_catalog_only
from app.context.models import ContextItem
from app.opportunities.backlog import (
    EVIDENCE_SNAPSHOT_VERSION,
    opportunity_fingerprint,
    persist_discoveries,
)

# --- the three real chunks (trimmed), as the incident persisted them ---------

CHUNK_1 = """## Decision / Insight

When CI is red, check **cwd, PATH, PYTHONPATH, and the environment** before
suspecting the app logic.

## Result

The pipeline turned green after aligning the invocation with how the imports
were written.

## Engineering Lesson

A failing pipeline is usually a signal about the environment, not the
correctness of the code.
"""

CHUNK_2 = """## Evidence

- `/home/alaabadawii/DevOps/jenkins-practice/Jenkinsfile`
- `git log` inside `/home/alaabadawii/DevOps/jenkins-practice/`

## Content Potential

- Debugging story ("when CI is red, check the environment first")

Story strength:
STRONG
"""

SOURCE = "stories_lessons/ci.md"
HASH = "hash-ci"


def _item(chunk_id, content, *, evidence_state=None):
    return ContextItem(
        content=content,
        source=SOURCE,
        chunk_id=chunk_id,
        evidence_state=evidence_state,
        category="stories_lessons",
        document_type="lesson",
        metadata={"content_hash": HASH, "category": "stories_lessons"},
        strategy="hybrid",
        rank=1,
        score=0.0,
    )


def _context(items):
    return SimpleNamespace(evidence_sections=(
        SimpleNamespace(name="stories_lessons", items=tuple(items)),
    ))


def test_link_three_a_catalog_only_tail_is_never_persisted(state_store):
    """The exact input the incident persisted: the tail alone."""

    persisted = persist_discoveries(
        state_store, _context([_item("hash-ci:2", CHUNK_2)]))

    assert persisted == [], "an index card must not become an opportunity"
    assert state_store.count_backlog() == 0


def test_link_one_the_persisted_evidence_is_the_story_not_the_tail(state_store):
    """With the footer and the story both present, the story is what is kept."""

    persisted = persist_discoveries(
        state_store,
        _context([_item("hash-ci:1", CHUNK_1), _item("hash-ci:2", CHUNK_2)]))

    assert len(persisted) == 1
    opportunity = persisted[0]
    assert opportunity.snapshot_version == EVIDENCE_SNAPSHOT_VERSION
    contents = [snapshot["content"] for snapshot in opportunity.evidence]
    assert any(has_narrative(text) for text in contents)
    assert all(not is_catalog_only(text) for text in contents)


def test_link_two_a_frozen_tail_is_refreshed_to_the_story(state_store):
    """A queued opportunity frozen on the tail is repaired in place.

    The fingerprint is unchanged (same documents), so only the snapshot
    refresh can heal it — which is the whole reason for snapshot versioning.
    """
    stale = {
        "source": SOURCE, "chunk_id": "hash-ci:2", "content_hash": HASH,
        "evidence_state": None, "category": "stories_lessons",
        "document_type": "lesson", "content": CHUNK_2,
    }
    fingerprint = opportunity_fingerprint(
        "stories_lessons", [(SOURCE, HASH)])
    stored = state_store.enqueue_opportunity(
        fingerprint, "stories_lessons", [stale],
        evidence_strength=0, snapshot_version=1)
    stale_hash = stored.snapshot_hash

    refreshed = persist_discoveries(
        state_store, _context([_item("hash-ci:1", CHUNK_1)]))[0]

    assert refreshed.opportunity_id == stored.opportunity_id, "no duplicate row"
    assert refreshed.snapshot_hash != stale_hash, "the snapshot was rebuilt"
    assert refreshed.snapshot_version == EVIDENCE_SNAPSHOT_VERSION
    assert has_narrative(refreshed.evidence[0]["content"])
    assert refreshed.status is stored.status, "lifecycle state is untouched"


def test_link_four_the_incidents_label_now_resolves_to_a_real_topic():
    """The reasoner emitted a descriptive label, not the offered topic name.

    ``'evidence: 3 item(s), evidence states: VERIFIED'`` was refused as unknown
    and surfaced as ``unusable_answer``. The offered topic ``evidence`` is what
    the label decorates, and normalization resolves it rather than declining —
    while still refusing a genuinely different name.
    """
    offered = {"evidence", "lessons"}

    assert resolve_topic(
        "evidence: 3 item(s), evidence states: VERIFIED", offered) == "evidence"
    assert resolve_topic("evidence and lessons", offered) is None
