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
