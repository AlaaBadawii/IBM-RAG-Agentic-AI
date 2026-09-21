"""Controlled vocabularies for the source registry.

The lifecycle vocabulary is **not** redefined here. ``LifecycleState`` already
lives in ``app.state.enums`` because lifecycle *transitions* are a runtime
observation recorded in the operational store, while the lifecycle
*declaration* is committed configuration in the registry. One vocabulary, two
places it is used — otherwise the two would drift apart, which is the failure
mode ``PLAN.md`` §5.5 records (a corpus where 42 files mention ``## Status``
and only 32 resolve against the vocabulary).
"""
from enum import Enum


class SourceType(str, Enum):
    """How a source's content is versioned.

    Both are first-class. Several workspace roots are plain directories whose
    content is in no repository at all, and ``~/FastAPI/ExitProject`` is a
    repository with zero commits — treating "git" as the only real kind would
    force those to be either faked or dropped.
    """

    GIT = "git"
    FILESYSTEM = "filesystem"


class SyncDisposition(str, Enum):
    """What synchronization should do with a source's changed files.

    There is deliberately **no "skip" member**. Lifecycle affects depth and
    priority, never visibility (``PLAN.md`` Step 2): a ``COMPLETED`` project
    must still have its deletions, renames, and new activity detected. Every
    disposition ingests; the members differ only in whether the change also
    raises a signal for a human.

    Expressing "ignore forever" as an option here is exactly the mistake the
    roadmap forbids, so the type makes it unrepresentable rather than
    discouraged.
    """

    NORMAL = "NORMAL"
    """Ingest. The change is what an active project is expected to produce."""

    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    """Ingest, and raise a status-review signal.

    Surfaces as ``REQUIRES_HUMAN_INTERVENTION`` (§2), so the change is
    recorded *and* visible. The alternative — discarding activity in a project
    the user has declared finished — would make the declaration a silent
    one-way door.
    """


class SyncPriority(str, Enum):
    """How much attention a source deserves relative to the others.

    ``PLAN.md`` Step 2 gives lifecycle exactly two levers: "synchronization
    depth and priority, never visibility". This is the priority lever — a
    stable, finished project does not need to be re-read as eagerly as one
    under active development — and it is the *only* thing besides the review
    signal that lifecycle is allowed to change.
    """

    HIGH = "HIGH"
    """Actively developed. New content here is the freshest evidence there is."""

    LOW = "LOW"
    """Settled: completed, paused, or not yet started. Still synchronized —
    see :class:`SyncDisposition`, which has no way to express skipping."""

