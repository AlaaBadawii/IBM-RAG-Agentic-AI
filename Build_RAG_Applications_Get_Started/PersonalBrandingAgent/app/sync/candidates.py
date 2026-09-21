"""Turning admitted, changed paths into the files the pipeline will index.

Two jobs, both about honesty:

**Naming.** A source's files go into the same Chroma collection as the
hand-written ``data/`` corpus, so each one is stored under a namespaced key
(:mod:`app.sync.namespace`). That key is the ``source`` metadata field, which
is what the pipeline's idempotency check and stale removal both key on — so
naming a candidate is not bookkeeping, it is the thing that makes the second
run of an unchanged source touch nothing.

**Refusing.** Every candidate is put through the self-ingestion guard at the
moment it becomes a candidate, not when the file is finally read. The registry
was already checked against protected paths at load time; this is the second
layer, and it is the one that holds when a path is not the path the registry
was validated against — a symlink, a mount, a parent directory that moved.
"""
from dataclasses import dataclass

from app.errors import SyncError
from app.ingestion.loader import SourceFile
from app.sources.guard import assert_path_admissible
from app.sources.models import SourceDefinition

from app.sync.namespace import source_key

__all__ = ["SourceCandidate", "candidate_files", "purge_keys"]


@dataclass
class SourceCandidate(SourceFile):
    """One admitted file of a registered source, named for the shared collection.

    ``SourceFile`` derives ``category`` and ``domain`` from the path because a
    corpus file's path *is* its classification: ``evidence/backend/x.md`` is
    evidence, about backend. A source file's path carries no such statement,
    and its classification already exists — the registry. So the source name
    becomes the category, and ``domain`` stays unset rather than being filled
    with a path segment that means something else in the corpus.
    """

    source_name: str = ""
    """The registered source this file came from."""

    source_relative_path: str = ""
    """The path as the source itself writes it, without the namespace."""

    @property
    def category(self) -> str:
        return self.source_name

    @property
    def domain(self) -> str | None:
        return None

    @property
    def key(self) -> str:
        """The stored key, which is also ``relative_path``."""
        return self.relative_path


def candidate_files(
    source: SourceDefinition, relative_paths: tuple[str, ...] | list[str]
) -> tuple[SourceCandidate, ...]:
    """Build the candidates for one source, refusing anything inadmissible.

    Raises:
        SyncError: a path is not source-relative, or is not a regular readable
            file. A candidate set is a claim about what changed, and indexing
            part of one would let the source's checkpoint advance past a file
            that never reached the index.
        RegistryError: the path resolves inside the application's own
            directory. Deliberately not caught here — a source that can reach
            the application's files is a registry defect, and the caller must
            record it as one rather than filtering it away.
    """
    root = source.local_path
    candidates: list[SourceCandidate] = []
    for relative in relative_paths:
        key = source_key(source.name, relative)  # validates the path shape
        path = root / relative
        assert_path_admissible(source.name, path)
        if not path.is_file():
            raise SyncError(
                f"source {source.name!r}: {relative} is in the revision but is not "
                "a readable file; the source and the revision disagree"
            )
        candidates.append(
            SourceCandidate(
                path=path,
                relative_path=key,
                source_name=source.name,
                source_relative_path=relative,
            )
        )
    return tuple(candidates)


def purge_keys(
    source: SourceDefinition, relative_paths: tuple[str, ...] | list[str]
) -> tuple[str, ...]:
    """Name the paths to remove the way they are *stored*, not the way they read.

    The pipeline removes a key by looking it up in what is in the collection,
    and what is in the collection is namespaced. Handing it a source-relative
    path would match nothing and remove nothing — silently, because deleting a
    key that is not there is not an error. This is the one place that
    translation happens.
    """
    return tuple(source_key(source.name, path) for path in relative_paths)
