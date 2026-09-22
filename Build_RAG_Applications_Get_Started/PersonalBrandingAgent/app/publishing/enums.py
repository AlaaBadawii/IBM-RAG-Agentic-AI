"""Controlled vocabularies of the publishing service (``PLAN.md`` Step 6).

The publish state machine itself lives in ``app/state/enums.py``
(``PublishState``), because the database constrains it. What is defined here is
the *service's* view of a publish: what it decided, which duplicate check
refused it, and how an interrupted attempt was recovered. As everywhere else in
this repository, these are closed sets so a caller can branch on them instead
of matching on a message.
"""
from enum import Enum


class PublishDecision(str, Enum):
    """What the publishing service did with one request.

    The three non-refusal values are exactly the terminal ``PublishState``
    values, deliberately: a decision and the durable outcome it produced must
    not be able to drift apart. ``REFUSED`` is the one the state store has no
    equivalent for — nothing was written and nothing was sent, so there is no
    publication to record, and calling it a "failure" would put a
    never-attempted request in the same bucket as one LinkedIn rejected.
    """

    PUBLISHED = "published"
    FAILED = "failed"
    UNKNOWN_REQUIRES_REVIEW = "unknown_requires_review"
    REFUSED = "refused"


class DuplicateKind(str, Enum):
    """Which of the three duplicate checks produced a finding.

    They are separate values because they are separate checks over separate
    data (``PLAN.md`` Step 6): an exact duplicate is a content hash that has
    already been sent, a near duplicate is a similarity against recently
    published text, and overuse is a count of stored topic, project or
    evidence references. Collapsing them into one "similar" verdict would lose
    the only part a caller can act on — *what* was repeated.
    """

    EXACT = "exact"
    NEAR = "near"
    TOPIC_OVERUSE = "topic_overuse"
    PROJECT_OVERUSE = "project_overuse"
    EVIDENCE_OVERUSE = "evidence_overuse"


class InterruptionKind(str, Enum):
    """How a previous attempt was interrupted, from the durable record alone.

    The two are not variations of one case: they differ in whether a request
    could have reached LinkedIn, which is exactly the difference between
    "safe to attempt again" and "never retry" (``PLAN.md`` Step 6, recovery).
    """

    NEVER_ATTEMPTED = "never_attempted"
    """The intent was written but the attempt never started: no request left
    the machine, so no post can exist."""

    ATTEMPTED_UNKNOWN = "attempted_unknown"
    """The attempt started and no outcome was recorded: the request may have
    been received, so a post may exist and only a person can resolve it."""
