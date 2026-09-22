"""Step 6: the publishing service — intent, attempt, outcome, recovery.

Every test here runs offline: the transport is a fake that returns a
``PublicationResult`` the test built, no credential is read, and no request is
made. What is being tested is the state machine, so the transport's answers are
the input and the durable store is the output.

The claims under test are the ones ``PLAN.md`` Step 6 lists as acceptance
criteria: no publish without a prior durable intent; one attempt per run,
enforced by the database; an ambiguous outcome recorded and never retried; a
crash between the call and the record recoverable rather than repaired; and a
post id recorded exactly when there is one.
"""
from dataclasses import replace

import pytest

from app.errors import StateConstraintError, StateStoreError
from app.integrations.linkedin.enums import (
    LinkedInErrorCategory,
    PublicationOutcome,
)
from app.integrations.linkedin.models import PublicationResult
from app.publishing import (
    MAX_PUBLISHES_PER_RUN,
    PublishDecision,
    PublishingService,
    PublishRequest,
    evidence_ref,
)
from app.state import StateStore
from app.state.enums import PublishState, Workflow
from app.state.models import to_iso, utc_now

POST_ID = "urn:li:share:7123456789"
TEXT = "I shipped a small thing and it taught me something about retries."


# --- fakes -------------------------------------------------------------------

def linkedin_result(outcome: PublicationOutcome, *, post_id: str | None = None,
                    message: str = "reported by the fake transport",
                    category: LinkedInErrorCategory | None = None,
                    retryable: bool = False,
                    requires_human: bool = False) -> PublicationResult:
    """A ``PublicationResult`` as the Step 5 integration would return it."""
    return PublicationResult(
        outcome=outcome,
        message=message,
        api_version="202601",
        attempted_at=to_iso(utc_now()),
        post_id=post_id,
        error_category=category,
        retryable=retryable,
        requires_human_intervention=requires_human,
    )


class FakeTransport:
    """Stands in for ``publish_to_linkedin``: records calls, returns an answer.

    ``answer`` may be a result or an exception. An exception is how a crash is
    simulated: the request happened, and the process never got to hear about it.
    """

    def __init__(self, answer, *, on_call=None):
        self.answer = answer
        self.on_call = on_call
        self.calls: list[str] = []

    def __call__(self, text: str) -> PublicationResult:
        self.calls.append(text)
        if self.on_call is not None:
            self.on_call(text)
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer

    @property
    def called(self) -> bool:
        return bool(self.calls)


@pytest.fixture
def store(tmp_path) -> StateStore:
    """A real store in a temporary file, closed after the test."""
    created = StateStore(tmp_path / "state" / "operational_state.db")
    yield created
    created.close()


def _service(store: StateStore, transport) -> PublishingService:
    return PublishingService(store, transport=transport)


def _run(store: StateStore, workflow: str = "branding"):
    return store.start_run(workflow)


def _published(store: StateStore) -> PublicationResult:
    return linkedin_result(PublicationOutcome.PUBLISHED, post_id=POST_ID)


# --- the write-ahead intent --------------------------------------------------

def test_the_intent_is_durable_before_the_linkedin_call(store):
    """Acceptance: no publish occurs without a prior durable intent.

    The check runs *inside* the transport, at the moment of the call: the
    assertion is about what the store contained when the request was made, not
    about what it contains afterwards.
    """
    run = _run(store)
    seen: dict = {}

    def inspect(text):
        seen["intent"] = store.get_intent_for_run(run.run_id)

    transport = FakeTransport(_published(store), on_call=inspect)
    report = _service(store, transport).publish(PublishRequest(content=TEXT), run.run_id)

    assert report.published
    assert seen["intent"] is not None, "no intent existed when the call was made"
    assert seen["intent"].state is PublishState.ATTEMPT_STARTED
    assert seen["intent"].content == TEXT


def test_the_intent_is_written_before_the_request_is_marked_started(store):
    """The two writes are ordered, so the crash point is recoverable.

    An intent at ``intent_created`` means the attempt never started; at
    ``attempt_started`` it may have. Recording them in the other order would
    make a crash indistinguishable from a request that was never sent, and the
    safe reading of that is "a post may exist" — which is exactly what the
    order here avoids claiming.
    """
    run = _run(store)
    states: list[PublishState] = []
    transport = FakeTransport(
        _published(store),
        on_call=lambda _: states.append(store.get_intent_for_run(run.run_id).state),
    )
    _service(store, transport).publish(PublishRequest(content=TEXT), run.run_id)
    assert states == [PublishState.ATTEMPT_STARTED]


def test_no_request_is_made_when_the_store_cannot_write_the_intent(store):
    """The store is the system's memory: if it cannot record, nothing is sent."""
    transport = FakeTransport(_published(store))
    with pytest.raises(StateConstraintError):
        # No such run, so the intent's foreign key refuses it.
        _service(store, transport).publish(
            PublishRequest(content=TEXT), "branding-does-not-exist"
        )
    assert not transport.called


def test_a_closed_store_stops_the_publish_before_any_request(store):
    run = _run(store)
    transport = FakeTransport(_published(store))
    service = _service(store, transport)
    store.close()

    with pytest.raises(StateStoreError):
        service.publish(PublishRequest(content=TEXT), run.run_id)
    assert not transport.called


# --- one publication per run -------------------------------------------------

def test_at_most_one_publish_reaches_the_gate_per_run(store):
    """Acceptance: a second attempt in the same run is rejected by the database.

    ``MAX_PUBLISHES_PER_RUN`` is not re-checked in Python — the second
    ``publish_intents`` row for the run is refused by
    ``ux_publish_intents_run``, which is why the raise is a
    ``StateConstraintError`` and not a refusal report.
    """
    assert MAX_PUBLISHES_PER_RUN == 1
    run = _run(store)
    transport = FakeTransport(_published(store))
    service = _service(store, transport)

    assert service.publish(PublishRequest(content=TEXT), run.run_id).published
    with pytest.raises(StateConstraintError):
        service.publish(PublishRequest(content="a different post entirely"),
                        run.run_id)

    assert len(transport.calls) == 1, "a second request was made in the same run"
    assert len(store.list_publish_intents()) == 1


def test_a_later_run_may_publish_different_content(store):
    """One-per-run is per run, not per system."""
    first = _run(store)
    second = _run(store)
    transport = FakeTransport(_published(store))
    service = _service(store, transport)

    assert service.publish(PublishRequest(content=TEXT), first.run_id).published
    assert service.publish(PublishRequest(content="something else, honestly"),
                           second.run_id).published
    assert len(transport.calls) == 2


# --- outcomes ----------------------------------------------------------------

def test_a_successful_publish_records_the_linkedin_post_id(store):
    run = _run(store)
    evidence = (evidence_ref("evidence/backend/fastapi.md", "abc123:0"),)
    report = _service(store, FakeTransport(_published(store))).publish(
        PublishRequest(content=TEXT, topic="backend", angle="lessons",
                       project="PersonalBrandingAgent", evidence=evidence),
        run.run_id,
    )

    assert report.decision is PublishDecision.PUBLISHED
    assert report.linkedin_post_id == POST_ID
    stored = store.get_publication_for_intent(report.intent_id)
    assert stored.outcome is PublishState.PUBLISHED
    assert stored.linkedin_post_id == POST_ID
    assert report.duplicates is not None


def test_the_evidence_a_post_was_grounded_in_is_stored_with_its_hash(store):
    """Acceptance: evidence references are stored with content hashes."""
    run = _run(store)
    evidence = (
        evidence_ref("evidence/backend/fastapi.md", "hashA:0"),
        evidence_ref("@source/ai-agents/notes.md", "hashB:3"),
    )
    report = _service(store, FakeTransport(_published(store))).publish(
        PublishRequest(content=TEXT, evidence=evidence), run.run_id
    )

    stored = store.get_publication_for_intent(report.intent_id)
    assert [(ref.source_path, ref.content_hash) for ref in stored.evidence] == [
        ("@source/ai-agents/notes.md", "hashB"),
        ("evidence/backend/fastapi.md", "hashA"),
    ]


def test_a_classified_failure_is_recorded_as_failed(store):
    run = _run(store)
    answer = linkedin_result(
        PublicationOutcome.FAILED,
        message="LinkedIn rejected the post with HTTP 422",
        category=LinkedInErrorCategory.VALIDATION,
    )
    report = _service(store, FakeTransport(answer)).publish(
        PublishRequest(content=TEXT), run.run_id
    )

    assert report.decision is PublishDecision.FAILED
    assert not report.requires_review
    assert report.linkedin_post_id is None
    stored = store.get_publication_for_intent(report.intent_id)
    assert stored.outcome is PublishState.FAILED
    assert stored.linkedin_post_id is None


def test_a_timeout_is_recorded_as_unknown_requires_review(store):
    """Acceptance: an ambiguous outcome is persisted, not guessed at."""
    run = _run(store)
    answer = linkedin_result(
        PublicationOutcome.UNKNOWN,
        message="LinkedIn request failed while creating the post: ReadTimeout",
        category=LinkedInErrorCategory.TRANSPORT,
    )
    report = _service(store, FakeTransport(answer)).publish(
        PublishRequest(content=TEXT), run.run_id
    )

    assert report.decision is PublishDecision.UNKNOWN_REQUIRES_REVIEW
    assert report.requires_review
    assert report.requires_human_intervention
    stored = store.get_publication_for_intent(report.intent_id)
    assert stored.outcome is PublishState.UNKNOWN_REQUIRES_REVIEW
    assert stored.linkedin_post_id is None


def test_a_success_without_a_post_id_is_ambiguous_not_published(store):
    """A claim of success with nothing to point at is not success."""
    run = _run(store)
    answer = linkedin_result(
        PublicationOutcome.PUBLISHED, post_id=None,
        message="LinkedIn accepted the request but returned no post id",
    )
    report = _service(store, FakeTransport(answer)).publish(
        PublishRequest(content=TEXT), run.run_id
    )

    assert report.decision is PublishDecision.UNKNOWN_REQUIRES_REVIEW
    assert report.linkedin_post_id is None


def test_an_authentication_failure_asks_for_a_person_without_retrying(store):
    run = _run(store)
    answer = linkedin_result(
        PublicationOutcome.FAILED,
        message="the stored credential has expired",
        category=LinkedInErrorCategory.AUTHENTICATION,
        requires_human=True,
    )
    transport = FakeTransport(answer)
    report = _service(store, transport).publish(PublishRequest(content=TEXT),
                                                run.run_id)

    assert report.decision is PublishDecision.FAILED
    assert report.requires_human_intervention
    assert len(transport.calls) == 1, "the service retried an auth failure"


# --- ambiguity is terminal ---------------------------------------------------

def test_an_ambiguous_outcome_is_never_retried_by_a_later_run(store):
    """Acceptance: an ambiguous outcome is persisted and never blindly retried.

    A later run proposing the same words is refused before any request is
    built — the durable intent, not a memory of what happened, is what stops it.
    """
    first = _run(store)
    ambiguous = linkedin_result(PublicationOutcome.UNKNOWN,
                                message="read timeout after sending")
    transport = FakeTransport(ambiguous)
    service = _service(store, transport)
    assert service.publish(PublishRequest(content=TEXT), first.run_id).requires_review

    second = _run(store)
    retry = FakeTransport(_published(store))
    report = _service(store, retry).publish(PublishRequest(content=TEXT),
                                            second.run_id)

    assert report.refused
    assert not retry.called, "an unresolved attempt was retried"
    assert "unresolved" in report.message


def test_a_definitely_failed_attempt_does_not_burn_the_content(store):
    """The mirror image: a rejection leaves the words free, so they can be fixed."""
    first = _run(store)
    rejected = linkedin_result(PublicationOutcome.FAILED,
                              message="LinkedIn rejected the post with HTTP 422")
    assert _service(store, FakeTransport(rejected)).publish(
        PublishRequest(content=TEXT), first.run_id
    ).decision is PublishDecision.FAILED

    second = _run(store)
    transport = FakeTransport(_published(store))
    assert _service(store, transport).publish(PublishRequest(content=TEXT),
                                              second.run_id).published
    assert transport.called


# --- recovery ----------------------------------------------------------------

def test_a_crash_after_the_external_call_leaves_an_ambiguous_state(store):
    """Acceptance: a crash between intent and response is recoverable, not FAILED.

    The transport simulates the worst case: LinkedIn *did* accept the post, and
    the process died before recording anything. The state left behind must say
    "a post may exist" — never "failed", which would let the next run send a
    duplicate.
    """
    run = _run(store)
    crashed = FakeTransport(RuntimeError("process died after the request"))
    service = _service(store, crashed)

    with pytest.raises(RuntimeError):
        service.publish(PublishRequest(content=TEXT), run.run_id)

    intent = store.get_intent_for_run(run.run_id)
    assert intent.state is PublishState.ATTEMPT_STARTED
    assert store.get_publication_for_intent(intent.intent_id) is None

    recovery = service.recover_run(run.run_id)

    assert recovery.recovered == 1
    assert recovery.blocked
    attempt = recovery.attempts[0]
    assert attempt.requires_review
    assert attempt.resolved_to is PublishState.UNKNOWN_REQUIRES_REVIEW
    stored = store.get_publication_for_intent(intent.intent_id)
    assert stored.outcome is PublishState.UNKNOWN_REQUIRES_REVIEW
    assert stored.linkedin_post_id is None


def test_a_crash_after_a_successful_post_leaves_a_recoverable_ambiguity(tmp_path):
    """The case ``PLAN.md`` describes: the post exists, the record does not.

    This is the worst case in the system, and it is prevented by design rather
    than repaired: because the intent was written and the attempt marked before
    the request, the crash leaves a state that *says* the outcome is unknown.
    Nothing here can prove whether the post went out — LinkedIn has no
    read-back — so the only honest resolution is to block the content and ask a
    person, which is what recovery does.
    """
    path = tmp_path / "state" / "operational_state.db"
    store = StateStore(path)
    run = store.start_run(Workflow.BRANDING)

    def crash(_text):
        store.close()  # the process dies with the post already sent
        return _published(store)

    with pytest.raises(StateStoreError):
        PublishingService(store, transport=crash).publish(
            PublishRequest(content=TEXT), run.run_id
        )

    reopened = StateStore(path)
    try:
        intent = reopened.get_intent_for_run(run.run_id)
        assert intent.state is PublishState.ATTEMPT_STARTED
        assert reopened.get_publication_for_intent(intent.intent_id) is None

        recovery = PublishingService(reopened).recover_run(run.run_id)
        assert recovery.blocked
        assert reopened.get_publication_for_intent(
            intent.intent_id
        ).outcome is PublishState.UNKNOWN_REQUIRES_REVIEW
    finally:
        reopened.close()


def test_recovery_never_retries_the_interrupted_attempt(store):
    """Recovery records an ambiguity; it does not resolve it by trying again."""
    run = _run(store)
    crashed = FakeTransport(RuntimeError("process died after the request"))
    service = _service(store, crashed)
    with pytest.raises(RuntimeError):
        service.publish(PublishRequest(content=TEXT), run.run_id)
    service.recover_run(run.run_id)

    later = _run(store)
    transport = FakeTransport(_published(store))
    report = _service(store, transport).publish(PublishRequest(content=TEXT),
                                                later.run_id)

    assert report.refused
    assert len(crashed.calls) == 1 and not transport.called


def test_recovery_releases_an_intent_whose_attempt_never_started(store):
    """The other interruption: intent written, attempt never begun.

    Nothing left the machine, so "no post exists" is a fact rather than a hope,
    and the words are free for a later run.
    """
    run = _run(store)
    intent = store.create_publish_intent(run.run_id, TEXT)
    service = PublishingService(store, transport=FakeTransport(_published(store)))

    recovery = service.recover_run(run.run_id)

    assert recovery.recovered == 1
    assert not recovery.blocked
    assert recovery.released[0].resolved_to is PublishState.FAILED
    assert store.get_publication_for_intent(intent.intent_id).outcome \
        is PublishState.FAILED

    later = _run(store)
    transport = FakeTransport(_published(store))
    assert _service(store, transport).publish(PublishRequest(content=TEXT),
                                              later.run_id).published


def test_recovery_is_idempotent(store):
    run = _run(store)
    store.create_publish_intent(run.run_id, TEXT)
    service = PublishingService(store, transport=FakeTransport(_published(store)))

    assert service.recover_run(run.run_id).recovered == 1
    assert service.recover_run(run.run_id).recovered == 0


def test_recovery_only_touches_the_run_it_was_asked_about(store):
    first = _run(store)
    second = _run(store)
    store.create_publish_intent(first.run_id, TEXT)
    store.create_publish_intent(second.run_id, "another post")

    service = PublishingService(store, transport=FakeTransport(_published(store)))
    report = service.recover_run(first.run_id)

    assert report.recovered == 1
    assert store.get_publish_intent(
        store.get_intent_for_run(second.run_id).intent_id
    ).state is PublishState.INTENT_CREATED


def test_the_store_survives_a_restart_with_its_publish_state_intact(tmp_path):
    """The record is durable, not process state."""
    path = tmp_path / "state" / "operational_state.db"
    store = StateStore(path)
    run = store.start_run(Workflow.BRANDING)
    service = PublishingService(store, transport=FakeTransport(_published(store)))
    intent_id = service.publish(PublishRequest(content=TEXT), run.run_id).intent_id
    store.close()

    reopened = StateStore(path)
    try:
        assert reopened.get_publish_intent(intent_id).state is PublishState.PUBLISHED
        assert reopened.get_publication_for_intent(intent_id).linkedin_post_id == POST_ID
        history = PublishingService(reopened).history
        assert [row.content_hash for row in history.recent_publications()] == [
            reopened.get_publish_intent(intent_id).content_hash
        ]
    finally:
        reopened.close()


def test_expiry_warnings_travel_back_with_a_successful_publish(store):
    """A publish can succeed and still be days away from failing forever."""
    run = _run(store)
    answer = replace(
        linkedin_result(PublicationOutcome.PUBLISHED, post_id=POST_ID),
        expiry_warning="the credential expires in 3 days",
    )
    report = _service(store, FakeTransport(answer)).publish(
        PublishRequest(content=TEXT), run.run_id
    )
    assert report.expiry_warning == "the credential expires in 3 days"
