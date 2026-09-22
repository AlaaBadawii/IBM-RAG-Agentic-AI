"""Errors raised inside the notification layer, and never outside it.

Follows ``app/integrations/linkedin/errors.py``: the package's contract with
its callers is a *report*, not an exception. A notification that could not be
delivered is an outcome — recorded, categorized, and returned — because the
workflow failure it was carrying must survive it (``PLAN.md`` Step 7).

So the exception here exists for the short distance between "the mail server
refused" and "the delivery record that says so". It is translated into a
report before it can escape the package. The one thing that does escape is a
:mclass:`~app.errors.StateStoreError`: if the delivery record itself cannot be
written, the caller has to know.
"""
from app.errors import NotificationError
from app.notify.enums import NotificationFailureCategory


class NotificationDeliveryError(NotificationError):
    """One delivery attempt failed. Carries the remedy, not just the text.

    ``category`` is what a human acts on: configuration means go and set the
    variables, authentication means go and check the app password, transport
    means the mail server or the network was the problem and the attempt is
    worth repeating on the next run.
    """

    def __init__(self, category: NotificationFailureCategory, message: str) -> None:
        super().__init__(message)
        self.category = category


class NotificationConfigurationError(NotificationDeliveryError):
    """The notifier is not configured well enough to attempt a delivery.

    A subclass, because it is a delivery failure from the caller's point of
    view (nothing was sent) while remaining distinguishable from a delivery
    failure by cause. It is raised *before* any connection is opened, so a
    misconfigured notifier never spends a timeout on a socket it cannot use.
    """

    def __init__(self, message: str) -> None:
        super().__init__(NotificationFailureCategory.CONFIGURATION, message)
