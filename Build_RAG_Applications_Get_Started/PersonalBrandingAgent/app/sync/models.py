"""What a synchronization attempt reports.

Every field here exists because a caller has to make a decision with it. The
result is the only thing an unattended 24-hour run leaves behind besides the
state store, so "nothing changed", "this worked", "this failed", and "this
completed project moved" have to be *distinguishable values*, not inferences
from a log line or a non-zero exit code (``PLAN.md`` §2).

The result never guesses. A source with no diff to report reports no diff
(:attr:`SourceSyncResult.full_resync`); a source that was not attempted
reports ``NO_CHANGE``; a source that failed carries its category and message
and nothing else is implied about it.
"""
from dataclasses import dataclass, field

from app.sources.lifecycle import StatusReviewSignal, SyncPlan
from app.sources.models import SourceDefinition
from app.state.models import SyncCheckpoint

from app.sync.enums import ChangeType, RevisionKind, SyncErrorCategory, SyncStatus

__all__ = ["ChangedPath", "SourceSyncResult", "SyncRunResult"]


@dataclass(frozen=True)
class ChangedPath:
    """One path-level change between two revisions, and what was decided.

    ``admitted`` and ``reason`` are filled in by the relevance policy
    (:mod:`app.sync.relevance`), so a change that was looked at and rejected
    is still visible in the result — with the *reason* that rejected it.
    Discarding a changed path silently is how a knowledge base quietly stops
    covering part of someone's work (``PLAN.md`` Step 2).
    """

    path: str
    """Source-relative posix path, as of the current revision."""

    change_type: ChangeType
    previous_path: str | None = None
    """Set for a rename: where the file was before."""

    similarity: int | None = None
    """Git's rename similarity score, 0–100. ``100`` means the blob is
    byte-identical.

    Reported, never acted on. The rename policy purges the old path whichever
    score git reports (see :mod:`app.sync.relevance`), so this exists for the
    person reading the result: "renamed, 100" and "renamed, 62" are different
    kinds of change to review, even though the synchronization is the same.
    """

    admitted: bool = False
    reason: str | None = None
    """The rule that rejected the path, when it was rejected."""

    @property
    def is_exact_rename(self) -> bool:
        """A rename that changed no bytes. Informative, not decisive."""
        return self.change_type is ChangeType.RENAMED and self.similarity == 100


@dataclass(frozen=True)
class SourceSyncResult:
    """The outcome of synchronizing one registered source."""

    source: SourceDefinition
    status: SyncStatus
    plan: SyncPlan
    previous_revision: str | None = None
    current_revision: str | None = None
    revision_kind: RevisionKind | None = None
    full_resync: bool = False
    """True when the candidate set came from the source's whole admitted
    content rather than from a diff.

    Three cases produce it, and they are all "there is no history to compare
    against": a first synchronization, a source with no commits, and a
    previous revision the repository no longer knows (history rewritten). It
    is reported rather than hidden because the work it implies is proportional
    to the source, not to the change.
    """

    changed_paths: tuple[ChangedPath, ...] = ()
    candidates: tuple[str, ...] = ()
    """Source-relative paths handed to the ingestion pipeline."""

    purged: tuple[str, ...] = ()
    """Source-relative paths handed to the ingestion pipeline for removal."""

    review_signal: StatusReviewSignal | None = None
    ingestion: dict | None = None
    """The ingestion pipeline's own stats, or ``None`` when it was not called."""

    checkpoint: SyncCheckpoint | None = None
    error: str | None = None
    error_category: SyncErrorCategory | None = None

    @property
    def source_name(self) -> str:
        return self.source.name

    @property
    def failed(self) -> bool:
        return self.status is SyncStatus.FAILED

    @property
    def needs_review(self) -> bool:
        return self.review_signal is not None

    @property
    def relevant_paths(self) -> tuple[str, ...]:
        """Every path this attempt acted on, added and removed alike."""
        return self.candidates + self.purged

    @property
    def did_work(self) -> bool:
        """True when the ingestion pipeline was actually invoked."""
        return self.ingestion is not None

    @property
    def requires_human_intervention(self) -> bool:
        """The condition ``PLAN.md`` §2 escalates to the user."""
        return self.needs_review or self.error_category in (
            SyncErrorCategory.SOURCE_UNAVAILABLE,
            SyncErrorCategory.GUARD_REFUSED,
        )


@dataclass(frozen=True)
class SyncRunResult:
    """One synchronization pass over every registered source.

    Deliberately not a single success flag. ``PLAN.md`` Step 3 requires that
    one source's failure leaves the others alone, so the run's outcome is a
    *shape* — some succeeded, some did not, some had nothing to do — and every
    question asked of it is answered by filtering rather than by a boolean.
    """

    results: tuple[SourceSyncResult, ...] = field(default=())

    def __iter__(self):
        return iter(self.results)

    def __len__(self) -> int:
        return len(self.results)

    def _with_status(self, status: SyncStatus) -> tuple[SourceSyncResult, ...]:
        return tuple(r for r in self.results if r.status is status)

    @property
    def synced(self) -> tuple[SourceSyncResult, ...]:
        return self._with_status(SyncStatus.SYNCED)

    @property
    def unchanged(self) -> tuple[SourceSyncResult, ...]:
        return self._with_status(SyncStatus.NO_CHANGE)

    @property
    def failed(self) -> tuple[SourceSyncResult, ...]:
        return self._with_status(SyncStatus.FAILED)

    @property
    def review_signals(self) -> tuple[StatusReviewSignal, ...]:
        """Lifecycle declarations reality has moved past."""
        return tuple(r.review_signal for r in self.results if r.review_signal)

    @property
    def ok(self) -> bool:
        """True when no source failed. A no-change source is a success."""
        return not self.failed

    @property
    def requires_human_intervention(self) -> bool:
        return any(r.requires_human_intervention for r in self.results)

    def get(self, source_name: str) -> SourceSyncResult | None:
        for result in self.results:
            if result.source_name == source_name:
                return result
        return None
