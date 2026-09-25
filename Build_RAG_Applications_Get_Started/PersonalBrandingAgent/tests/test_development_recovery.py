"""M7.2: externally-deleted recovery and controlled republication.

Isolated state throughout. Recovery is an explicit, preconditioned
operation: covered-by-publication in, uncovered-with-marker out, history
untouched. Nothing here weakens duplicate protection.
"""
import pytest

from app.integrations.linkedin.enums import PublicationOutcome
from app.integrations.linkedin.models import PublicationResult
from app.opportunities.opportunities import (
    build_opportunities,
    mark_development_published,
)
from app.state import RunOutcome, StateStore
from app.state.schema import SCHEMA_VERSION


@pytest.fixture
def store(tmp_path):
    with StateStore(tmp_path / "m72.db") as state:
        yield state


def _published(store, work_id="w", key="d", body="post body here",
               post_id="urn:li:test-1"):
    store.ensure_tracked_work(work_id, work_id)
    store.ensure_development(work_id, key, key)
    run = store.start_run("branding")
    intent = store.create_publish_intent(run.run_id, body)
    store.mark_attempt_started(intent.intent_id)
    publication = store.record_publication(
        intent.intent_id, "published", linkedin_post_id=post_id)
    store.finish_run(run.run_id, RunOutcome.DO_NOT_PUBLISH)
    store.set_development_covered(
        work_id, key, covered=True, coverage_kind="published",
        publication_id=publication.publication_id)
    return publication


def _transport(captured, post_id="urn:li:test-2"):
    def send(text):
        captured.append(text)
        return PublicationResult(
            outcome=PublicationOutcome.PUBLISHED, message="published",
            post_id=post_id, api_version="202607",
            attempted_at="2026-09-24T00:00:00+00:00")
    return send


# ------------------------------------------------------- recovery ---

def test_schema_is_at_v8_with_recovery_column(store):
    assert SCHEMA_VERSION == 8
    cols = [r[1] for r in store._conn.execute(
        "PRAGMA table_info(developments)")]
    assert "external_status" in cols


def test_ordinary_covered_publication_stays_protected(store):
    _published(store)

    opps = build_opportunities(store, [{
        "id": "w", "display_name": "W",
        "developments": [{"key": "d"}]}])

    assert opps == []


def test_externally_deleted_can_be_reopened(store):
    publication = _published(store)

    reopened = store.mark_development_externally_deleted("w", "d")

    assert reopened.covered is False
    assert reopened.external_status == "deleted_by_owner"
    assert reopened.coverage_kind == "published"
    assert reopened.publication_id == publication.publication_id
    # Historical publication row untouched.
    assert store.get_publication(
        publication.publication_id) is not None


def test_reopened_development_is_eligible_again(store):
    _published(store)
    store.mark_development_externally_deleted("w", "d")

    opps = build_opportunities(store, [{
        "id": "w", "display_name": "W",
        "developments": [{"key": "d"}]}])

    assert [(o.work_id, o.key) for o in opps] == [("w", "d")]


def test_unrelated_covered_developments_stay_protected(store):
    _published(store, key="a")
    store.ensure_development("w", "b", "B", covered=True)

    opps = build_opportunities(store, [{
        "id": "w", "display_name": "W",
        "developments": [{"key": "a"}, {"key": "b"}]}])

    assert opps == []
    store.mark_development_externally_deleted("w", "a")
    opps = build_opportunities(store, [{
        "id": "w", "display_name": "W",
        "developments": [{"key": "a"}, {"key": "b"}]}])
    assert [(o.key) for o in opps] == ["a"]


def test_recovery_cannot_trigger_accidentally(store):
    from app.errors import StateStoreError

    store.ensure_tracked_work("w", "W")
    store.ensure_development("w", "plain", "P")
    with pytest.raises(StateStoreError):
        store.mark_development_externally_deleted("w", "plain")
    with pytest.raises(StateStoreError):
        store.mark_development_externally_deleted("w", "missing")
    store.ensure_development("w", "base", "B", covered=True)
    with pytest.raises(StateStoreError, match="not by a publication"):
        store.mark_development_externally_deleted("w", "base")


def test_double_recovery_is_refused(store):
    _published(store)
    store.mark_development_externally_deleted("w", "d")

    from app.errors import StateStoreError
    with pytest.raises(StateStoreError):
        store.mark_development_externally_deleted("w", "d")


# ------------------------------------------------------- republication ---

def test_republication_creates_new_record_old_preserved(store):
    from app.publishing import PublishingService, PublishRequest

    old = _published(store, body="first post body here")
    store.mark_development_externally_deleted("w", "d")
    captured = []
    service = PublishingService(
        store, transport=_transport(captured, post_id="urn:li:test-2"))
    run = store.start_run("branding")

    report = service.publish(
        PublishRequest(content="second post body here"), run.run_id)

    assert report.published
    assert captured == ["second post body here"]
    assert store.get_publication(old.publication_id) is not None
    assert report.publication.publication_id != old.publication_id
    mark_development_published(
        store, "w", "d", report.publication.publication_id)
    current = store.get_development("w", "d")
    assert current.covered is True
    assert current.publication_id == report.publication.publication_id


def test_repeat_after_republication_is_refused(store):
    from app.publishing import PublishingService, PublishRequest

    _published(store, body="first post body here")
    store.mark_development_externally_deleted("w", "d")
    service = PublishingService(
        store, transport=_transport([], post_id="urn:li:test-2"))
    run = store.start_run("branding")
    report = service.publish(
        PublishRequest(content="second post body here"), run.run_id)
    assert report.published

    preview = service.preview_publish(
        PublishRequest(content="second post body here"), "other-run")

    assert preview.would_publish is False


# ------------------------------------------------------- generation safety ---

def test_abu_opportunity_still_bounded_after_recovery(store):
    _published(store, work_id="personal-branding-agent",
               key="abu-prompt-introduction", body="first intro body here")
    store.mark_development_externally_deleted(
        "personal-branding-agent", "abu-prompt-introduction")
    entries = [{"id": "personal-branding-agent",
                "display_name": "PBA",
                "developments": [{"key": "abu-prompt-introduction",
                                  "corpus_categories": ["in_progress_projects"],
                                  "evidence_sources": [
                                      "in_progress_projects/personal_branding_agent.md"]}]}]

    opps = build_opportunities(store, entries)

    assert len(opps) == 1
    assert opps[0].evidence_sources == frozenset(
        {"in_progress_projects/personal_branding_agent.md"})
