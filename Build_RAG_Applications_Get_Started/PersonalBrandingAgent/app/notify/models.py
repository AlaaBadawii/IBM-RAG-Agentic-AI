"""Value objects of the notification layer.

Small, immutable, and inert: nothing here opens a socket, reads configuration
or touches the store, so a caller can build, compare, log or record one of
these values without triggering anything.
"""
from dataclasses import dataclass

from app.notify.enums import (
    NotificationDecision,
    NotificationFailureCategory,
    WaiverReason,
)
from app.state.models import Notification


@dataclass(frozen=True)
class NotificationMessage:
    """One email, as content: a subject and a body.

    Deliberately not addressed. *Where* a message goes is the transport's
    business — that is what makes the interface provider-agnostic
    (``PLAN.md`` §12.1 decision 3) — and keeping the addresses out means a
    message can be composed, tested and compared without a transport existing.
    """

    subject: str
    body: str

    def render(self) -> str:
        """The whole message as one string, for logging and test assertions."""
        return f"{self.subject}\n\n{self.body}"


@dataclass(frozen=True)
class NotificationReport:
    """What the notification layer did about one failure, or one run.

    The counterpart of ``PublishReport`` for the alerting path: every case is
    a report, because the caller is an unattended workflow that has to keep
    going. Distinguishing the three cases matters —

    * ``SENT`` — the alert is out;
    * ``FAILED`` — an alert was owed and did not go. ``notification`` carries
      the delivery record (``delivery_state='failed'``) that makes it visible,
      and ``category`` says whether to fix configuration, a credential, or
      nothing at all;
    * ``WAIVED`` — nothing was owed, and ``waiver`` says why.

    A failed delivery is **not** an exception and never replaces the failure
    it was reporting: that row was written before this ran and is untouched by
    it (``PLAN.md`` Step 7).
    """

    decision: NotificationDecision
    message: str
    notification: Notification | None = None
    waiver: WaiverReason | None = None
    category: NotificationFailureCategory | None = None

    @property
    def sent(self) -> bool:
        return self.decision is NotificationDecision.SENT

    @property
    def failed(self) -> bool:
        return self.decision is NotificationDecision.FAILED

    @property
    def waived(self) -> bool:
        return self.decision is NotificationDecision.WAIVED

    @property
    def recorded(self) -> bool:
        """Whether this attempt left a delivery record behind.

        ``False`` only when the notifier was built without a store — the case
        of reporting that the store itself is broken, where requiring it in
        order to speak would be a contradiction.
        """
        return self.notification is not None
