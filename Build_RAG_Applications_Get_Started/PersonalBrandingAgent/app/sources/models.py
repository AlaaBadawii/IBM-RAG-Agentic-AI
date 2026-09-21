"""Typed registry models.

A source is a promise: *this exact directory, and these exact files inside it,
are evidence about the user.* Everything here exists to keep that promise
inspectable — the effective rule set can be printed and read, the reason for
every exclusion travels with the exclusion, and nothing about a source's
runtime behaviour is stored on the definition (``PLAN.md`` Step 2: definition
and state must not be conflated).
"""
from dataclasses import dataclass, field
from pathlib import Path

from app.sources.enums import SourceType
from app.sources.patterns import is_admitted
from app.state.enums import LifecycleState

__all__ = ["ExcludeRule", "NotRegisteredEntry", "Registry", "SourceDefinition"]


@dataclass(frozen=True)
class ExcludeRule:
    """A pattern that rejects, and why.

    The reason is required and non-empty at load time. An exclusion without a
    stated reason cannot be reviewed later: nobody can tell a deliberate
    "this is someone else's code" from a leftover from a debugging session,
    and the safe response to both becomes "leave it alone" — which is how a
    rule that should have been removed outlives its purpose.
    """

    pattern: str
    reason: str


@dataclass(frozen=True)
class SourceDefinition:
    """One exact source: where it is, what it admits, how it is governed."""

    name: str
    type: SourceType
    local_path: Path
    lifecycle: LifecycleState
    include: tuple[str, ...] = ()
    exclude: tuple[ExcludeRule, ...] = ()
    repo_identity: str | None = None
    ref: str | None = None
    description: str = ""

    @property
    def exclude_patterns(self) -> tuple[str, ...]:
        """Exclusion patterns only, for the matcher."""
        return tuple(rule.pattern for rule in self.exclude)

    @property
    def is_git(self) -> bool:
        return self.type is SourceType.GIT

    def reason_for(self, pattern: str) -> str | None:
        for rule in self.exclude:
            if rule.pattern == pattern:
                return rule.reason
        return None

    def admits(self, relative_path: str) -> bool:
        """Whether a source-relative path enters the knowledge base."""
        return is_admitted(relative_path, self.include, self.exclude_patterns)

    def describe(self) -> str:
        return f"{self.name} [{self.type.value}, {self.lifecycle.value}] {self.local_path}"


@dataclass(frozen=True)
class NotRegisteredEntry:
    """A directory inside a declared root that is deliberately not a source.

    The registry's exclusions say what a *source* must not contain. This says
    something different and equally necessary: which of the things found in
    the workspace were looked at, considered, and left out. Without it, the
    only record of that decision is a document nobody re-reads, and the next
    person to touch the registry cannot tell "we decided against this" from
    "we never noticed it".

    Each entry names a path and the evidence behind the decision, because
    these are the entries a reader is most likely to disagree with.
    """

    path: Path
    reason: str


@dataclass(frozen=True)
class Registry:
    """The validated set of sources, loaded from a committed file."""

    sources: tuple[SourceDefinition, ...]
    path: Path
    declared_roots: tuple[Path, ...] = field(default=())
    not_registered: tuple[NotRegisteredEntry, ...] = field(default=())

    def __iter__(self):
        return iter(self.sources)

    def __len__(self) -> int:
        return len(self.sources)

    def get(self, name: str) -> SourceDefinition | None:
        for source in self.sources:
            if source.name == name:
                return source
        return None

    def require(self, name: str) -> SourceDefinition:
        source = self.get(name)
        if source is None:
            known = ", ".join(sorted(s.name for s in self.sources))
            raise KeyError(f"unknown source {name!r}; registered: {known}")
        return source

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(source.name for source in self.sources)

    def containing(self, path: Path | str) -> SourceDefinition | None:
        """The source whose root contains ``path``, if any.

        Used by the guard on the candidate-file path, and deliberately
        returns the source rather than a boolean: a caller that has to refuse
        a file should be able to say *which source asked for it*.
        """
        target = Path(path).expanduser().resolve()
        for source in self.sources:
            if target == source.local_path or target.is_relative_to(source.local_path):
                return source
        return None
