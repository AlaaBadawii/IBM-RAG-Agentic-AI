"""Which changed paths become ingestion work, and which are refused.

``PLAN.md`` Step 3 §4 in one sentence: **include is the floor, exclude is a
veto, and a veto cannot be outvoted.** The matching itself is
:mod:`app.sources.patterns`' job and is not reimplemented here — what this
module adds is the same decision *plus the reason it went that way*, because a
changed path that was looked at and rejected has to be visible in the
synchronization result. A path silently dropped is how a knowledge base stops
covering part of someone's work without anyone noticing.

Relevance is a filter, never a classifier
    There is no model here, no heuristic, and no scoring. ``EXCLUDE_READMES``
    is the precedent the roadmap names: a small, named, ordered, reversible
    rule set that a reader can predict. Everything below is those same rules
    applied to a changed path, which is why a commit touching only excluded
    files produces no ingestion work at all rather than "a little".

The rename policy
    A rename is the one change that can remove content and add it in the same
    breath, and the ids make it subtle. Chunk ids are content-addressed
    (``<sha256 of cleaned text>:<index>``), so a rename that changes no bytes
    produces **the same ids at the new path**. The policy below is therefore:

    * the new path is a candidate when the registry admits it;
    * the old path is purged when the registry admitted it — *including* an
      exact rename.

    Purging the old path on an exact rename looks redundant, and is not. The
    ingestion pipeline deletes a file's old chunks before writing its new ones
    (``pipeline._index_documents``); that ordering is what makes removing the
    old key safe even when the ids coincide, because the delete happens first
    and the add then claims the ids for the new key. Skipping the purge would
    instead leave the two rows to be overwritten in place, which is correct
    only because Chroma happens to accept an ``add`` on an existing id — an
    undocumented convenience, not a guarantee, and not something correctness
    should rest on. Purging is the version that keeps working if that changes.

    The similarity score is still read, and still reported
    (:attr:`~app.sync.models.ChangedPath.is_exact_rename`): it is the fact that
    tells a reader whether a rename moved bytes or merely moved a file, and it
    is what a test asserts on. It is deliberately not used to skip the purge.
"""
from dataclasses import dataclass, field

from app.sources.models import SourceDefinition
from app.sources.patterns import matches

from app.sync.enums import ChangeType
from app.sync.models import ChangedPath
from app.sync.revision import read_admitted_paths

__all__ = [
    "Admission",
    "ChangePlan",
    "annotate",
    "decide",
    "full_resync_plan",
    "plan_changes",
]


@dataclass(frozen=True)
class Admission:
    """The relevance decision for one path, and what decided it."""

    admitted: bool
    rule: str | None = None
    """The pattern that decided, when a rule did. ``None`` when the path simply
    matched no include pattern — which is a different fact from a veto."""

    reason: str | None = None
    """Human-readable, and the exclusion's own stated reason when a rule
    vetoed. Carried through to the result so a rejection is reviewable."""

    @property
    def vetoed(self) -> bool:
        """True when an exclusion rejected the path, rather than no include
        having admitted it. Only a veto is an *active* decision."""
        return not self.admitted and self.rule is not None


def decide(source: SourceDefinition, relative_path: str) -> Admission:
    """Whether one source-relative path enters the knowledge base, and why not.

    Deny wins, exactly as :func:`~app.sources.patterns.is_admitted` decides it —
    this function only recovers the *reason*, by naming the exclusion that
    matched. The exclusion is checked first for that reason, and the two
    functions are kept in agreement by a test that runs both over the same
    paths.
    """
    exclude = source.exclude_patterns
    for pattern in exclude:
        if matches(relative_path, pattern):
            return Admission(
                admitted=False,
                rule=pattern,
                reason=source.reason_for(pattern) or "excluded by the registry",
            )
    if not any(matches(relative_path, pattern) for pattern in source.include):
        return Admission(
            admitted=False,
            rule=None,
            reason="matches none of the source's include patterns",
        )
    return Admission(admitted=True)


def annotate(
    source: SourceDefinition, changes: tuple[ChangedPath, ...] | list[ChangedPath]
) -> tuple[ChangedPath, ...]:
    """Fill in the relevance decision on every changed path.

    Every path gets a verdict, including a rename's old path (which is judged
    on its own merits — it may have been admitted while its new location is
    not, or the reverse).
    """
    annotated: list[ChangedPath] = []
    for change in changes:
        admission = decide(source, change.path)
        annotated.append(
            ChangedPath(
                path=change.path,
                change_type=change.change_type,
                previous_path=change.previous_path,
                similarity=change.similarity,
                admitted=admission.admitted,
                reason=admission.reason,
            )
        )
    return tuple(annotated)


@dataclass(frozen=True)
class ChangePlan:
    """What a revision's changes amount to: files to index, keys to remove."""

    changes: tuple[ChangedPath, ...] = field(default=())
    """Every changed path, with its relevance decision. Reported in full, not
    only the admitted ones — this is what makes an irrelevant commit's effect
    (`candidates == ()`) explicable rather than mysterious."""

    candidates: tuple[str, ...] = field(default=())
    """Source-relative paths to index."""

    purges: tuple[str, ...] = field(default=())
    """Source-relative paths whose stored content must be removed."""

    @property
    def relevant_paths(self) -> tuple[str, ...]:
        """Paths the registry admitted, whether added or removed."""
        return tuple(c.path for c in self.changes if c.admitted)

    @property
    def is_empty(self) -> bool:
        """True when there is no ingestion work — an irrelevant-only commit."""
        return not self.candidates and not self.purges


def plan_changes(
    source: SourceDefinition, changes: tuple[ChangedPath, ...] | list[ChangedPath]
) -> ChangePlan:
    """Turn annotated changed paths into candidates and purges.

    ``changes`` is expected to carry its relevance decision already
    (:func:`annotate`); the rename policy below relies on it. An empty
    ``candidates`` from a non-empty change set is the intended outcome for a
    commit that touched only excluded files.
    """
    candidates: list[str] = []
    purges: list[str] = []

    for change in changes:
        if change.change_type is ChangeType.DELETED:
            if change.admitted:
                # The file was admitted and is gone: its content leaves with it
                # through the pipeline's own removal path, which is the only
                # deletion mechanism in the system.
                purges.append(change.path)
            continue

        if change.change_type is ChangeType.RENAMED:
            if change.admitted:
                candidates.append(change.path)
            if change.previous_path is not None:
                previous = decide(source, change.previous_path)
                if previous.admitted:
                    purges.append(change.previous_path)
            continue

        if change.admitted:
            candidates.append(change.path)

    return ChangePlan(
        changes=tuple(changes),
        candidates=tuple(_dedupe(candidates)),
        purges=tuple(_dedupe(purges)),
    )


def full_resync_plan(source: SourceDefinition) -> ChangePlan:
    """The plan when there is no baseline to diff against.

    Every admitted file is a candidate, and there is no purge list: with no
    per-path history, nothing can be named as removed. Stale keys are handled
    instead by the ingestion pipeline's scoped sweep, which the synchronizer
    enables **only** for a plan built here — a sweep's keep-set is the source's
    whole inventory, so enabling it for a diff would delete everything the
    revision did not touch.
    """
    return ChangePlan(
        changes=(),
        candidates=read_admitted_paths(source),
        purges=(),
    )


def _dedupe(paths: list[str]) -> list[str]:
    """Collapse repeats, preserving first-seen order.

    Git can report the same path twice in one diff — a rename whose old path is
    also re-added, for instance — and indexing or purging it twice would be
    wasted work at best.
    """
    seen: set[str] = set()
    unique: list[str] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique
