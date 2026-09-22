"""The notification service: the one place that decides whether to email.

``PLAN.md`` Step 7 is explicit that this is **not** an Agent decision:

    workflow phase fails → persist failure → notification service → email → user

So the decision lives here, in deterministic code, and it takes exactly two
inputs the layers below already produce — a run's recorded outcome, and a
recorded failure. Nothing has to be re-derived, and no phase has to remember
to notify: a phase records a structured failure, and the wrapper asks this
service to report the run.

    from app.notify import NotificationService

    service = NotificationService(store)
    service.notify_run(run.run_id)          # the workflow wrapper
    service.notify_failure(failure)         # a phase, with no store needed

Three rules the design rests on:

1. **A success is not a failure.** ``DO_NOT_PUBLISH`` — and a run that has not
   finished — is waived, not emailed. An alerting path that cries wolf on a
   normal no-op is one a person will filter into a folder and stop reading.
2. **A delivery failure is its own outcome.** It is recorded as a
   ``notifications`` row with ``delivery_state='failed'`` and a categorized
   reason, and returned as a report. It never raises past the caller, never
   touches the ``operational_failures`` row it was reporting, and never turns
   a failed run into a successful one.
3. **The first occurrence is never suppressed.** Noise control suppresses the
   *repetitions* of a failure already reported inside the quiet window; the
   first time a failure is seen, there is nothing to compare against and it
   goes out.

The store is optional, and only for one reason: the state store is itself a
phase that must be able to report a failure (``PLAN.md`` Step 7, reachability
table). Requiring a working store in order to say "the store is broken" would
be a contradiction, so a store-less service still composes and sends, and its
report says ``recorded is False``.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from app import config as app_config
from app.errors import StateStoreError
from app.logging_config import get_logger, redact
from app.notify.enums import (
    NotificationDecision,
    NotificationFailureCategory,
    WaiverReason,
)
from app.notify.errors import NotificationDeliveryError
from app.notify.messages import build_failure_message, build_run_message
from app.notify.models import NotificationMessage, NotificationReport
from app.notify.transport import EmailTransport, SMTPTransport
from app.state.enums import DeliveryState, RunOutcome
from app.state.models import (
    Notification,
    OperationalFailure,
    WorkflowRun,
    utc_now,
)
from app.state.store import StateStore

logger = get_logger(__name__)

#: How many recent deliveries are examined when looking for a repeat. A
#: bounded read: the question is "was this reported a moment ago", and the
#: answer cannot be in the tail of a long history.
_RECENT = 10

_NOTIFIABLE_ELSEWHERE = (
    "This run did not fail and does not need a person, so no notification was "
    "sent. DO_NOT_PUBLISH is a successful outcome, not a failure."
)
_UNFINISHED = (
    "This run has not finished. An unfinished run is a run in progress, not a "
    "failure, so no notification was sent."
)


class NotificationService:
    """Decides, composes, sends and records. Never retries, never raises past
    the caller except when the store itself refuses the delivery record."""

    def __init__(self, store: StateStore | None = None, *,
                 transport: EmailTransport | None = None,
                 repeat_after_hours: float | None = None) -> None:
        self._store = store
        self._transport = transport if transport is not None else SMTPTransport()
        self._repeat_after_hours = (
            app_config.SMTP_REPEAT_AFTER_HOURS
            if repeat_after_hours is None else repeat_after_hours
        )

    @property
    def transport(self) -> EmailTransport:
        return self._transport

    # -- entry points -------------------------------------------------------

    def notify_run(self, run_id: str) -> NotificationReport:
        """Report a finished run, if its outcome warrants it.

        The workflow wrapper calls this once, after recording the outcome. It
        needs no knowledge of email, and the decision is not the Agent's.
        """
        store = self._require_store("report a run")
        run = store.get_run(run_id)
        if run is None:
            raise StateStoreError(f"unknown run {run_id}")

        if run.outcome is None:
            return self._waive(WaiverReason.NORMAL_OUTCOME, _UNFINISHED)
        if run.outcome is RunOutcome.DO_NOT_PUBLISH:
            return self._waive(WaiverReason.NORMAL_OUTCOME, _NOTIFIABLE_ELSEWHERE)

        failures = store.list_failures(run_id=run_id)
        message = build_run_message(run, failures, secrets=self._secrets)
        return self._deliver(message, key=("run_id", run.run_id),
                             run_id=run.run_id, failure_id=None, subject_of=run)

    def notify_failure(self, failure: OperationalFailure) -> NotificationReport:
        """Report one recorded failure.

        The phase-facing entry point. It needs no store to *compose* — which is
        what makes the store itself reportable — and when a store was supplied
        the delivery outcome is recorded against the failure it concerns.
        """
        message = build_failure_message(failure, secrets=self._secrets)
        return self._deliver(message, key=("failure_id", failure.failure_id),
                             run_id=failure.run_id,
                             failure_id=failure.failure_id,
                             subject_of=failure)

    # -- the delivery itself ------------------------------------------------

    def _deliver(self, message: NotificationMessage, *,
                 key: tuple[str, str],
                 run_id: str | None,
                 failure_id: str | None,
                 subject_of: Any) -> NotificationReport:
        prior = self._recently_sent(key)
        if prior is not None:
            reason = (
                f"already reported at {prior.created_at} "
                f"({prior.subject}); repeats inside "
                f"{self._repeat_after_hours:g}h are suppressed so a recurring "
                f"failure cannot flood the mailbox"
            )
            logger.info("Notification suppressed: %s", reason)
            return self._waive(WaiverReason.REPEAT_SUPPRESSED, reason)

        category, error = self._attempt(message)
        if category is not None:
            record = self._record(DeliveryState.FAILED, message,
                                  run_id=run_id, failure_id=failure_id,
                                  error=error)
            logger.warning("Notification delivery failed (%s): %s",
                           category.value, error)
            return NotificationReport(
                decision=NotificationDecision.FAILED,
                message=(f"could not notify {self._transport.recipient or 'anyone'}"
                         f" about {self._describe(subject_of)}: {error}"),
                notification=record,
                category=category,
            )

        record = self._record(DeliveryState.SENT, message, run_id=run_id,
                              failure_id=failure_id, error=None)
        return NotificationReport(
            decision=NotificationDecision.SENT,
            message=(f"notified {self._transport.recipient} about "
                     f"{self._describe(subject_of)}"),
            notification=record,
        )

    def _attempt(self, message: NotificationMessage
                 ) -> tuple[NotificationFailureCategory | None, str | None]:
        """Send once. Returns the failure category and reason, or no failure.

        A transport is infrastructure standing between the system and a
        mailbox: whatever it raises, the run must still finish its own failure
        handling (``PLAN.md`` Step 7, Failure/recovery). An error this layer
        does not recognize is therefore a transport failure, not a crash.

        The reason is scrubbed **here**, before it is logged or recorded: it is
        text produced by something outside this process (a mail server, a
        provider's client), and a password that appears in it must not reach
        either the log or the delivery record. Scrubbing at the single point
        where the text enters the layer is what makes that true for both.
        """
        try:
            self._transport.send(message)
        except NotificationDeliveryError as exc:
            return exc.category, redact(str(exc), *self._secrets)
        except Exception as exc:  # noqa: BLE001 — see the docstring
            return (NotificationFailureCategory.TRANSPORT,
                    redact(f"the transport raised {type(exc).__name__}: {exc}",
                           *self._secrets))
        return None, None

    # -- noise control ------------------------------------------------------

    def _recently_sent(self, key: tuple[str, str]) -> Notification | None:
        """The delivery that already reported this event, inside the window.

        Only ``sent`` rows count: an alert that failed to go out is not an
        alert, and the next run must be free to try again (``PLAN.md`` Step 7,
        Failure/recovery). The *first* occurrence has no prior row at all, so
        it can never be suppressed by this.
        """
        store = self._store
        if store is None:
            return None
        field, value = key
        if field == "failure_id":
            recent = store.list_notifications(
                delivery_state=DeliveryState.SENT, failure_id=value, limit=_RECENT
            )
        else:
            recent = store.list_notifications(
                delivery_state=DeliveryState.SENT, run_id=value, limit=_RECENT
            )
        cutoff = utc_now() - timedelta(hours=self._repeat_after_hours)
        for notification in recent:  # newest first
            sent_at = _parse(notification.created_at)
            if sent_at is None or sent_at > cutoff:
                return notification
        return None

    # -- recording ----------------------------------------------------------

    def _record(self, state: DeliveryState, message: NotificationMessage, *,
                run_id: str | None, failure_id: str | None,
                error: str | None) -> Notification | None:
        """Persist the delivery outcome, or return ``None`` without a store.

        The ``notifications`` row is separate from the failure it reports, by
        design: a delivery failure must never replace or erase the workflow
        failure (``PLAN.md`` Step 7). This writes only the notification.
        """
        store = self._store
        if store is None:
            return None
        return store.record_notification(
            recipient=self._transport.recipient,
            subject=message.subject,
            delivery_state=state,
            failure_id=failure_id,
            run_id=run_id,
            transport=self._transport.name,
            smtp_config=self._transport.describe(),
            error_message=error,
        )

    # -- helpers ------------------------------------------------------------

    @property
    def _secrets(self) -> tuple[str, ...]:
        """Secrets this service knows about beyond the environment's.

        A transport that holds its own configuration holds its own password;
        the composer is told about it so the password cannot be rendered into
        a message that quotes back an error from the mail server.
        """
        config = getattr(self._transport, "config", None)
        secrets = getattr(config, "secrets", None)
        return tuple(secrets()) if callable(secrets) else ()

    def _require_store(self, what: str) -> StateStore:
        if self._store is None:
            raise StateStoreError(
                f"no state store was supplied, so it is not possible to {what}: "
                "the failure being reported cannot be read"
            )
        return self._store

    @staticmethod
    def _describe(subject_of: Any) -> str:
        if isinstance(subject_of, WorkflowRun):
            return f"run {subject_of.run_id}"
        if isinstance(subject_of, OperationalFailure):
            return f"the failure in phase {subject_of.phase}"
        return "the failure"

    @staticmethod
    def _waive(waiver: WaiverReason, reason: str) -> NotificationReport:
        return NotificationReport(decision=NotificationDecision.WAIVED,
                                  message=reason, waiver=waiver)


def _parse(moment: str) -> datetime | None:
    """Parse a stored timestamp, defensively.

    Every timestamp this system writes is the store's canonical UTC ISO form,
    so this normally cannot fail; it returns ``None`` rather than raising
    because an unreadable timestamp must not stop an alert from going out.
    """
    try:
        parsed = datetime.fromisoformat(moment)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
