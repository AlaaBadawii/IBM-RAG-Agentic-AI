"""Controlled vocabularies for operational state.

Operational state is only useful if it can be *queried*, and it can only be
queried if it is constrained. Every vocabulary below is mirrored by a CHECK
constraint in the schema (see ``schema.py``), so the database rejects a value
outside the vocabulary — not merely the Python API that normally writes it.

Sources in ``PLAN.md``:

    RunOutcome       §2          the three workflow outcomes
    PublishState     Step 1/6    the publish state machine
    LifecycleState   Step 2       project lifecycle (decision 5 in §12.1)
    SyncOutcome      Step 3       per-source checkpoint outcome
    DeliveryState    Step 7       notification delivery records

These are ``str`` enums so a member can be passed straight to sqlite3 and
compared against a stored string, while still being a typed value in code.
The store binds ``.value`` explicitly rather than relying on that.
"""
from enum import Enum


class RunOutcome(str, Enum):
    """How a workflow run terminated. Every run ends as exactly one of these.

    ``DO_NOT_PUBLISH`` is a **success**, not a failure: the system judged
    that publishing was not worthwhile, or found no opportunity at all
    (``PLAN.md`` §2).
    """

    DO_NOT_PUBLISH = "DO_NOT_PUBLISH"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"
    REQUIRES_HUMAN_INTERVENTION = "REQUIRES_HUMAN_INTERVENTION"


class PublishState(str, Enum):
    """The state machine of a publish intent.

    ``intent_created`` and ``attempt_started`` are the two states before a
    resolution; the other three are terminal. The distinction between
    ``failed`` and ``unknown_requires_review`` is the whole point: a
    definitive failure did not publish, an ambiguous one may have.
    """

    INTENT_CREATED = "intent_created"
    ATTEMPT_STARTED = "attempt_started"
    PUBLISHED = "published"
    FAILED = "failed"
    UNKNOWN_REQUIRES_REVIEW = "unknown_requires_review"


#: States a publish intent can be resolved to. ``record_publication`` accepts
#: only these.
TERMINAL_PUBLISH_STATES = (
    PublishState.PUBLISHED,
    PublishState.FAILED,
    PublishState.UNKNOWN_REQUIRES_REVIEW,
)


class LifecycleState(str, Enum):
    """Project lifecycle. Explicit and stored — never inferred.

    ``COMPLETED`` affects synchronization *depth and priority*, never
    visibility: a completed project still has its deletions and renames
    detected, and new activity raises a review signal rather than being
    ignored (``PLAN.md`` Step 2).
    """

    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    PLANNED = "PLANNED"


class SyncOutcome(str, Enum):
    """The result of the most recent synchronization attempt for a source."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class DeliveryState(str, Enum):
    """Delivery state of a notification.

    Deliberately a *separate* record from the failure it reports: a delivery
    failure must never erase or mask the original workflow failure
    (``PLAN.md`` Step 7).
    """

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class CredentialDerivation(str, Enum):
    """How a stored credential's expiry timestamp was obtained.

    Stored with the expiry, because the two derivations are not equally
    trustworthy and a later reviewer has to be able to tell them apart
    (``PLAN.md`` Step 5: "read expiry from the stored credential; never
    guess").

    ``ID_TOKEN_IAT`` is authoritative — the issuance claim LinkedIn signed
    inside the credential itself. ``FILE_MTIME`` is the fallback used when the
    credential carries no decodable ``id_token``: the moment the file was
    written is the best available evidence of when it was issued, and it is
    evidence rather than a guess only because the file is written by the
    exchange that issues the token.
    """

    ID_TOKEN_IAT = "id_token_iat"
    FILE_MTIME = "file_mtime"


class Workflow(str, Enum):
    """The two independent scheduled workflows (``PLAN.md`` Step 11).

    ``workflow_runs.workflow`` is intentionally *not* CHECK-constrained: the
    vocabulary is owned by the workflow layer (Step 11), and Step 13 keeps a
    manual LinkedIn path that may need a name of its own. This enum is here
    so callers do not have to spell the known values as loose strings.
    """

    SYNC = "sync"
    BRANDING = "branding"
