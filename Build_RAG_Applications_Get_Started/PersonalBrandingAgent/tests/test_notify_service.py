"""Step 7: the notification service — decision, delivery, record.

Every test here runs offline. The transport is a fake that captures composed
messages, no SMTP connection is opened, and no credential is read. What is
under test is the decision (which outcomes are worth an email), the record
(what a delivery left behind), and the two things ``PLAN.md`` Step 7 refuses
to allow: a secret in a message, and an alerting failure that swallows or
replaces the failure it was reporting.
"""
import pytest

from app import paths
from app.errors import StateStoreError
from app.notify import (
    SMTPConfig,
    SUBJECT,
    NotificationDecision,
    NotificationDeliveryError,
    NotificationFailureCategory,
    NotificationKind,
    NotificationService,
    PublishedPost,
    WaiverReason,
)
from app.notify.errors import NotificationConfigurationError
from app.state.enums import DeliveryState, RunOutcome
from app.state.store import StateStore

TEXT = "Publishing failed on the post request."
NOTIFY_PACKAGE = paths.PROJECT_ROOT / "app" / "notify"
PUBLISHING_PACKAGE = paths.PROJECT_ROOT / "app" / "publishing"
PHASES = (
    "source_registry_loading",
    "sync_change_detection",
    "file_discovery",
    "ingestion",
    "embedding",
    "retrieval",
    "context_construction",
    "generation",
    "verification",
    "agent_reasoning",
    "linkedin_authentication",
    "linkedin_publish",
    "ambiguous_publication",
    "state_store",
    "scheduling_lock",
    "recovery",
)


# --- fakes -------------------------------------------------------------------

class CapturingTransport:
    """Stands in for the SMTP transport: captures messages, can be told to fail.

    Implements the same four-member contract as ``SMTPTransport``, which is the
    point of the interface: a fake and the real thing are interchangeable, so
    nothing below has to know which one it is holding.
    """

    name = "fake"

    def __init__(self, *, fail_with: BaseException | None = None,
                 recipient: str = "owner@example.com", config=None) -> None:
        self.messages = []
        self.fail_with = fail_with
        self._recipient = recipient
        self.config = config

    @property
    def recipient(self) -> str:
        return self._recipient

    def describe(self) -> str:
        return "fake transport"

    def send(self, message) -> None:
        self.messages.append(message)
        if self.fail_with is not None:
            raise self.fail_with

    @property
    def called(self) -> bool:
        return bool(self.messages)


@pytest.fixture
def store(tmp_path) -> StateStore:
    created = StateStore(tmp_path / "state" / "operational_state.db")
    yield created
    created.close()


def _run(store: StateStore, workflow: str = "branding"):
    return store.start_run(workflow)


def _failure(store: StateStore, run_id, *, phase: str = "linkedin_publish",
             message: str = TEXT, category: str = "TRANSPORT",
             retryable: bool = True, human: bool = False,
             dedupe_key: str | None = None):
    return store.record_failure(
        phase=phase, error_category=category, message=message,
        retryable=retryable, requires_human_intervention=human, run_id=run_id,
        workflow="branding", dedupe_key=dedupe_key,
    )


def _finished(store: StateStore, outcome: RunOutcome, *, phase="linkedin_publish"):
    """A run that terminated as ``outcome``, with one failure recorded."""
    run = _run(store)
    failure = _failure(store, run.run_id, phase=phase)
    store.finish_run(run.run_id, outcome, failed_phase=phase)
    return run, failure


def _service(store, transport, **kwargs) -> NotificationService:
    return NotificationService(store, transport=transport, **kwargs)


# --- a failed run notifies ---------------------------------------------------

def test_a_failed_run_produces_exactly_one_notification(store):
    """Acceptance: a notification is sent for a failed unattended run."""
    run, _ = _finished(store, RunOutcome.WORKFLOW_FAILED)
    transport = CapturingTransport()
    report = _service(store, transport).notify_run(run.run_id)

    assert report.decision is NotificationDecision.SENT
    assert report.sent
    assert len(transport.messages) == 1

    message = transport.messages[0]
    assert message.kind is NotificationKind.ISSUE
    assert message.subject == SUBJECT
    # The outcome is still carried — in the body, where the metadata lives.
    assert "Outcome:" in message.body and "WORKFLOW_FAILED" in message.body
    # Every field PLAN.md Step 7 requires the content to carry.
    body = message.body
    assert "Workflow:" in body and "branding" in body
    assert "Phase:" in body and "linkedin_publish" in body
    assert "Run:" in body and run.run_id in body
    assert "Error category:" in body and "TRANSPORT" in body
    assert TEXT in body
    assert "Retryable:" in body
    assert "Requires human intervention:" in body
    assert run.started_at in body
    assert "Notified:" in body


def test_the_delivery_is_recorded_against_the_run(store):
    run, _ = _finished(store, RunOutcome.WORKFLOW_FAILED)
    transport = CapturingTransport(recipient="owner@example.com")
    report = _service(store, transport).notify_run(run.run_id)

    stored = store.get_notification(report.notification.notification_id)
    assert stored.delivery_state is DeliveryState.SENT
    assert stored.delivered_at is not None
    assert stored.attempted_at is not None
    assert stored.recipient == "owner@example.com"
    assert stored.run_id == run.run_id
    assert stored.transport == "fake"
    assert stored.error_message is None
    assert stored.subject == SUBJECT
    assert store.list_notifications(run_id=run.run_id) == [stored]


def test_the_message_carries_every_failure_recorded_against_the_run(store):
    run = _run(store)
    _failure(store, run.run_id, phase="retrieval", message="index missing",
             category="RETRIEVAL")
    _failure(store, run.run_id, phase="linkedin_publish", message=TEXT)
    store.finish_run(run.run_id, RunOutcome.WORKFLOW_FAILED,
                     failed_phase="linkedin_publish")

    transport = CapturingTransport()
    _service(store, transport).notify_run(run.run_id)

    body = transport.messages[0].body
    assert "index missing" in body
    assert TEXT in body
    assert "--- Failure 1 of 2 ---" in body
    assert "--- Failure 2 of 2 ---" in body


def test_a_failed_run_with_no_failure_record_still_notifies(store):
    """The outcome is the fact; a missing explanation is not a reason for silence."""
    run = _run(store)
    store.finish_run(run.run_id, RunOutcome.WORKFLOW_FAILED)

    transport = CapturingTransport()
    report = _service(store, transport).notify_run(run.run_id)

    assert report.sent
    assert "No failure record was written" in transport.messages[0].body


# --- human intervention is a distinct notification ---------------------------

def test_human_intervention_notifies_with_its_own_outcome(store):
    """The distinction PLAN.md §11 draws has to survive into the mailbox."""
    run, _ = _finished(store, RunOutcome.REQUIRES_HUMAN_INTERVENTION)
    transport = CapturingTransport()
    _service(store, transport).notify_run(run.run_id)

    message = transport.messages[0]
    assert "REQUIRES_HUMAN_INTERVENTION" in message.body
    assert "WORKFLOW_FAILED" not in message.body
    assert "Action required" in message.body
    assert "cannot be resolved automatically" in message.body


def test_a_definitive_failure_asks_for_nothing(store):
    run, _ = _finished(store, RunOutcome.WORKFLOW_FAILED)
    transport = CapturingTransport()
    _service(store, transport).notify_run(run.run_id)

    body = transport.messages[0].body
    assert "Action required" not in body
    assert "No action is required" in body


def test_a_failure_that_needs_a_person_is_labelled_as_such(store):
    run = _run(store)
    failure = _failure(store, run.run_id, message="the token expired",
                       category="AUTHENTICATION", retryable=False, human=True)
    transport = CapturingTransport()
    report = _service(store, transport).notify_failure(failure)

    assert report.sent
    message = transport.messages[0]
    assert message.subject == SUBJECT
    assert "REQUIRES_HUMAN_INTERVENTION" in message.body
    assert "Requires human intervention:    yes" in message.body


# --- a normal run does not ---------------------------------------------------

def test_a_do_not_publish_run_sends_nothing(store):
    """Acceptance: no notification is sent for a normal DO_NOT_PUBLISH run."""
    run = _run(store)
    store.finish_run(run.run_id, RunOutcome.DO_NOT_PUBLISH)

    transport = CapturingTransport()
    report = _service(store, transport).notify_run(run.run_id)

    assert report.decision is NotificationDecision.WAIVED
    assert report.waiver is WaiverReason.NORMAL_OUTCOME
    assert not transport.called, "a successful no-op produced an email"
    assert store.list_notifications() == []


def test_a_do_not_publish_run_notifies_even_with_a_recorded_failure(store):
    """A recovered phase failure does not turn a successful run into an alert.

    The outcome is what the run terminated as, and that is the recorded fact —
    not the presence of a failure row from a phase the run got past.
    """
    run = _run(store)
    _failure(store, run.run_id, phase="retrieval", retryable=True)
    store.finish_run(run.run_id, RunOutcome.DO_NOT_PUBLISH)

    transport = CapturingTransport()
    assert _service(store, transport).notify_run(run.run_id).waived
    assert not transport.called


def test_an_unfinished_run_sends_nothing(store):
    run = _run(store)
    transport = CapturingTransport()
    report = _service(store, transport).notify_run(run.run_id)

    assert report.waived
    assert report.waiver is WaiverReason.NORMAL_OUTCOME
    assert not transport.called


def test_an_unknown_run_is_a_store_error(store):
    with pytest.raises(StateStoreError, match="unknown run"):
        _service(store, CapturingTransport()).notify_run("run-does-not-exist")


def test_a_run_cannot_be_reported_without_a_store():
    """Reading the outcome is the one thing that needs the store."""
    with pytest.raises(StateStoreError, match="no state store"):
        NotificationService(transport=CapturingTransport()).notify_run("run-1")


# --- every phase can reach it ------------------------------------------------

@pytest.mark.parametrize("phase", PHASES)
def test_every_phase_in_the_reachability_table_can_report(store, phase):
    """Acceptance: every phase can raise a notifiable failure.

    The service is handed a recorded failure and a transport. It reads no
    module of any phase, which is exactly why a phase cannot fail to be
    reportable: reporting is not something the phase does, it is something
    done with what the phase recorded.
    """
    run = _run(store)
    failure = _failure(store, run.run_id, phase=phase,
                       message=f"{phase} broke", category="UNKNOWN")
    transport = CapturingTransport()
    report = _service(store, transport).notify_failure(failure)

    assert report.sent
    assert transport.messages[0].subject == SUBJECT
    assert phase in transport.messages[0].body
    assert f"{phase} broke" in transport.messages[0].body


def test_a_store_failure_can_be_notified_without_a_store(store):
    """The state store is itself a phase that must be able to report.

    Requiring a working store in order to say "the store is broken" would be a
    contradiction, so the store is optional for exactly this case — and the
    report says the delivery could not be recorded rather than pretending it
    was.
    """
    failure = _failure(store, _run(store).run_id, phase="state_store",
                       message="the database is locked", category="STATE_STORE")
    transport = CapturingTransport()
    report = NotificationService(transport=transport).notify_failure(failure)

    assert report.sent
    assert not report.recorded
    assert report.notification is None
    assert "database is locked" in transport.messages[0].body
    # The failure itself is still in the store, written before the alert.
    assert store.list_failures()[0].failure_id == failure.failure_id


# --- a delivery failure is its own outcome -----------------------------------

def test_a_transport_failure_is_recorded_and_leaves_the_failure_alone(store):
    """Acceptance: the delivery failure does not erase the workflow failure.

    The two are separately observable: the failure row is untouched, the run's
    outcome is untouched, and the delivery has a row of its own saying it did
    not go out.
    """
    run, failure = _finished(store, RunOutcome.WORKFLOW_FAILED)
    transport = CapturingTransport(
        fail_with=NotificationDeliveryError(
            NotificationFailureCategory.TRANSPORT,
            "SMTP delivery failed: SMTPServerDisconnected: connection reset",
        )
    )
    report = _service(store, transport).notify_run(run.run_id)

    assert report.decision is NotificationDecision.FAILED
    assert report.category is NotificationFailureCategory.TRANSPORT
    assert report.notification is not None
    assert report.notification.delivery_state is DeliveryState.FAILED
    assert report.notification.delivered_at is None
    assert "SMTPServerDisconnected" in report.notification.error_message

    # The original failure is intact and still visible.
    stored = store.get_failure(failure.failure_id)
    assert stored.message == TEXT
    assert stored.occurrence_count == 1
    assert store.get_run(run.run_id).outcome is RunOutcome.WORKFLOW_FAILED
    assert store.list_failures(run_id=run.run_id) == [stored]


def test_the_two_outcomes_are_separately_observable(store):
    run, _ = _finished(store, RunOutcome.WORKFLOW_FAILED)
    transport = CapturingTransport(
        fail_with=NotificationDeliveryError(
            NotificationFailureCategory.TRANSPORT, "timed out"))
    _service(store, transport).notify_run(run.run_id)

    assert len(store.list_failures(run_id=run.run_id)) == 1
    assert len(store.list_notifications(run_id=run.run_id)) == 1
    assert store.list_notifications(
        delivery_state=DeliveryState.FAILED, run_id=run.run_id
    )[0].delivery_state is DeliveryState.FAILED


def test_a_configuration_failure_has_its_own_category(store):
    """A missing address and a dead mail server are not the same problem."""
    run, _ = _finished(store, RunOutcome.WORKFLOW_FAILED)
    transport = CapturingTransport(fail_with=NotificationConfigurationError(
        "no email transport is configured: SMTP_HOST, SMTP_SENDER and "
        "SMTP_RECIPIENT must be set before a notification can be sent"
    ))
    report = _service(store, transport).notify_run(run.run_id)

    assert report.failed
    assert report.category is NotificationFailureCategory.CONFIGURATION
    assert "SMTP_HOST" in report.notification.error_message


def test_an_unexpected_transport_error_still_leaves_the_run_intact(store):
    """Infrastructure standing between the system and a mailbox cannot crash it."""
    run, _ = _finished(store, RunOutcome.WORKFLOW_FAILED)
    transport = CapturingTransport(fail_with=ValueError("the provider changed"))
    report = _service(store, transport).notify_run(run.run_id)

    assert report.failed
    assert report.category is NotificationFailureCategory.TRANSPORT
    assert "ValueError" in report.notification.error_message
    assert store.get_run(run.run_id).outcome is RunOutcome.WORKFLOW_FAILED


def test_a_notification_never_turns_a_failed_run_into_a_success(store):
    run, _ = _finished(store, RunOutcome.WORKFLOW_FAILED)
    transport = CapturingTransport(fail_with=ValueError("boom"))
    report = _service(store, transport).notify_run(run.run_id)

    assert not report.sent
    assert store.get_run(run.run_id).outcome is RunOutcome.WORKFLOW_FAILED
    assert store.list_notifications()[0].delivery_state is DeliveryState.FAILED


# --- noise control -----------------------------------------------------------

def test_the_first_occurrence_is_never_suppressed_and_repeats_are(store):
    """Acceptance: duplicate suppression never hides a first occurrence."""
    run = _run(store)
    failure = _failure(store, run.run_id, dedupe_key="retrieval:index_missing")
    service = _service(store, CapturingTransport())
    transport = service.transport

    first = service.notify_failure(failure)
    # The same failure, seen again: the row is the same row, its count grows.
    again = store.record_failure(
        phase=failure.phase, error_category=failure.error_category,
        message=failure.message, run_id=failure.run_id,
        dedupe_key="retrieval:index_missing",
    )
    second = service.notify_failure(again)

    assert first.sent, "the first occurrence was suppressed"
    assert len(transport.messages) == 1
    assert second.decision is NotificationDecision.WAIVED
    assert second.waiver is WaiverReason.REPEAT_SUPPRESSED
    assert "already reported" in second.message
    assert again.occurrence_count == 2


def test_a_repeat_notifies_again_once_the_quiet_window_has_passed(store):
    run = _run(store)
    failure = _failure(store, run.run_id, dedupe_key="duplicate-key")
    transport = CapturingTransport()
    service = _service(store, transport, repeat_after_hours=0)

    assert service.notify_failure(failure).sent
    assert service.notify_failure(failure).sent

    assert len(transport.messages) == 2
    assert store.list_notifications(delivery_state=DeliveryState.SENT).__len__() == 2


def test_a_failed_delivery_does_not_count_as_having_reported_it(store):
    """An alert that never went out is not an alert; the next run tries again."""
    run, failure = _finished(store, RunOutcome.WORKFLOW_FAILED)
    broken = CapturingTransport(fail_with=ValueError("the mail server is down"))
    assert _service(store, broken).notify_run(run.run_id).failed

    transport = CapturingTransport()
    report = _service(store, transport).notify_run(run.run_id)

    assert report.sent
    assert transport.called


def test_a_repeat_is_suppressed_per_failure_not_globally(store):
    """Two different failures are two different emails."""
    run = _run(store)
    first = _failure(store, run.run_id, phase="retrieval", dedupe_key="a")
    second = _failure(store, run.run_id, phase="generation", dedupe_key="b")
    transport = CapturingTransport()
    service = _service(store, transport)

    assert service.notify_failure(first).sent
    assert service.notify_failure(second).sent
    assert len(transport.messages) == 2


# --- secrets -----------------------------------------------------------------

def test_no_secret_appears_in_a_notification_or_its_delivery_record(store):
    """Acceptance: no secret value can appear in a notification."""
    config = SMTPConfig(host="smtp.example.com", port=587,
                        sender="owner@example.com",
                        recipient="owner@example.com",
                        username="owner@example.com",
                        password="app-password-xyz")
    monkeypatch_secret = "env-secret-value"
    import os

    os.environ["LINKEDIN_CLIENT_SECRET"] = monkeypatch_secret
    try:
        run = _run(store)
        failure = _failure(
            store, run.run_id,
            message=(f"the mail server said the password app-password-xyz was "
                     f"wrong and the token {monkeypatch_secret} was expired"),
            category="AUTHENTICATION",
        )
        transport = CapturingTransport(config=config)
        report = _service(store, transport).notify_failure(failure)
    finally:
        del os.environ["LINKEDIN_CLIENT_SECRET"]

    rendered = transport.messages[0].render()
    assert "app-password-xyz" not in rendered
    assert monkeypatch_secret not in rendered
    assert "[REDACTED]" in rendered
    assert "app-password-xyz" not in report.notification.subject
    assert "app-password-xyz" not in report.message


def test_a_delivery_error_is_scrubbed_before_it_is_recorded(store):
    """The text a mail server returns is external input, not a trusted string."""
    config = SMTPConfig(host="h", port=587, sender="a@b.c", recipient="d@e.f",
                        username="a@b.c", password="app-password-xyz")
    run, _ = _finished(store, RunOutcome.WORKFLOW_FAILED)
    transport = CapturingTransport(config=config, fail_with=ValueError(
        "535 authentication failed for app-password-xyz"))
    report = _service(store, transport).notify_run(run.run_id)

    assert "app-password-xyz" not in report.notification.error_message


def test_the_configuration_used_is_recorded_without_its_credentials(store):
    config = SMTPConfig(host="smtp.example.com", port=587, sender="a@example.com",
                        recipient="owner@example.com", username="a@example.com",
                        password="app-password-xyz")
    run, _ = _finished(store, RunOutcome.WORKFLOW_FAILED)
    transport = CapturingTransport(config=config)
    report = _service(store, transport).notify_run(run.run_id)

    recorded = store.get_notification(report.notification.notification_id)
    assert recorded.recipient == "owner@example.com"
    assert recorded.transport == "fake"
    assert "app-password-xyz" not in (recorded.smtp_config or "")


# --- one mailbox, two kinds of message ----------------------------------------
#
# Follow-up to Step 7. The mailbox receives both the problems the system could
# not resolve and the posts it published, so every notification carries the
# same subject and the body leads with the thing itself. These are the focused
# tests for that: one subject, two kinds, and the supplied content present in
# the body of each.

ISSUE_TEXT = "the retrieval index is missing its embedding column"
POST_TEXT = ("Today I learned that a retrieval pipeline is mostly a story about "
             "what you throw away. Here is how I decide what stays.")


def _post(**overrides) -> PublishedPost:
    values = dict(content=POST_TEXT, post_id="urn:li:share:7001",
                  url="https://www.linkedin.com/feed/update/urn:li:share:7001",
                  published_at="2026-09-22T09:00:00+00:00")
    values.update(overrides)
    return PublishedPost(**values)


def test_an_issue_notification_uses_the_branding_agent_subject(store):
    """Acceptance: the failure email's subject is exactly ``Branding Agent``."""
    run = _run(store)
    failure = _failure(store, run.run_id, message=ISSUE_TEXT,
                       category="RETRIEVAL")
    transport = CapturingTransport()
    report = _service(store, transport).notify_failure(failure)

    assert report.sent
    message = transport.messages[0]
    assert message.subject == "Branding Agent"
    assert message.subject == SUBJECT
    assert message.kind is NotificationKind.ISSUE
    assert store.get_notification(report.notification.notification_id).subject \
        == "Branding Agent"


def test_a_run_notification_uses_the_same_subject_as_a_phase_notification(store):
    """A mailbox rule that finds one has to find the other."""
    failed, _ = _finished(store, RunOutcome.WORKFLOW_FAILED)
    human, _ = _finished(store, RunOutcome.REQUIRES_HUMAN_INTERVENTION)

    transport = CapturingTransport()
    service = _service(store, transport)
    service.notify_run(failed.run_id)
    service.notify_run(human.run_id)

    subjects = [message.subject for message in transport.messages]
    assert subjects == ["Branding Agent", "Branding Agent"]


def test_the_issue_email_body_contains_the_supplied_description(store):
    """Acceptance: the body carries the issue description, not just metadata.

    It leads with it: the description a phase recorded is the answer to "what
    is wrong", and it is quoted first and unaltered.
    """
    run = _run(store)
    failure = _failure(store, run.run_id, message=ISSUE_TEXT,
                       category="RETRIEVAL")
    transport = CapturingTransport()
    _service(store, transport).notify_failure(failure)

    body = transport.messages[0].body
    assert ISSUE_TEXT in body
    # First content line, before any of the structured fields.
    assert body.splitlines()[2] == ISSUE_TEXT
    assert body.index(ISSUE_TEXT) < body.index("Phase:")


def test_a_run_email_leads_with_every_recorded_description(store):
    run = _run(store)
    _failure(store, run.run_id, phase="retrieval", message=ISSUE_TEXT,
             category="RETRIEVAL")
    _failure(store, run.run_id, message=TEXT)
    store.finish_run(run.run_id, RunOutcome.WORKFLOW_FAILED,
                     failed_phase="linkedin_publish")

    transport = CapturingTransport()
    _service(store, transport).notify_run(run.run_id)

    body = transport.messages[0].body
    assert ISSUE_TEXT in body and TEXT in body
    assert body.index(ISSUE_TEXT) < body.index("Outcome:")
    assert body.index(TEXT) < body.index("Outcome:")


# --- the other thing the mailbox carries --------------------------------------

def test_a_publication_notification_uses_the_branding_agent_subject(store):
    """Acceptance: the publication email's subject is ``Branding Agent`` too."""
    transport = CapturingTransport()
    report = _service(store, transport).notify_publication(_post())

    assert report.sent
    message = transport.messages[0]
    assert message.subject == "Branding Agent"
    assert message.kind is NotificationKind.PUBLICATION


def test_the_publication_email_body_contains_the_published_post(store):
    """Acceptance: the body carries the post content as supplied."""
    transport = CapturingTransport()
    _service(store, transport).notify_publication(_post())

    body = transport.messages[0].body
    assert POST_TEXT in body
    assert body.splitlines()[2] == POST_TEXT, "the post is not led with"
    assert "urn:li:share:7001" in body


def test_a_publication_is_reported_even_though_the_run_did_not_fail(store):
    """The half the failure path cannot reach.

    A successful publish terminates ``DO_NOT_PUBLISH`` and is waived, so if a
    publication did not notify on its own, nothing would ever tell the user
    what went out under their name.
    """
    run = _run(store)
    store.finish_run(run.run_id, RunOutcome.DO_NOT_PUBLISH)
    transport = CapturingTransport()
    service = _service(store, transport)

    assert service.notify_run(run.run_id).waived, "a success is waived"
    report = service.notify_publication(_post(), run_id=run.run_id)

    assert report.sent
    assert transport.called
    recorded = store.get_notification(report.notification.notification_id)
    assert recorded.delivery_state is DeliveryState.SENT
    assert recorded.run_id == run.run_id
    assert recorded.failure_id is None, "a post is not a failure"


def test_a_publication_is_not_suppressed_by_the_repeat_window(store):
    """A post is an event, not a condition: two posts are two things to read."""
    transport = CapturingTransport()
    service = _service(store, transport, repeat_after_hours=24)

    first = service.notify_publication(_post(post_id="urn:li:share:1"))
    second = service.notify_publication(_post(post_id="urn:li:share:2"))

    assert first.sent and second.sent, "the second post was suppressed"
    assert len(transport.messages) == 2


def test_a_publication_with_no_identifiers_still_composes(store):
    """Nothing about a publish is guaranteed to be recorded but the content."""
    transport = CapturingTransport()
    report = _service(store, transport).notify_publication(
        PublishedPost(content=POST_TEXT))

    assert report.sent
    body = transport.messages[0].body
    assert POST_TEXT in body
    assert "(not recorded)" in body


def test_a_publication_needs_no_store(store):
    """Same contract as a failure: composing never requires the store."""
    transport = CapturingTransport()
    report = NotificationService(transport=transport).notify_publication(_post())

    assert report.sent
    assert report.recorded is False


def test_a_failed_publication_notification_is_recorded_without_a_failure(store):
    """A delivery failure is reported as such and invents no failure row."""
    transport = CapturingTransport(
        fail_with=NotificationDeliveryError(
            NotificationFailureCategory.TRANSPORT, "the mail server refused")
    )
    report = _service(store, transport).notify_publication(_post())

    assert report.failed
    recorded = store.get_notification(report.notification.notification_id)
    assert recorded.delivery_state is DeliveryState.FAILED
    assert recorded.failure_id is None
    assert store.list_failures() == [], "a notification failure wrote a failure"


def test_no_secret_reaches_a_publication_email(store):
    """Acceptance: the SMTP password is never included, in either kind."""
    config = SMTPConfig(host="smtp.example.com", port=587,
                        sender="owner@example.com",
                        recipient="owner@example.com",
                        username="owner@example.com",
                        password="app-password-xyz")
    transport = CapturingTransport(config=config)
    report = _service(store, transport).notify_publication(
        _post(content=f"{POST_TEXT} (sent with app-password-xyz)"))

    rendered = transport.messages[0].render()
    assert "app-password-xyz" not in rendered
    assert "[REDACTED]" in rendered
    assert "app-password-xyz" not in report.message
    recorded = store.get_notification(report.notification.notification_id)
    assert "app-password-xyz" not in recorded.subject
    assert "app-password-xyz" not in (recorded.smtp_config or "")
    assert "app-password-xyz" not in (recorded.error_message or "")


def test_the_reported_post_is_never_indexed_anywhere(store):
    """The post is reported, not learned from: no store row carries its text.

    ``PLAN.md`` §6 keeps publication history out of Chroma, and Step 6 does not
    write post content into the state store either. Notifying about a post must
    not become the loophole: the delivery row records that a message was sent
    and to whom, never what it said.
    """
    transport = CapturingTransport()
    report = _service(store, transport).notify_publication(_post())

    recorded = store.get_notification(report.notification.notification_id)
    for value in vars(recorded).values():
        assert POST_TEXT not in str(value)


# --- the layers stay apart ---------------------------------------------------

def _imports(path) -> list[str]:
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


@pytest.mark.parametrize("module", sorted(NOTIFY_PACKAGE.glob("*.py")),
                         ids=lambda path: path.name)
def test_the_notification_layer_cannot_reach_the_knowledge_layer(module):
    """Notification is infrastructure beside the workflows, not inside them.

    Enforced structurally for the same reason ``app/publishing`` is: a
    behavioural test could only show what did not happen in the cases it tried,
    while an import scan shows there is no code path at all.
    """
    forbidden = ("chroma", "langchain", "app.retrieval", "app.ingestion",
                 "app.publishing")
    offenders = [
        name for name in _imports(module)
        if any(name == bad or name.startswith(f"{bad}.") for bad in forbidden)
    ]
    assert not offenders, f"{module.name} reaches a lower layer: {offenders}"


@pytest.mark.parametrize("module", sorted(PUBLISHING_PACKAGE.glob("*.py")),
                         ids=lambda path: path.name)
def test_the_publishing_layer_cannot_send_a_notification(module):
    """``PLAN.md`` Step 7: SMTP belongs to the notification layer.

    A publish path that could compose and send mail would be a second place
    deciding who gets told what — and the decision to notify is deliberately
    single, deterministic, and outside the layer that publishes.
    """
    forbidden = ("smtplib", "app.notify")
    offenders = [
        name for name in _imports(module)
        if any(name == bad or name.startswith(f"{bad}.") for bad in forbidden)
    ]
    assert not offenders, f"{module.name} can send a notification: {offenders}"
