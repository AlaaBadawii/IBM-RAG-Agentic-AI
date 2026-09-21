"""Resolving a source's revision, and detecting what changed since the last one.

Two questions, kept apart on purpose (``PLAN.md`` Step 3):

    *What revision is this source at now?*  — answered here, from git or from
    the content itself.

    *What revision did the system successfully process?* — answered by the
    operational store, never here. This module has no idea what a checkpoint
    is, which is what stops the two from being conflated.

For a **git** source the answer is a commit id, and the difference between two
commit ids is a path-level diff that git computes. For a **filesystem** source
there is no history at all, so the answer is a digest of the source's admitted
content, and a changed digest re-submits the whole admitted set. That is not a
weaker design, it is the honest one: without a version control system there is
nothing to diff *against*, and inventing a second one here is exactly what the
step forbids. The narrowing then happens one layer down, where it already
happens — the ingestion pipeline's content hashes decide which files genuinely
changed (``PLAN.md`` Step 3 §6).

Everything a source contains is filtered through the registry's own patterns
before it is looked at, and every directory is passed through the
self-ingestion guard while walking. A file the registry did not admit is never
read, hashed, or counted — which is what makes hashing a whole filesystem
source affordable in the first place: the virtualenv an exclusion names is
never descended into, so it costs nothing to skip.
"""
import os
import subprocess
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Sequence

from app.errors import GitError, SourceUnavailableError, SyncError
from app.logging_config import get_logger
from app.sources.guard import is_protected
from app.sources.models import SourceDefinition
from app.sources.patterns import is_admitted, matches

from app.sync.enums import ChangeType, RevisionKind
from app.sync.models import ChangedPath

__all__ = [
    "CONTENT_REVISION_PREFIX",
    "GIT_TIMEOUT_SECONDS",
    "SourceRevision",
    "changed_paths",
    "content_revision",
    "is_known_commit",
    "iter_admitted_files",
    "read_admitted_paths",
    "read_revision",
    "resolve_git_revision",
]

logger = get_logger(__name__)

GIT_TIMEOUT_SECONDS = 120.0
"""A git command that hangs is a hung unattended run. Bounded on purpose."""

CONTENT_REVISION_PREFIX = "content:"
"""Marks a revision that is a digest of content rather than a commit id.

Both kinds are stored in the same ``sync_checkpoints.last_revision`` column, so
this prefix is what keeps one from being mistaken for the other — and what lets
the synchronizer refuse to ask git to diff a digest.
"""

_CHANGE_TYPES: dict[str, ChangeType] = {
    "A": ChangeType.ADDED,
    "M": ChangeType.MODIFIED,
    "D": ChangeType.DELETED,
    "R": ChangeType.RENAMED,
    "T": ChangeType.MODIFIED,  # typechange: still a change to the path
    "U": ChangeType.MODIFIED,  # unmerged: a change, never a removal
}
"""Git's status letters, mapped. ``C`` (copy) is handled separately: a copy
adds a path and removes nothing, so it is an addition however git spells it."""


@dataclass(frozen=True)
class SourceRevision:
    """What a source is at, right now."""

    kind: RevisionKind
    revision: str
    detail: str = ""

    @property
    def is_git(self) -> bool:
        return self.kind is RevisionKind.GIT


# --- git ---------------------------------------------------------------------

def _run_git(repo: Path, args: Sequence[str],
             timeout: float = GIT_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    """Run one git command in ``repo``, for callers that need the exit code.

    ``core.quotepath=false`` is set globally here, and callers that parse paths
    pass ``-z``: a path that has to be un-escaped before it can be looked up is
    a path that will eventually be looked up wrongly.
    """
    command = ["git", "-c", "core.quotepath=false", *args]
    try:
        return subprocess.run(
            command,
            cwd=str(repo),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise GitError(
            "git is not installed, so git-backed sources cannot be synchronized"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError(
            f"git {' '.join(args)} did not finish within {timeout:.0f}s in {repo}"
        ) from exc
    except OSError as exc:
        raise GitError(f"git {' '.join(args)} could not be run in {repo}: {exc}") from exc


def _git(repo: Path, args: Sequence[str]) -> str:
    """Run one git command that must succeed, and return its stdout."""
    completed = _run_git(repo, args)
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip().splitlines()
        raise GitError(
            f"git {' '.join(args)} failed in {repo} "
            f"(exit {completed.returncode}): {detail[-1] if detail else 'no output'}"
        )
    return completed.stdout


def resolve_git_revision(repo: Path, ref: str | None) -> str | None:
    """The commit ``ref`` currently points at, or ``None`` if there are none.

    The two failure modes are separated, because they mean different things:

    * the repository has **no commits** → ``None``. A registered repository
      with an unborn ``HEAD`` is a legitimate source (``exit-project-studyflow``
      is registered that way), and it is synchronized by content instead.
    * the repository has commits but the declared ``ref`` does not resolve →
      :class:`GitError`. The registry and the repository now disagree, and
      picking another ref on the user's behalf would be inventing a
      synchronization target they did not declare.
    """
    head = _run_git(repo, ["rev-parse", "--verify", "--quiet", "HEAD^{commit}"])
    if not head.stdout.strip():
        return None
    if not ref:
        return head.stdout.strip()
    resolved = _run_git(repo, ["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
    if not resolved.stdout.strip():
        raise GitError(
            f"{repo}: the declared ref {ref!r} does not resolve. Synchronization "
            "tracks the revision the registry names, so either restore that ref "
            "or correct 'ref' in sources.yaml."
        )
    return resolved.stdout.strip()


def is_known_commit(repo: Path, revision: str) -> bool:
    """True when ``revision`` is a commit this repository still knows.

    A checkpoint can outlive the commit it names — a rebase, a garbage
    collection, a force-push — and then there is no valid diff to compute.
    Detecting that is what lets the synchronizer fall back to a full
    re-synchronization instead of producing a diff against nothing.
    """
    if not revision or revision.startswith(CONTENT_REVISION_PREFIX):
        return False
    completed = _run_git(repo, ["cat-file", "-e", f"{revision}^{{commit}}"])
    return completed.returncode == 0


def changed_paths(
    source: SourceDefinition, previous: str, current: str
) -> tuple[ChangedPath, ...] | None:
    """Every path that differs between two revisions, classified by git.

    Returns ``None`` — not an empty tuple — when no diff can be computed,
    because "nothing changed" and "we cannot tell what changed" are different
    answers and only one of them is safe to act on as a no-op.
    """
    repo = source.local_path
    if not is_known_commit(repo, previous):
        logger.info(
            "Source %s: previous revision %s is unknown to this repository; "
            "re-synchronizing its whole admitted content",
            source.name, previous,
        )
        return None
    if not is_known_commit(repo, current):
        raise GitError(
            f"source {source.name!r}: revision {current} is not a commit in {repo}"
        )
    output = _git(repo, ["diff", "--name-status", "-M", "-z", previous, current, "--"])
    return _parse_name_status(output, where=f"{source.name} ({previous}..{current})")


def _parse_name_status(output: str, *, where: str) -> tuple[ChangedPath, ...]:
    """Parse ``git diff --name-status -M -z``.

    The ``-z`` form is a NUL-separated token stream: ``<status>\\0<path>\\0``,
    and for a rename ``R<score>\\0<old>\\0<new>\\0`` — old first. It is used
    rather than the newline form because it is unambiguous for every filename a
    filesystem will accept, and because the similarity score decides the rename
    policy.
    """
    tokens = output.split("\0")
    if tokens and tokens[-1] == "":
        tokens.pop()

    changes: list[ChangedPath] = []
    index = 0
    while index < len(tokens):
        status = tokens[index]
        index += 1
        code = status[:1]

        if code in ("R", "C"):
            if index + 1 >= len(tokens):
                raise GitError(
                    f"git reported a truncated rename/copy while diffing {where}: "
                    "refusing to report a partial change set"
                )
            previous_path, path = tokens[index], tokens[index + 1]
            index += 2
            if code == "R":
                changes.append(
                    ChangedPath(
                        path=path,
                        change_type=ChangeType.RENAMED,
                        previous_path=previous_path,
                        similarity=int(status[1:] or 0),
                    )
                )
            else:
                # A copy adds a path and removes nothing, so it is an addition
                # however git spells it.
                changes.append(ChangedPath(path=path, change_type=ChangeType.ADDED))
            continue

        if index >= len(tokens):
            raise GitError(
                f"git reported a truncated status {status!r} while diffing {where}"
            )
        path = tokens[index]
        index += 1
        change_type = _CHANGE_TYPES.get(code)
        if change_type is None:
            # An unrecognised status is re-read rather than dropped: the cost of
            # re-submitting an unchanged file is zero (its content hash decides),
            # and the cost of dropping a changed one is a knowledge base that
            # quietly goes stale.
            logger.warning(
                "git reported status %r for %s while diffing %s; treating it as a "
                "modification", status, path, where,
            )
            change_type = ChangeType.MODIFIED
        changes.append(ChangedPath(path=path, change_type=change_type))
    return tuple(changes)


# --- content -----------------------------------------------------------------

def iter_admitted_files(source: SourceDefinition) -> list[tuple[str, Path]]:
    """Every file of a source that the registry admits, sorted by path.

    The registry's rules are applied *during* the walk, not after it: a
    directory an exclusion names is never descended into. So the 617 MB
    virtualenv an exclusion was written for costs nothing to skip, and 36,082
    ``.py`` files become the 93 the registry actually admits (``PLAN.md``
    Step 2).

    Sorted rather than filesystem-ordered, so two walks of one unchanged tree
    produce one digest — which is what makes "no change" detectable at all.

    Raises:
        SyncError: a directory could not be read. A revision computed from a
            partial read would be a claim about the source that is not true,
            and every later synchronization would inherit it.
    """
    root = source.local_path
    include, exclude = source.include, source.exclude_patterns
    found: list[tuple[str, Path]] = []
    frontier: list[Path] = [root]

    while frontier:
        current = frontier.pop()
        try:
            with os.scandir(current) as scan:
                entries = sorted(scan, key=lambda entry: entry.name)
        except OSError as exc:
            raise SyncError(f"cannot read directory {current}: {exc}") from exc

        for entry in entries:
            if entry.is_symlink():
                # A link is not authored content, and following one can leave
                # the source entirely, or loop.
                continue
            child = Path(entry.path)
            if entry.is_dir(follow_symlinks=False):
                if entry.name == ".git":
                    continue
                relative = child.relative_to(root).as_posix()
                if any(matches(relative, pattern) for pattern in exclude):
                    continue
                if is_protected(child):
                    # The self-ingestion guard, applied while walking rather
                    # than only when a file is finally chosen.
                    continue
                frontier.append(child)
                continue
            if not entry.is_file(follow_symlinks=False):
                continue
            relative = child.relative_to(root).as_posix()
            if is_admitted(relative, include, exclude):
                found.append((relative, child))

    found.sort(key=lambda item: item[0])
    return found


def content_revision(source: SourceDefinition) -> str:
    """A digest of a source's admitted content, used when there is no history.

    Paths are part of the digest as well as contents, so a rename that leaves
    every byte alone is still a change: the stored key moved, and the ingestion
    layer has to retract the old one.
    """
    digest = sha256()
    for relative, path in iter_admitted_files(source):
        try:
            file_digest = sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise SyncError(
                f"source {source.name!r}: {relative} is admitted by the registry "
                f"but cannot be read ({exc}); no honest revision can be computed"
            ) from exc
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\0")
    return f"{CONTENT_REVISION_PREFIX}{digest.hexdigest()}"


def read_admitted_paths(source: SourceDefinition) -> tuple[str, ...]:
    """The source-relative paths of everything the registry admits, sorted."""
    return tuple(relative for relative, _ in iter_admitted_files(source))


def read_revision(source: SourceDefinition) -> SourceRevision:
    """Where a source is now.

    Raises:
        SourceUnavailableError: the registered path is missing, is not a
            directory, or is declared ``git`` and is no longer a repository.
        GitError: a git command failed, or the declared ref does not resolve.
        SyncError: a directory or admitted file could not be read.
    """
    root = source.local_path
    if not root.exists():
        raise SourceUnavailableError(
            f"source {source.name!r} is registered at {root}, which does not "
            "exist. Fix the registry, or restore the source."
        )
    if not root.is_dir():
        raise SourceUnavailableError(
            f"source {source.name!r} is registered at {root}, which is not a directory."
        )
    if not source.is_git:
        return SourceRevision(
            kind=RevisionKind.CONTENT, revision=content_revision(source)
        )
    if not (root / ".git").exists():
        raise SourceUnavailableError(
            f"source {source.name!r} is declared 'git' but {root} is no longer a "
            "repository. The registry and the filesystem disagree."
        )

    commit = resolve_git_revision(root, source.ref)
    if commit is None:
        return SourceRevision(
            kind=RevisionKind.CONTENT,
            revision=content_revision(source),
            detail="the repository has no commits, so it is synchronized by content",
        )
    return SourceRevision(kind=RevisionKind.GIT, revision=commit)
