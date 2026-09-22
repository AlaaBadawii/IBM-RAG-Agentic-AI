"""Step 6: the publishing-history read service.

``PLAN.md`` Step 6 requires the history to be queryable **deterministically,
without retrieval**, and to be incapable of returning a generated post as
evidence about the user. The tests below check both halves of that: what the
queries return, and what this layer is structurally unable to touch.

The separation tests are deliberately structural (an import scan over
``app/publishing``) rather than behavioural: "this module does not import
Chroma" is a property that cannot silently regress, whereas "no test observed
a write" only proves that no test looked.
"""
import ast
from dataclasses import fields
from datetime import timedelta
from pathlib import Path

import pytest

from app.integrations.linkedin.enums import PublicationOutcome
from app.integrations.linkedin.models import PublicationResult
from app.publishing import (
    PublishingHistory,
    PublishingService,
    PublishRequest,
    evidence_ref,
)
from app.state.models import EvidenceRef, to_iso, utc_now

POST_ID = "urn:li:share:7123456789"
PUBLISHING_PACKAGE = Path(__file__).resolve().parents[1] / "app" / "publishing"


def _result(outcome=PublicationOutcome.PUBLISHED, post_id=POST_ID):
    return PublicationResult(
        outcome=outcome,
        message="published",
        api_version="202601",
        attempted_at=to_iso(utc_now()),
        post_id=post_id,
    )


def publish(store, *, content, topic=None, angle=None, project=None,
            evidence=(), result=None):
    run = store.start_run("branding")
    service = PublishingService(
        store, transport=lambda _: result or _result()
    )
    return service.publish(
        PublishRequest(content=content, topic=topic, angle=angle,
                       project=project, evidence=evidence),
        run.run_id,
    )


@pytest.fixture
def history(state_store) -> PublishingHistory:
    return PublishingHistory(state_store)


# --- an empty history is not an error ----------------------------------------

def test_an_empty_history_returns_empty_not_an_error(history):
    """Acceptance: empty history returns empty."""
    assert history.recent_publications() == ()
    assert history.recent_topics() == ()
    assert history.recent_projects() == ()
    assert history.recent_evidence() == ()
    assert history.requires_review() == ()
    assert history.unresolved_intents() == ()


# --- what was published ------------------------------------------------------

def test_recent_publications_returns_the_stored_records(state_store, history):
    """Acceptance: history queries return only stored records."""
    publish(state_store, content="the first post", topic="sync",
            project="PersonalBrandingAgent")
    publish(state_store, content="the second post", topic="retrieval",
            project="RAG_Lab")

    rows = history.recent_publications()

    assert [row.topic for row in rows] == ["retrieval", "sync"]
    assert [row.project for row in rows] == ["RAG_Lab", "PersonalBrandingAgent"]
    assert all(row.linkedin_post_id == POST_ID for row in rows)
    stored_ids = {record.publication_id
                  for record in state_store.list_publication_records()}
    assert {row.publication_id for row in rows} == stored_ids


def test_history_reports_only_what_actually_published(state_store, history):
    """A failure is not history, and an ambiguity is a question, not a fact."""
    publish(state_store, content="this one went out")
    publish(state_store, content="this one was rejected",
            result=_result(PublicationOutcome.FAILED, post_id=None))
    publish(state_store, content="this one is unresolved",
            result=_result(PublicationOutcome.UNKNOWN, post_id=None))

    assert len(history.recent_publications()) == 1
    review = history.requires_review()
    assert len(review) == 1
    assert review[0].linkedin_post_id is None
    assert review[0].content_hash


def test_a_limit_bounds_the_answer_without_changing_its_order(state_store, history):
    """A limit is a window on a deterministic order, not a different query."""
    for index in range(4):
        publish(state_store, content=f"post {index}")

    assert len(history.recent_publications()) == 4
    limited = history.recent_publications(limit=2)
    assert len(limited) == 2
    assert [row.publication_id for row in limited] == [
        row.publication_id for row in history.recent_publications()[:2]
    ]


# --- what was used -----------------------------------------------------------

def test_topics_are_counted_from_stored_intents(state_store, history):
    publish(state_store, content="one about sync", topic="sync")
    publish(state_store, content="two about sync", topic="sync")
    publish(state_store, content="one about retrieval", topic="retrieval")
    publish(state_store, content="no topic at all")

    rows = history.recent_topics()

    assert [(row.value, row.uses) for row in rows] == [
        ("sync", 2), ("retrieval", 1)
    ]
    assert all(row.publication_ids for row in rows)
    assert all(row.last_used_at for row in rows)


def test_projects_discussed_are_counted_from_stored_intents(state_store, history):
    publish(state_store, content="one", project="RAG_Lab")
    publish(state_store, content="two", project="RAG_Lab")
    publish(state_store, content="three", project="PersonalBrandingAgent")

    rows = history.recent_projects()

    assert [(row.value, row.uses) for row in rows] == [
        ("RAG_Lab", 2), ("PersonalBrandingAgent", 1)
    ]


def test_evidence_used_is_counted_by_path_and_content_hash(state_store, history):
    """Acceptance: evidence references contain content hashes."""
    before = evidence_ref("evidence/backend/fastapi.md", "hashA:0")
    changed = evidence_ref("evidence/backend/fastapi.md", "hashB:0")
    publish(state_store, content="one", evidence=(before, changed))
    publish(state_store, content="two", evidence=(before,))

    rows = history.recent_evidence()

    assert [(row.source_path, row.content_hash, row.uses) for row in rows] == [
        ("evidence/backend/fastapi.md", "hashA", 2),
        ("evidence/backend/fastapi.md", "hashB", 1),
    ]
    assert all(row.publication_ids for row in rows)


def test_every_row_is_attributable_to_a_stored_publication(state_store, history):
    """Acceptance: every result is attributable to stored publication state."""
    publish(state_store, content="one", topic="sync", project="RAG_Lab",
            evidence=(evidence_ref("evidence/backend/fastapi.md", "hashA:0"),))

    stored = {record.publication_id
              for record in state_store.list_publication_records()}
    reported = {row.publication_id for row in history.recent_publications()}
    for row in (history.recent_topics() + history.recent_projects()
                + history.recent_evidence()):
        reported |= set(row.publication_ids)

    assert reported, "nothing was reported at all"
    assert reported <= stored, "a row was reported that no publication supports"


def test_a_window_excludes_what_is_outside_it(state_store, history):
    publish(state_store, content="an old post", topic="sync")
    future = to_iso(utc_now() + timedelta(days=60))

    assert history.recent_topics() != ()
    assert history.recent_topics(since=future) == ()
    assert history.recent_evidence(since=future) == ()


# --- generated posts never become evidence -----------------------------------

def test_the_history_never_returns_the_generated_text(state_store, history):
    """Acceptance: no generated post can be returned as evidence.

    The published prose is absent from every type the history hands out. What
    it returns is the hash, the labels, and references to the *corpus* the post
    was grounded in — never the post itself, which is what could become
    "evidence" for the next one (``PLAN.md`` §6.1).
    """
    text = "A generated post about incremental synchronization."
    publish(state_store, content=text, topic="sync")

    rows = history.recent_publications()
    assert rows
    for row in rows:
        assert text not in repr(row)
        assert "content" not in {field.name for field in fields(row)}
    assert text not in repr(history.recent_topics())
    assert text not in repr(history.recent_evidence())


def test_the_evidence_a_history_row_carries_belongs_to_the_corpus(
        state_store, history):
    """A history row's evidence is what the post cited, not the post."""
    ref = evidence_ref("evidence/backend/fastapi.md", "hashA:0")
    publish(state_store, content="a post", evidence=(ref,))

    row = history.recent_publications()[0]

    assert [(e.source_path, e.content_hash) for e in row.evidence] == [
        ("evidence/backend/fastapi.md", "hashA")
    ]


@pytest.mark.parametrize("module", sorted(PUBLISHING_PACKAGE.glob("*.py")),
                         ids=lambda path: path.name)
def test_the_publishing_layer_cannot_reach_the_vector_store(module):
    """Acceptance: publishing state is never written into Chroma.

    Enforced structurally: nothing in ``app/publishing`` imports the retrieval,
    ingestion, or vector-store layers, so there is no code path that could
    index a publication. A behavioural test could only show that it did not
    happen in the cases it tried.
    """
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden = ("chroma", "langchain", "app.retrieval", "app.ingestion")
    offenders = [
        name for name in imported
        if any(name == bad or name.startswith(f"{bad}.") for bad in forbidden)
    ]
    assert not offenders, f"{module.name} reaches the knowledge layer: {offenders}"


# --- evidence references -----------------------------------------------------

def test_an_evidence_reference_carries_the_path_and_the_content_hash():
    ref = evidence_ref("@source/ai-agents/notes.md", "abc123:4")
    assert ref.source_path == "@source/ai-agents/notes.md"
    assert ref.content_hash == "abc123"


def test_an_evidence_reference_without_a_content_hash_is_refused():
    """Without the hash, a later audit cannot tell "changed" from "never cited"."""
    with pytest.raises(ValueError, match="no content hash"):
        evidence_ref("evidence/backend/fastapi.md", "")
    with pytest.raises(ValueError, match="no content hash"):
        evidence_ref("evidence/backend/fastapi.md", ":0")
    with pytest.raises(ValueError, match="source path"):
        evidence_ref("", "abc123:0")


def test_a_request_refuses_an_evidence_reference_with_an_empty_hash():
    with pytest.raises(ValueError, match="content hash"):
        PublishRequest(content="a post",
                       evidence=(EvidenceRef(source_path="a.md", content_hash=""),))


def test_a_request_refuses_empty_content():
    with pytest.raises(ValueError, match="non-empty"):
        PublishRequest(content="   ")
