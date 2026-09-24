"""What changed in tracked work since the branding system last reviewed it (M2).

Two operations, kept separate on purpose:

* :func:`detect_changes` — did something change? Deterministic: git
  revisions, content digests, admitted paths. Same inputs, same logical
  result (see ``SourceChange.change_id``).
* classification — what kind of change? Deterministic rules over the
  detected facts. No LLM is consulted: nothing here may invent state, and
  "something changed but was classified minor" must stay auditable as
  distinct from "nothing changed".

What this layer never does:

* decide whether anything is worth posting (M3);
* advance the branding review cursor — detection only reads cursors.
  Advancing one means "reviewed", which only an explicit
  ``StateStore.set_review_cursor`` call by the reviewing layer (M3/the
  workflow) may assert. A detector that advanced cursors would mark work
  reviewed that nobody evaluated.
* merge the two timelines: sync checkpoints say "ingested", review cursors
  say "evaluated". A sync advancing never touches a cursor, here or
  anywhere else.

Size is never significance: every rule below reads change *kinds* (added,
modified, deleted, renamed, new directory, trivial edit), never counts of
chunks, lines (beyond the trivial-edit bound), or files. A one-file feature
and a thousand-file reformat are classified by what they are.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.state.models import utc_now_iso
from app.sync.enums import ChangeType

__all__ = [
    "TRIVIAL_EDIT_MAX_LINES",
    "ChangeClassification",
    "ChangeSet",
    "SourceChange",
    "detect_changes",
]


class ChangeClassification(str, Enum):
    """What kind of change the detected facts amount to.

    ``NO_CHANGE`` also covers "never reviewed" and "nothing admitted" —
    always with ``SourceChange.unreviewed`` / ``detail`` saying which, so
    an audit never confuses the three.
    """

    NO_CHANGE = "no_change"
    MINOR_CHANGE = "minor_change"
    MEANINGFUL_CHANGE = "meaningful_change"
    MILESTONE = "milestone"


#: A modification this small, alone, is a trivial edit (a typo, a wording
#: tweak) rather than a development. Applies only to exactly one modified
#: file with nothing else admitted in the range — any addition alongside it
#: is new content and escapes this rule.
TRIVIAL_EDIT_MAX_LINES = 10


@dataclass(frozen=True)
class SourceChange:
    """What changed in one source of one tracked work.

    ``paths`` holds admitted changed paths only (see
    :func:`app.sync.relevance.annotate`); excluded material never reaches a
    change record. For non-git sources per-path attribution is unavailable
    (a content digest has no paths in it), so ``paths`` is empty and
    ``detail`` says so — rather than fabricating per-file modifications.
    """

    work_id: str
    source_name: str
    before_revision: str | None
    after_revision: str
    paths: tuple = ()
    classification: ChangeClassification = ChangeClassification.NO_CHANGE
    unreviewed: bool = False
    detail: str = ""

    @property
    def change_id(self) -> str:
        """Stable identity of this logical change: no timestamps, no random
        ids. Detecting ``A → B`` twice yields the same id twice."""
        return (
            f"{self.work_id}:{self.source_name}:"
            f"{self.before_revision or '-'}:{self.after_revision}"
        )


@dataclass(frozen=True)
class ChangeSet:
    """One detection pass over one tracked work."""

    work_id: str
    detected_at: str
    changes: tuple[SourceChange, ...] = ()


def detect_changes(store: Any, work_id: str, *, registry: Any = None
                   ) -> ChangeSet:
    """Compare each source of ``work_id`` against its branding review cursor.

    Reads cursors, never writes them. Unknown tracked work raises; a named
    source missing from the registry raises rather than silently tracking
    nothing.
    """
    from app.sources.registry import load_registry
    from app.sync.revision import changed_paths, read_revision

    tracked = store.get_tracked_work(work_id)
    if tracked is None:
        raise ValueError(f"unknown tracked work {work_id!r}")
    active_registry = registry if registry is not None else load_registry()

    changes: list[SourceChange] = []
    for source_name in tracked.sources:
        source = active_registry.get(source_name)
        if source is None:
            raise ValueError(
                f"tracked work {work_id!r} names source {source_name!r}, "
                f"which is not in the registry"
            )
        cursor = store.get_review_cursor(work_id, source_name)
        previous = cursor.reviewed_revision if cursor is not None else None
        current = read_revision(source).revision
        if previous is None:
            changes.append(SourceChange(
                work_id=work_id, source_name=source_name,
                before_revision=None, after_revision=current,
                unreviewed=True, detail="never reviewed; nothing to compare",
            ))
        elif previous == current:
            changes.append(SourceChange(
                work_id=work_id, source_name=source_name,
                before_revision=previous, after_revision=current,
                detail="reviewed revision is current",
            ))
        elif source.is_git and not previous.startswith("content:"):
            changes.append(_detect_git(work_id, source, previous, current))
        else:
            changes.append(SourceChange(
                work_id=work_id, source_name=source_name,
                before_revision=previous, after_revision=current,
                classification=ChangeClassification.MEANINGFUL_CHANGE,
                detail=(
                    "admitted content differs from the reviewed state; "
                    "per-file attribution is unavailable for non-git "
                    "sources, so the content as a whole is reported"
                ),
            ))
    return ChangeSet(
        work_id=work_id, detected_at=utc_now_iso(), changes=tuple(changes))


def _detect_git(work_id: str, source: Any, previous: str,
                current: str) -> SourceChange:
    """Per-path git diff between the cursor and the current revision."""
    from app.sync.relevance import annotate
    from app.sync.revision import changed_paths

    raw = changed_paths(source, previous, current)
    if raw is None:
        return SourceChange(
            work_id=work_id, source_name=source.name,
            before_revision=previous, after_revision=current,
            classification=ChangeClassification.MEANINGFUL_CHANGE,
            detail=(
                "previous revision is unknown to the repository; the "
                "present content was never reviewed as a whole"
            ),
        )
    admitted = tuple(
        path for path in annotate(source, raw) if path.admitted
    )
    base = SourceChange(
        work_id=work_id, source_name=source.name,
        before_revision=previous, after_revision=current,
        paths=admitted,
    )
    if not admitted:
        return _replace(base, detail="no admitted changes in range")
    if all(path.change_type is ChangeType.DELETED for path in admitted):
        return _replace(
            base, ChangeClassification.MINOR_CHANGE,
            "removals only; nothing new to cite",
        )
    if all(path.is_exact_rename for path in admitted):
        return _replace(
            base, ChangeClassification.MINOR_CHANGE,
            "renamed without content change",
        )
    if _is_trivial_edit(source, admitted, previous, current):
        return _replace(
            base, ChangeClassification.MINOR_CHANGE, "trivial edit",
        )
    if _started_new_directory(source, admitted, previous):
        return _replace(
            base, ChangeClassification.MILESTONE, "new top-level directory",
        )
    return _replace(
        base, ChangeClassification.MEANINGFUL_CHANGE,
        "added or modified admitted content",
    )


def _replace(change: SourceChange,
             classification: ChangeClassification
             = ChangeClassification.NO_CHANGE,
             detail: str = "") -> SourceChange:
    """A copy with classification and detail set (frozen dataclass)."""
    return SourceChange(
        work_id=change.work_id, source_name=change.source_name,
        before_revision=change.before_revision,
        after_revision=change.after_revision, paths=change.paths,
        classification=classification, unreviewed=change.unreviewed,
        detail=detail,
    )


def _is_trivial_edit(source: Any, admitted: tuple,
                     previous: str, current: str) -> bool:
    """Exactly one modified file, ten or fewer changed lines total."""
    from app.sync.revision import diff_numstat

    if len(admitted) != 1:
        return False
    only = admitted[0]
    if only.change_type is not ChangeType.MODIFIED:
        return False
    counts = diff_numstat(source.local_path, previous, current).get(only.path)
    if counts is None:
        return False
    return sum(counts) <= TRIVIAL_EDIT_MAX_LINES


def _started_new_directory(source: Any, admitted: tuple,
                           previous: str) -> bool:
    """An added path under a top-level directory with no admitted history.

    A project started (or first admitted) reads exactly like this; an
    extension of an existing directory does not.
    """
    from app.sync.revision import list_tree

    added_tops = {
        path.path.split("/")[0] for path in admitted
        if path.change_type in (ChangeType.ADDED, ChangeType.RENAMED)
        and "/" in path.path
    }
    if not added_tops:
        return False
    before = {
        entry for entry in list_tree(source.local_path, previous)
        if source.admits(entry)
    }
    return any(
        not any(entry == top or entry.startswith(top + "/") for entry in before)
        for top in added_tops
    )
