"""Controlled vocabularies of the notification layer.

Mirrors the layout of ``app/state/enums.py`` and ``app/integrations/linkedin/
enums.py``: a decision is only useful if it can be branched on, and it can only
be branched on if its values are a closed set.

Note what is deliberately **not** here: a vocabulary for *severity*. The two
notifiable conditions are ``WORKFLOW_FAILED`` and
``REQUIRES_HUMAN_INTERVENTION``, which are the run outcomes Step 1 already
constrains in the database (``PLAN.md`` §2, §11). A second enum with the same
two values would be a place for the two to drift apart, which is precisely the
distinction an unattended system cannot afford to lose.
"""
from enum import Enum


class NotificationKind(str, Enum):
    """What a notification is *about*.

    The mailbox carries exactly two things and nothing else: a problem the
    system could not resolve on its own, and a post it published on the user's
    behalf. The kind is carried on the message rather than encoded in the
    subject, because the subject is deliberately the same for both — one
    mailbox rule has to be able to find all of them — so without this field the
    two would only be distinguishable by reading the body.
    """

    #: Something went wrong and a person has to hear about it.
    ISSUE = "issue"
    #: Something was published and a person should see what it was.
    PUBLICATION = "publication"


class NotificationDecision(str, Enum):
    """What happened to one notification request.

    ``WAIVED`` is not a failure and not a silent success: it is the decision
    that no notification was owed — a run that neither failed nor needs a
    person, or a repeat of a failure already reported. It is recorded in the
    report, never in the store, because there is nothing to deliver.
    """

    SENT = "sent"
    FAILED = "failed"
    WAIVED = "waived"


class WaiverReason(str, Enum):
    """Why no notification was sent.

    Kept apart from :class:`NotificationFailureCategory` because these are the
    opposite thing: a waiver is a *correct* decision that the system took
    deliberately, and conflating it with "the email could not be sent" would
    make a healthy run look like a broken one.
    """

    #: A normal termination — ``DO_NOT_PUBLISH``, or a run that has not
    #: finished yet. A no-op is not a failure (``PLAN.md`` Step 7).
    NORMAL_OUTCOME = "normal_outcome"
    #: The same failure, already reported inside the quiet window. The first
    #: occurrence is never suppressed; only its repetitions are.
    REPEAT_SUPPRESSED = "repeat_suppressed"


class NotificationFailureCategory(str, Enum):
    """Why a notification could not be delivered.

    Deliberately *not* the run-outcome vocabulary: this describes a problem
    with the alerting path, not with the work it was reporting. A notification
    failure must never be recorded as, or mistaken for, a workflow failure
    (``PLAN.md`` Step 7).

    The three values are the three distinct remedies: fix the configuration,
    fix the credential, or wait — the network or the mail server is the
    problem.
    """

    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    TRANSPORT = "transport"
