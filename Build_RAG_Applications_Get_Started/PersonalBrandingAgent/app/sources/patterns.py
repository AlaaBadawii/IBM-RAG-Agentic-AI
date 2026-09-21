"""Include/exclude pattern matching over a source's relative paths.

The grammar is deliberately small and gitignore-shaped, because the patterns
are authored by hand in ``sources.yaml`` and a rule nobody can predict is a
rule that silently admits the wrong file:

    *        any run of characters within one path segment
    ?        exactly one character within one path segment
    **       any number of path segments, including none
    dir/     a trailing slash means "this directory and everything under it"

A pattern containing no ``/`` matches at **any depth**, so ``__pycache__/``
means every ``__pycache__`` anywhere rather than only one at the root. This is
the behaviour a reader already expects from ``.gitignore``.

Matching is **deny-wins**: a path is admitted only if it matches at least one
include pattern *and* matches no exclude pattern. It is not "last rule wins",
because the two rules answer different questions — include says what this
source is for, exclude says what must never enter the knowledge base — and an
exclusion that a later include could override would make the credentials rule
depend on list order.

Character classes (``[abc]``), absolute patterns, and ``..`` segments are
rejected outright rather than approximated. Each has a plausible-looking
expansion that is subtly wrong, and a registry is the wrong place to be
clever: refusing to load is recoverable, admitting a credential file is not.
"""
import re

__all__ = [
    "PatternError",
    "compile_pattern",
    "is_admitted",
    "matches",
    "validate_pattern",
]


class PatternError(ValueError):
    """Raised when a pattern is malformed or uses unsupported syntax."""


_UNSUPPORTED = {
    "[": "character classes are not supported; list the paths explicitly",
    "]": "character classes are not supported; list the paths explicitly",
}


def _translate(body: str) -> str:
    """Convert the body of a pattern (no trailing slash) into a regex body."""
    out: list[str] = []
    i = 0
    length = len(body)
    while i < length:
        char = body[i]

        if char == "*":
            if body[i:i + 2] == "**":
                # "**/" consumes a whole segment, so it may also match nothing.
                # A bare "**" with no slash is just "anything".
                if body[i:i + 3] == "**/":
                    out.append("(?:.*/)?")
                    i += 3
                else:
                    out.append(".*")
                    i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif char == "?":
            out.append("[^/]")
            i += 1
        elif char == "/":
            out.append("/")
            i += 1
        else:
            out.append(re.escape(char))
            i += 1
    return "".join(out)


def compile_pattern(pattern: str) -> re.Pattern:
    """Compile a registry pattern into a regex over relative posix paths.

    Raises:
        PatternError: the pattern is empty, absolute, contains a ``..``
            segment, uses unsupported syntax, or is otherwise malformed.
    """
    validate_pattern(pattern)

    body = pattern.strip()
    directory = body.endswith("/")
    body = body.rstrip("/")

    # A pattern with no separator applies at any depth: "__pycache__/" should
    # not mean only the root-level __pycache__.
    if "/" not in body:
        body = "**/" + body

    regex = _translate(body)
    # A trailing slash names a directory, and a directory rule governs its
    # contents too — excluding "instance/" but admitting "instance/x.db" would
    # be a trap.
    suffix = "(?:/.*)?" if directory else ""
    return re.compile(f"^(?:{regex}){suffix}$")


def validate_pattern(pattern: str) -> None:
    """Reject a pattern that cannot be matched predictably.

    Called both by :func:`compile_pattern` and directly by registry loading,
    so a bad pattern is a *load* failure carrying the source name rather than
    a surprise during synchronization.
    """
    if not isinstance(pattern, str):
        raise PatternError(f"pattern must be a string, got {type(pattern).__name__}")

    body = pattern.strip()
    if not body:
        raise PatternError("pattern must not be empty")
    if body.startswith("/"):
        raise PatternError(
            f"pattern {pattern!r} is absolute; registry patterns are relative "
            "to the source root"
        )
    if body.startswith("~"):
        raise PatternError(
            f"pattern {pattern!r} looks like a home-relative path; registry "
            "patterns are relative to the source root"
        )
    if ".." in body.split("/"):
        raise PatternError(
            f"pattern {pattern!r} escapes the source root with '..'"
        )
    for char, reason in _UNSUPPORTED.items():
        if char in body:
            raise PatternError(f"pattern {pattern!r}: {reason}")
    if body.rstrip("/") == "":
        raise PatternError(f"pattern {pattern!r} names no file or directory")


def matches(relative_path: str, pattern: str) -> bool:
    """True when ``relative_path`` (posix, from the source root) matches."""
    normalized = relative_path.strip("/")
    if not normalized:
        return False
    return compile_pattern(pattern).match(normalized) is not None


def is_admitted(
    relative_path: str,
    include: tuple[str, ...] | list[str],
    exclude: tuple[str, ...] | list[str],
) -> bool:
    """Decide whether a path enters the knowledge base.

    Deny wins, and an empty include list admits **nothing** — a source that
    forgot to declare what it is for is a configuration error, and the safe
    reading of "no stated purpose" is silence rather than everything.
    """
    if not any(matches(relative_path, pattern) for pattern in include):
        return False
    return not any(matches(relative_path, pattern) for pattern in exclude)
