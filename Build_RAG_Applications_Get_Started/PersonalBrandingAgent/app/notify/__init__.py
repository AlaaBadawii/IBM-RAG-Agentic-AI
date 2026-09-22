"""Operational notification: what happened reaches a person.

``PLAN.md`` Step 7. The system runs unattended, so a failure written only to a
log file is effectively invisible — and a post published under the user's name
is invisible for the opposite reason: it succeeded, so nothing reports it. This
package makes both visible, and it does so as **infrastructure rather than
Agent discretion**: the Agent is never responsible for remembering to notify
anyone, because the workflow wrapper reports the run's outcome, a failing phase
reports its failure, and a completed publish is reported as a post.

    from app.notify import NotificationService

    service = NotificationService(store)
    service.notify_run(run.run_id)               # the workflow wrapper
    service.notify_failure(failure)              # any phase, store optional
    service.notify_publication(post)             # a post that went out

One mailbox, one subject (``"Branding Agent"``), and a body that leads with the
thing itself — the issue description, or the published post's content. What a
message is *about* is carried as a :class:`NotificationKind` on the message, so
nothing has to infer it from the subject line.

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
  stays beside the workflows instead of reaching into them. A published post
  arrives as a :class:`PublishedPost` value for the same reason — the caller
  already holds it.
* **It does not make a post evidence.** Reporting a post is not indexing it:
  the content goes into an email and the delivery into the ``notifications``
  table, never into Chroma and never into the next post's context. Local
  publication history stays where Step 6 put it.

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
    NotificationKind,
    WaiverReason,
)
from app.notify.errors import (
    NotificationConfigurationError,
    NotificationDeliveryError,
)
from app.notify.messages import (
    SUBJECT,
    build_failure_message,
    build_post_message,
    build_run_message,
    outcome_label,
)
from app.notify.models import (
    NotificationMessage,
    NotificationReport,
    PublishedPost,
)
from app.notify.service import NotificationService
from app.notify.transport import EmailTransport, SMTPTransport

__all__ = [
    "EmailTransport",
    "NotificationConfigurationError",
    "NotificationDecision",
    "NotificationDeliveryError",
    "NotificationFailureCategory",
    "NotificationKind",
    "NotificationMessage",
    "NotificationReport",
    "NotificationService",
    "PublishedPost",
    "REQUIRED_SETTINGS",
    "SMTPConfig",
    "SMTPTransport",
    "SUBJECT",
    "WaiverReason",
    "build_failure_message",
    "build_post_message",
    "build_run_message",
    "missing_settings",
    "outcome_label",
    "require_smtp",
    "smtp_config",
]
