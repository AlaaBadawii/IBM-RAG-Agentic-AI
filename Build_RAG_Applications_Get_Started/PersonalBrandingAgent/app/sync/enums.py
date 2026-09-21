"""Controlled vocabularies for the synchronization layer.

The synchronization layer answers two questions that must never be confused
(``PLAN.md`` Step 3):

    Git                what changed since the last processed revision?
    Application state  what revision did the system successfully process?

Everything here is deliberately small and closed. A synchronization result is
read by an unattended workflow, so "how did this source go?" has to be a value
that can be compared, counted, and tested — never a sentence to be parsed.
"""
from enum import Enum

__all__ = ["ChangeType", "RevisionKind", "SyncErrorCategory", "SyncStatus"]


class ChangeType(str, Enum):
    """How one path changed between two revisions.

    Taken from git's own classification (``--name-status``) rather than
    inferred from filenames: a rename is a *fact about history* that only the
    version control system knows, and guessing it from a deleted path plus an
    added one with a similar name is exactly the kind of invention this
    roadmap avoids.
    """

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"

    @property
    def removes_content(self) -> bool:
        """True when the change can leave indexed content behind."""
        return self in (ChangeType.DELETED, ChangeType.RENAMED)


class RevisionKind(str, Enum):
    """What a source's revision string actually is.

    Both kinds are first-class, because both kinds of source are. A git source
    in a repository with **no commits** (``exit-project-studyflow`` is one) has
    no history to name, so it is synchronized by content exactly like a
    filesystem source — rather than being forced into a revision it does not
    have (``PLAN.md`` Step 2 registered it deliberately).
    """

    GIT = "git"
    """A commit id. Git can diff two of these, so changes are detected per path."""

    CONTENT = "content"
    """A digest of the source's admitted content. There is no history to diff,
    so a changed digest re-submits the source's admitted files and the
    ingestion layer's content hashes decide what genuinely changed."""


class SyncStatus(str, Enum):
    """How one source's synchronization attempt ended.

    ``NO_CHANGE`` is a success, not an absence: the source is already at the
    revision the system successfully processed, so nothing was attempted. It
    is a distinct member because the difference between "we did nothing
    because there was nothing to do" and "we did nothing because we failed"
    is exactly what an unattended run has to be able to report.
    """

    NO_CHANGE = "NO_CHANGE"
    SYNCED = "SYNCED"
    FAILED = "FAILED"

    @property
    def succeeded(self) -> bool:
        return self in (SyncStatus.NO_CHANGE, SyncStatus.SYNCED)


class SyncErrorCategory(str, Enum):
    """Why a source's synchronization failed, as a value rather than a message.

    The category is what a later notification or an operator filter can act
    on; the message is what a human reads. Recording both is what keeps
    ``operational_failures`` queryable instead of a wall of text
    (``PLAN.md`` Step 3, Failure/recovery).
    """

    SOURCE_UNAVAILABLE = "source_unavailable"
    """The registered path is gone, is not a directory, or is no longer a
    repository — ``REQUIRES_HUMAN_INTERVENTION``."""

    GUARD_REFUSED = "guard_refused"
    """The self-ingestion guard refused a candidate path. Fatal for the source
    and for the run's trustworthiness: a source that can reach the
    application's own files is a registry defect, not a transient error."""

    GIT_FAILURE = "git_failure"
    """A git command failed, or the declared ref does not resolve."""

    CONTENT_UNREADABLE = "content_unreadable"
    """An admitted file could not be read, so no honest revision exists."""

    INGESTION_FAILURE = "ingestion_failure"
    """The existing ingestion pipeline failed for the candidates."""

    STATE_FAILURE = "state_failure"
    """The operational store could not be read or written."""

    UNEXPECTED = "unexpected"
    """Anything else. Recorded as a value so it is never silently swallowed."""
