"""Behavioural tests for the operational state store.

Two themes run through them: every guarantee the store claims must be
demonstrable, and every way the store can fail must fail *closed* — a caller
must never be able to mistake a refused or broken write for a successful one.
"""
import sqlite3

import pytest

from app.errors import StateConstraintError, StateStoreError
from app.state import (
    DeliveryState,
    EvidenceRef,
    LifecycleState,
    PublishState,
    RunOutcome,
    StateStore,
    Workflow,
    content_hash_of,
)

CANDIDATE_POST = "Shipped an incremental sync layer this week."


@pytest.fixture
def store_path(tmp_path):
    return tmp_path / "state_db" / "operational_state.db"


@pytest.fixture
def store(store_path):
    with StateStore(store_path) as opened:
        yield opened


def _intent(store, content=CANDIDATE_POST, topic="sync", angle="lessons"):
    run = store.start_run(Workflow.BRANDING)
    intent = store.create_publish_intent(
        run.run_id, content, topic=topic, angle=angle
    )
    return run, intent


# --- workflow runs ---------------------------------------------------------

def test_a_new_run_has_no_outcome_yet(store):
    run = store.start_run(Workflow.BRANDING)
    assert run.workflow == "branding"
    assert run.outcome is None
    assert run.finished_at is None
    assert not run.finished


def test_finishing_a_run_records_the_outcome_and_the_failed_phase(store):
    run = store.start_run(Workflow.SYNC)
    finished = store.finish_run(run.run_id, RunOutcome.WORKFLOW_FAILED,
                                failed_phase="ingestion")
    assert finished.outcome is RunOutcome.WORKFLOW_FAILED
    assert finished.failed_phase == "ingestion"
    assert finished.finished_at is not None


def test_the_three_outcomes_are_all_reachable(store):
    for outcome in RunOutcome:
        run = store.start_run(Workflow.BRANDING)
        assert store.finish_run(run.run_id, outcome).outcome is outcome


def test_an_outcome_outside_the_vocabulary_is_a_caller_error(store):
    run = store.start_run(Workflow.BRANDING)
    with pytest.raises(ValueError, match="outcome must be one of"):
        store.finish_run(run.run_id, "SUCCEEDED")


def test_a_run_cannot_be_finished_twice(store):
    run = store.start_run(Workflow.BRANDING)
    store.finish_run(run.run_id, RunOutcome.DO_NOT_PUBLISH)
    with pytest.raises(StateStoreError, match="no unfinished run"):
        store.finish_run(run.run_id, RunOutcome.WORKFLOW_FAILED)


def test_finishing_an_unknown_run_is_refused(store):
    with pytest.raises(StateStoreError, match="no unfinished run"):
        store.finish_run("branding-nope", RunOutcome.DO_NOT_PUBLISH)


def test_lists_separate_finished_from_unfinished_runs(store):
    done = store.start_run(Workflow.SYNC)
    store.finish_run(done.run_id, RunOutcome.DO_NOT_PUBLISH)
    hanging = store.start_run(Workflow.BRANDING)

    assert [run.run_id for run in store.list_unfinished_runs()] == [hanging.run_id]
    assert {run.run_id for run in store.list_runs()} == {done.run_id, hanging.run_id}
    assert [run.run_id for run in store.list_runs(Workflow.SYNC)] == [done.run_id]


def test_a_run_survives_a_process_restart(store_path):
    """Milestone: the record outlives the process that wrote it."""
    store = StateStore(store_path)
    run = store.start_run(Workflow.BRANDING)
    store.finish_run(run.run_id, RunOutcome.REQUIRES_HUMAN_INTERVENTION,
                     failed_phase="linkedin_auth")
    store.close()

    reopened = StateStore(store_path)
    try:
        restored = reopened.get_run(run.run_id)
        assert restored is not None
        assert restored.outcome is RunOutcome.REQUIRES_HUMAN_INTERVENTION
        assert restored.failed_phase == "linkedin_auth"
        assert restored.started_at == run.started_at
    finally:
        reopened.close()


# --- publish intents: the write-ahead record -------------------------------

def test_an_intent_is_recorded_before_any_attempt(store):
    _, intent = _intent(store)
    assert intent.state is PublishState.INTENT_CREATED
    assert intent.content == CANDIDATE_POST
    assert intent.content_hash == content_hash_of(CANDIDATE_POST)
    assert intent.topic == "sync" and intent.angle == "lessons"


def test_an_intent_cannot_be_created_for_an_unknown_run(store):
    with pytest.raises(StateConstraintError):
        store.create_publish_intent("branding-does-not-exist", CANDIDATE_POST)


def test_only_one_publish_intent_per_run(store):
    """Acceptance: violating one-publish-per-run is rejected by the database."""
    run, _ = _intent(store)
    with pytest.raises(StateConstraintError, match="database constraint"):
        store.create_publish_intent(run.run_id, "a completely different post")


def test_the_same_content_cannot_be_published_twice(store):
    _, first = _intent(store)
    store.mark_attempt_started(first.intent_id)
    store.record_publication(
        first.intent_id, PublishState.PUBLISHED, linkedin_post_id="urn:li:share:1"
    )

    with pytest.raises(StateConstraintError, match="database constraint"):
        _, _ = _intent(store)  # a later run proposing the same words


def test_an_ambiguous_attempt_keeps_blocking_the_same_content(store):
    _, first = _intent(store)
    store.mark_attempt_started(first.intent_id)
    store.record_publication(first.intent_id, PublishState.UNKNOWN_REQUIRES_REVIEW)

    with pytest.raises(StateConstraintError):
        _intent(store)


def test_an_attempt_that_definitely_failed_releases_its_content(store):
    _, first = _intent(store)
    store.mark_attempt_started(first.intent_id)
    store.record_publication(first.intent_id, PublishState.FAILED)

    # It never reached LinkedIn, so the words are not burned.
    _, second = _intent(store)
    assert second.content_hash == first.content_hash


def test_an_attempt_can_only_start_from_a_fresh_intent(store):
    _, intent = _intent(store)
    store.mark_attempt_started(intent.intent_id)
    with pytest.raises(StateConstraintError, match="not intent_created"):
        store.mark_attempt_started(intent.intent_id)


def test_starting_an_attempt_for_an_unknown_intent_is_refused(store):
    with pytest.raises(StateStoreError, match="unknown publish intent"):
        store.mark_attempt_started("intent_missing")


# --- publications ----------------------------------------------------------

def test_a_publication_requires_a_write_ahead_intent(store):
    with pytest.raises(StateStoreError, match="unknown publish intent"):
        store.record_publication("intent_missing", PublishState.PUBLISHED,
                                 linkedin_post_id="urn:li:share:1")


def test_recording_a_publication_resolves_its_intent_in_one_step(store):
    _, intent = _intent(store)
    store.mark_attempt_started(intent.intent_id)

    publication = store.record_publication(
        intent.intent_id, PublishState.PUBLISHED, linkedin_post_id="urn:li:share:7"
    )

    assert publication.outcome is PublishState.PUBLISHED
    assert publication.linkedin_post_id == "urn:li:share:7"
    assert publication.run_id == intent.run_id
    assert publication.content_hash == intent.content_hash
    assert store.get_publish_intent(intent.intent_id).state is PublishState.PUBLISHED
    assert store.get_publication_for_intent(intent.intent_id).publication_id == (
        publication.publication_id
    )


def test_an_intent_cannot_be_resolved_twice(store):
    _, intent = _intent(store)
    store.mark_attempt_started(intent.intent_id)
    store.record_publication(intent.intent_id, PublishState.FAILED)

    with pytest.raises(StateConstraintError, match="already resolved"):
        store.record_publication(intent.intent_id, PublishState.FAILED)


def test_a_published_outcome_requires_a_post_id(store):
    _, intent = _intent(store)
    store.mark_attempt_started(intent.intent_id)
    with pytest.raises(ValueError, match="requires the LinkedIn post id"):
        store.record_publication(intent.intent_id, PublishState.PUBLISHED)


def test_an_unpublished_outcome_cannot_carry_a_post_id(store):
    _, intent = _intent(store)
    store.mark_attempt_started(intent.intent_id)
    with pytest.raises(ValueError, match="cannot carry a LinkedIn post id"):
        store.record_publication(intent.intent_id, PublishState.FAILED,
                                 linkedin_post_id="urn:li:share:1")


def test_an_unresolved_state_is_not_an_outcome(store):
    _, intent = _intent(store)
    store.mark_attempt_started(intent.intent_id)
    with pytest.raises(ValueError, match="terminal publish state"):
        store.record_publication(intent.intent_id, PublishState.ATTEMPT_STARTED)


def test_evidence_references_are_stored_with_their_content_hashes(store):
    _, intent = _intent(store)
    store.mark_attempt_started(intent.intent_id)
    publication = store.record_publication(
        intent.intent_id,
        PublishState.PUBLISHED,
        linkedin_post_id="urn:li:share:3",
        evidence_refs=[
            EvidenceRef("evidence/backend/fastapi.md", "hash-a"),
            EvidenceRef("completed_projects/quizey.md", "hash-b"),
            EvidenceRef("evidence/backend/fastapi.md", "hash-a"),  # duplicate
        ],
    )

    stored = store.get_publication(publication.publication_id).evidence
    # Duplicates collapse; the read is ordered deterministically by path.
    assert stored == [
        EvidenceRef("completed_projects/quizey.md", "hash-b"),
        EvidenceRef("evidence/backend/fastapi.md", "hash-a"),
    ]
    # And it is queryable straight from the record, without retrieval.
    assert store.list_publications()[0].evidence == stored


# --- synchronization checkpoints -------------------------------------------

def test_a_checkpoint_starts_empty_for_an_unsynced_source(store):
    assert store.get_checkpoint("ibm") is None


def test_a_successful_sync_advances_the_checkpoint(store):
    checkpoint = store.record_sync_success("ibm", "abc123")
    assert checkpoint.last_revision == "abc123"
    assert checkpoint.last_outcome.value == "SUCCEEDED"
    assert checkpoint.last_synced_at is not None


def test_a_failed_sync_does_not_advance_the_checkpoint(store):
    store.record_sync_success("ibm", "abc123")
    after = store.record_sync_failure("ibm")
    assert after.last_revision == "abc123"  # the same range will be re-read
    assert after.last_outcome.value == "FAILED"


def test_a_source_that_never_synced_can_record_a_failure(store):
    checkpoint = store.record_sync_failure("new-source")
    assert checkpoint.last_revision is None
    assert checkpoint.last_synced_at is None
    assert checkpoint.last_outcome.value == "FAILED"


def test_an_empty_revision_is_refused(store):
    with pytest.raises(ValueError, match="revision must be non-empty"):
        store.record_sync_success("ibm", "")


# --- source lifecycle ------------------------------------------------------

def test_lifecycle_can_be_set_and_observed(store):
    assert store.get_source_lifecycle("quizey") is None

    store.set_source_lifecycle("quizey", LifecycleState.COMPLETED, note="shipped")
    assert store.get_source_lifecycle("quizey").lifecycle is LifecycleState.COMPLETED

    store.set_source_lifecycle("quizey", LifecycleState.ACTIVE, note="reopened")
    current = store.get_source_lifecycle("quizey")
    assert current.lifecycle is LifecycleState.ACTIVE
    assert current.note == "reopened"
    assert len(store.list_source_lifecycles()) == 1


def test_a_lifecycle_outside_the_vocabulary_is_a_caller_error(store):
    with pytest.raises(ValueError, match="lifecycle must be one of"):
        store.set_source_lifecycle("quizey", "DONE")


# --- failures and notifications --------------------------------------------

def test_a_failure_is_stored_structured(store):
    run = store.start_run(Workflow.BRANDING)
    failure = store.record_failure(
        phase="verification",
        error_category="evidence_insufficient",
        message="no supporting evidence for the claim",
        retryable=False,
        requires_human_intervention=True,
        run_id=run.run_id,
        workflow=Workflow.BRANDING,
    )
    assert failure.occurrence_count == 1
    assert failure.retryable is False
    assert failure.requires_human_intervention is True
    assert [row.failure_id for row in store.list_failures(run_id=run.run_id)] == [
        failure.failure_id
    ]


def test_a_repeated_failure_is_counted_not_multiplied(store):
    first = store.record_failure("retrieval", "chroma_unavailable", "boom",
                                 retryable=True, dedupe_key="retrieval:chroma")
    again = store.record_failure("retrieval", "chroma_unavailable", "boom",
                                 retryable=True, dedupe_key="retrieval:chroma")

    assert again.failure_id == first.failure_id
    assert again.occurrence_count == 2
    assert again.first_seen_at == first.first_seen_at
    assert len(store.list_failures()) == 1  # the first occurrence is still there


def test_failures_without_a_key_are_never_merged(store):
    first = store.record_failure("generation", "llm_error", "one")
    second = store.record_failure("generation", "llm_error", "two")
    assert first.failure_id != second.failure_id
    assert len(store.list_failures()) == 2


def test_a_delivery_failure_does_not_replace_the_workflow_failure(store):
    run = store.start_run(Workflow.BRANDING)
    failure = store.record_failure(
        phase="notification", error_category="smtp_unreachable",
        message="could not reach the SMTP host", run_id=run.run_id,
    )
    notification = store.record_notification(
        recipient="user@example.com",
        subject="Branding run failed",
        delivery_state=DeliveryState.FAILED,
        failure_id=failure.failure_id,
        run_id=run.run_id,
        error_message="connection refused",
    )

    # Both outcomes are separately observable — neither masks the other.
    assert store.get_failure(failure.failure_id) is not None
    assert notification.delivery_state is DeliveryState.FAILED
    assert notification.delivered_at is None
    assert [row.notification_id for row in store.list_notifications(
        run_id=run.run_id, delivery_state=DeliveryState.FAILED
    )] == [notification.notification_id]


def test_a_sent_notification_records_when_it_was_delivered(store):
    notification = store.record_notification(
        "user@example.com", "Run failed", DeliveryState.SENT
    )
    assert notification.delivered_at is not None
    assert notification.attempted_at is not None


def test_a_pending_notification_can_be_resolved_later(store):
    pending = store.record_notification(
        "user@example.com", "Run failed", DeliveryState.PENDING
    )
    resolved = store.update_notification_delivery(
        pending.notification_id, DeliveryState.FAILED, error_message="timeout"
    )
    assert resolved.delivery_state is DeliveryState.FAILED
    assert resolved.error_message == "timeout"
    assert resolved.delivered_at is None


def test_resolving_an_unknown_notification_is_refused(store):
    with pytest.raises(StateStoreError, match="unknown notification"):
        store.update_notification_delivery("notif_missing", DeliveryState.SENT)


# --- locks -----------------------------------------------------------------

def test_a_lock_is_held_exclusively(store, store_path):
    first = store.acquire_lock("branding", "host-a:1")
    assert first.acquired and not first.recovered_stale

    other = StateStore(store_path)
    try:
        second = other.acquire_lock("branding", "host-b:2")
        assert not second.acquired
        assert second.holder == "host-a:1"
        assert second.lock.owner == "host-a:1"
    finally:
        other.close()


def test_a_stale_lock_is_recovered_and_reported(store, store_path):
    store.acquire_lock("branding", "host-a:1", ttl_seconds=0)

    other = StateStore(store_path)
    try:
        recovered = other.acquire_lock("branding", "host-b:2")
        assert recovered.acquired
        assert recovered.recovered_stale
        assert recovered.lock.owner == "host-b:2"
    finally:
        other.close()


def test_only_the_owner_can_release_a_lock(store):
    store.acquire_lock("branding", "host-a:1")
    assert store.release_lock("branding", "host-b:2") is False
    assert store.get_lock("branding") is not None
    assert store.release_lock("branding", "host-a:1") is True
    assert store.get_lock("branding") is None


def test_renewing_a_lock_you_do_not_hold_is_refused(store):
    store.acquire_lock("branding", "host-a:1")
    with pytest.raises(StateStoreError, match="not held by"):
        store.renew_lock("branding", "host-b:2")


def test_a_renewed_lock_still_belongs_to_its_owner(store):
    store.acquire_lock("branding", "host-a:1", ttl_seconds=0)
    renewed = store.renew_lock("branding", "host-a:1", ttl_seconds=60)
    assert renewed.owner == "host-a:1"
    assert renewed.expires_at >= renewed.heartbeat_at


def test_a_negative_ttl_is_a_caller_error(store):
    with pytest.raises(ValueError, match="must not be negative"):
        store.acquire_lock("branding", "host-a:1", ttl_seconds=-1)


# --- fail-closed behaviour -------------------------------------------------

def test_concurrent_connections_see_each_other_s_committed_writes(store, store_path):
    run = store.start_run(Workflow.SYNC)

    other = StateStore(store_path)
    try:
        assert other.get_run(run.run_id).run_id == run.run_id
    finally:
        other.close()


def test_a_blocked_writer_fails_as_a_store_error_while_readers_proceed(
    store_path, monkeypatch
):
    """WAL keeps readers working; a writer that cannot get the lock gives up.

    Giving up is bounded on purpose. Waiting indefinitely inside an unattended
    workflow is indistinguishable from hanging, and a raw ``sqlite3`` error
    escaping here would make every caller depend on the driver.
    """
    monkeypatch.setattr("app.state.store.BUSY_TIMEOUT_SECONDS", 0.05)
    with StateStore(store_path) as store:
        blocker = sqlite3.connect(str(store_path))
        blocker.isolation_level = None
        blocker.execute("BEGIN IMMEDIATE")  # another process holds the writer
        try:
            assert store.list_runs() == []  # a reader is not blocked by it
            with pytest.raises(StateStoreError, match="failed"):
                store.start_run(Workflow.BRANDING)
        finally:
            blocker.execute("ROLLBACK")
            blocker.close()


def test_a_closed_store_refuses_every_operation(store):
    run = store.start_run(Workflow.BRANDING)
    store.close()

    with pytest.raises(StateStoreError, match="closed"):
        store.create_publish_intent(run.run_id, CANDIDATE_POST)
    with pytest.raises(StateStoreError, match="closed"):
        store.start_run(Workflow.BRANDING)
    with pytest.raises(StateStoreError, match="closed"):
        store.acquire_lock("branding", "host-a:1")
    with pytest.raises(StateStoreError, match="closed"):
        store.get_run(run.run_id)


def test_closing_twice_is_harmless(store):
    store.close()
    store.close()


def test_an_unusable_location_fails_at_construction(tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("in the way")
    with pytest.raises(StateStoreError, match="unavailable"):
        StateStore(blocker / "operational_state.db")


def test_empty_content_is_refused_before_it_reaches_the_database(store):
    run = store.start_run(Workflow.BRANDING)
    with pytest.raises(ValueError, match="empty content"):
        store.create_publish_intent(run.run_id, "   ")
