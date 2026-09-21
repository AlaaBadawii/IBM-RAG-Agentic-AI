"""How a file from a registered source is named once it is inside Chroma.

A registered source is a directory somewhere else on the machine, and its
files now live in the *same* Chroma collection as the hand-written ``data/``
corpus. Two things therefore have to be impossible:

The corpus must never be confused with a source
    ``data/evidence/backend/fastapi.md`` is one person's curated claim about
    their own work. ``~/LLMs/IBM/.../fastapi/some_route.py`` is raw authored
    code. Both are evidence, but they are not the same kind of thing, and a
    registry entry that happened to be named ``evidence`` would silently mix
    them. So every source-derived key carries an explicit namespace that no
    corpus path can produce.

Two sources must never be confused with each other
    Stale removal is expressed as a *scope* — "stored keys that belong to this
    source and are no longer candidates" — so a scope that matched a second
    source's keys would delete another source's content. The separator is what
    prevents it: ``@source/ai/`` cannot match ``@source/ai-agents/x.md``
    because the prefix ends at a ``/``, and a name containing ``/`` is refused
    outright (:func:`assert_namespace_safe`) rather than being allowed to
    create the ambiguity.

The namespace is therefore a correctness device, not a cosmetic one, and it is
the reason a source's files can share a collection with the corpus without
either being able to damage the other.
"""
from app.errors import SyncError

__all__ = [
    "NAMESPACE_PREFIX",
    "assert_namespace_safe",
    "is_source_key",
    "source_key",
    "source_namespace",
]

NAMESPACE_PREFIX = "@source/"
"""Marks a stored key as coming from a registered source.

``@`` cannot begin a ``data/`` corpus path in practice (every corpus file is a
Markdown document under one of ten known category directories), and the
prefix is checked rather than assumed: :func:`is_source_key` is what the
synchronizer uses to reason about which keys it owns.
"""


def assert_namespace_safe(source_name: str) -> str:
    """Refuse a source name that would make the namespace ambiguous.

    Raises:
        SyncError: the name is empty, contains ``/`` (which would let it
            swallow another source's keys), or contains the namespace marker.
    """
    if not isinstance(source_name, str) or not source_name.strip():
        raise SyncError("a source name must be a non-empty string")
    if "/" in source_name or "\\" in source_name:
        raise SyncError(
            f"source name {source_name!r} contains a path separator, which "
            "would make its synchronization namespace ambiguous with another "
            "source's. Rename the source in sources.yaml."
        )
    if source_name.startswith("@"):
        raise SyncError(
            f"source name {source_name!r} begins with '@', which is reserved "
            "for the source namespace."
        )
    return source_name


def source_namespace(source_name: str) -> str:
    """The key prefix owned by one source, terminated by a separator."""
    return f"{NAMESPACE_PREFIX}{assert_namespace_safe(source_name)}/"


def source_key(source_name: str, relative_path: str) -> str:
    """The stored key for one file of one registered source.

    Raises:
        SyncError: the relative path is absolute, escapes the source root, or
            is empty — a path that does not stay inside its source is not a
            candidate at all, whatever produced it.
    """
    namespace = source_namespace(source_name)
    relative = str(relative_path).strip()
    if not relative:
        raise SyncError(f"source {source_name!r}: an empty relative path is not a file")
    if relative.startswith("/") or "\\" in relative:
        raise SyncError(
            f"source {source_name!r}: {relative_path!r} is not a source-relative "
            "posix path"
        )
    if ".." in relative.split("/"):
        raise SyncError(
            f"source {source_name!r}: {relative_path!r} escapes the source root"
        )
    return f"{namespace}{relative}"


def is_source_key(key: str) -> bool:
    """True when a stored key came from a registered source."""
    return isinstance(key, str) and key.startswith(NAMESPACE_PREFIX)
