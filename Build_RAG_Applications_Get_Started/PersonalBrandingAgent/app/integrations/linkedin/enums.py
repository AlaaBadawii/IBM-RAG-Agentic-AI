"""Controlled vocabularies of the LinkedIn boundary.

Mirrors the layout of ``app/state/enums.py`` and for the same reason: a result
is only useful if it can be branched on, and it can only be branched on if its
values are a closed set.

Two of these are deliberately *not* the state store's vocabulary.
``PublicationOutcome`` is the integration's own view of one attempt, from which
the publish state machine (Step 6) derives ``PublishState``;
``LinkedInErrorCategory`` is left unconstrained in the schema on purpose, since
the layer that owns its values is this one.
"""
from enum import Enum


class LinkedInErrorCategory(str, Enum):
    """Why a LinkedIn call failed.

    The set is the table ``PLAN.md`` Step 5 names — authentication,
    permission, validation, rate limit, transport, unknown. It is a small set
    because its only job is to decide what the *system* does next, and the
    system has only a few distinct options: reauthorize by hand, stop,
    abandon the draft, back off, fail the run.

    A category is not a diagnosis. It is deliberately coarser than LinkedIn's
    own error codes, which are neither stable nor documented consistently
    enough to branch on.
    """

    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    VALIDATION = "validation"
    RATE_LIMIT = "rate_limit"
    TRANSPORT = "transport"
    UNKNOWN = "unknown"


class PublicationOutcome(str, Enum):
    """What is known about one publish attempt.

    ``FAILED`` and ``UNKNOWN`` are the distinction the whole design rests on
    (``PLAN.md`` §5.1, §11). LinkedIn cannot be read back, so a request that
    may have been received cannot be resolved by asking: either the API
    definitively rejected it (``FAILED`` — no post exists) or it is unresolved
    (``UNKNOWN`` — a post may exist, and a human has to look).

    ``UNKNOWN`` is never a synonym for "probably fine" or "probably not". It
    is a claim about what the system can prove, and the honest answer is
    nothing.
    """

    PUBLISHED = "published"
    FAILED = "failed"
    UNKNOWN = "unknown"


class CredentialStatus(str, Enum):
    """Whether the stored LinkedIn credential can be used right now.

    ``EXPIRING_SOON`` is usable: the point of the warning is to reach a human
    *before* the failure, not to stop working early. Its remedy is the same as
    ``EXPIRED``'s — re-authorize by hand — but it is not yet a failure, and
    treating it as one would take the system down days early for no reason.
    """

    MISSING = "missing"
    UNREADABLE = "unreadable"
    EXPIRED = "expired"
    EXPIRING_SOON = "expiring_soon"
    VALID = "valid"
