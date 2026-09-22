"""Exception hierarchy for the application.

Keeping errors typed lets CLIs and tests distinguish "configuration problem"
from "ingestion problem" from "retrieval problem" without string matching.
"""


class AppError(Exception):
    """Base class for all application errors."""


class ConfigError(AppError):
    """Raised when required configuration (e.g. an API key) is missing."""


class IngestionError(AppError):
    """Raised when the data/ -> Chroma pipeline fails."""


class RetrievalError(AppError):
    """Raised when a retrieval strategy fails (missing index, bad filter...)."""


class RegistryError(AppError):
    """Raised when the source registry cannot be trusted.

    Always fatal to synchronization, never a warning. A registry that loads
    with an entry silently dropped is worse than one that refuses to load at
    all: the missing source produces no error, no signal, and a knowledge base
    that quietly stops covering part of the user's work. So a path that does
    not exist, a declared type that does not match reality, a malformed
    pattern, or an exclusion that would admit the application's own internals
    all stop the load (``PLAN.md`` Step 2, Failure/recovery).
    """


class SyncError(AppError):
    """Raised when a registered source cannot be synchronized.

    Always scoped to **one source**. The synchronizer records the failure,
    leaves that source's checkpoint where it was, and continues with the
    others — a source that cannot be read must not stop the knowledge base
    from catching up on the twenty-eight that can (``PLAN.md`` Step 3,
    Failure/recovery).
    """


class SourceUnavailableError(SyncError):
    """Raised when a registered source is no longer there as registered.

    Its path is gone, it is no longer a directory, or it is declared ``git``
    and no longer has a repository. ``PLAN.md`` §2 names this case explicitly
    as ``REQUIRES_HUMAN_INTERVENTION``: nothing the synchronizer can do will
    fix it, and the registry — which is the user's statement about their own
    workspace — has to be corrected.
    """


class GitError(SyncError):
    """Raised when a git command fails or a declared ref does not resolve.

    Distinct from :class:`SourceUnavailableError` because it is usually
    transient and needs no decision from the user.
    """


class StateStoreError(AppError):
    """Raised when the operational state store is unusable.

    The store is the system's durable memory. Callers must treat this as a
    hard stop, never as a warning: for anything with an external side effect
    (publishing), a store failure means the operation must not proceed.
    """


class StateConstraintError(StateStoreError):
    """Raised when the store refuses a write that would break an invariant.

    A subclass rather than a sibling, because a refused write is still a store
    failure. The distinction exists so callers and tests can tell "the store
    rejected this" — a duplicate publish attempt, a value outside an allowed
    vocabulary, a state transition the store owns — from "the store could not
    be reached at all".

    Either way the caller's obligation is the same: do not proceed.
    """


class NotificationError(AppError):
    """Raised when the notification path cannot do its job at all.

    A *delivery* failure — the mail server refused, the password is wrong, the
    connection timed out — is **not** one of these: it is a recorded outcome
    with a category of its own, because the workflow failure it was reporting
    must survive it (``PLAN.md`` Step 7). What remains here is the case where
    the notifier cannot even attempt a delivery, which is a configuration
    defect the caller has to fix.
    """
