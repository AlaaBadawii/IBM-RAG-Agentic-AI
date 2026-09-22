"""Operational failure notification: a failure reaches a person.

``PLAN.md`` Step 7. The system runs unattended, so a failure written only to a
log file is effectively invisible. This package makes it visible, and it does
so as **infrastructure rather than Agent discretion**: the Agent is never
responsible for remembering to notify anyone, because the workflow wrapper
reports the run's outcome and a failing phase reports its failure.

    from app.notify import NotificationService

    service = NotificationService(store)
    service.notify_run(run.run_id)               # the workflow wrapper
    service.notify_failure(failure)              # any phase, store optional

The shape is the one the lower layers already have:

    workflow phase fails
            -> store.record_failure(...)          (Step 1, already written)
            -> NotificationService                (this package)
            -> EmailTransport -> SMTPTransport    (stdlib smtplib)
            -> notifications row                  (Step 1, delivery record)

What this package deliberately does **not** do:

* **It does not decide that something is a failure.** It reads a recorded run
  outcome and a recorded failure. Severity is decided by the layer that knows
  it, and the vocabulary is the run-outcome vocabulary Step 1 constrains.
* **It does not retry.** ``PLAN.md`` Step 7: a delivery failure is recorded and
  surfaced on the next run. Nothing here loops or backs off.
* **It does not orchestrate.** Nothing calls these methods yet: the workflow
  that calls ``notify_run`` after recording an outcome belongs to Step 11, and
  wiring the scheduled runs to it is that step's decision. The obligation Step
  7 accepts is that any outcome a workflow records is *reportable*, and that it
  is reportable *without* the Agent choosing to report it.
* **It does not import the publishing layer.** Publishing reports outcomes
  rather than raising, so a caller notifies on them; the notification service
  stays beside the workflows instead of reaching into them.

Configuration is entirely environmental (``app/config.py``): host, port,
sender, recipient, optional username/password, TLS mode and timeout. With no
mail configuration the application still runs and still records failures — it
simply cannot alert, which its delivery records state rather than hide.
"""
from app.notify.config import (
    REQUIRED_SETTINGS,
    SMTPConfig,
    missing_settings,
    require_smtp,
    smtp_config,
)
from app.notify.enums import (
    NotificationDecision,
    NotificationFailureCategory,
    WaiverReason,
)
from app.notify.errors import (
    NotificationConfigurationError,
    NotificationDeliveryError,
)
from app.notify.messages import (
    build_failure_message,
    build_run_message,
    outcome_label,
)
from app.notify.models import NotificationMessage, NotificationReport
from app.notify.service import NotificationService
from app.notify.transport import EmailTransport, SMTPTransport

__all__ = [
    "EmailTransport",
    "NotificationConfigurationError",
    "NotificationDecision",
    "NotificationDeliveryError",
    "NotificationFailureCategory",
    "NotificationMessage",
    "NotificationReport",
    "NotificationService",
    "REQUIRED_SETTINGS",
    "SMTPConfig",
    "SMTPTransport",
    "WaiverReason",
    "build_failure_message",
    "build_run_message",
    "missing_settings",
    "outcome_label",
    "require_smtp",
    "smtp_config",
]
