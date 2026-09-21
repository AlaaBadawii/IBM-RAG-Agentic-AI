"""The self-ingestion guard: this application must never ingest itself.

``~/LLMs/IBM`` is a monorepo that **contains this application**, so registering
it as a source is unavoidable and also the single most dangerous entry in the
registry. Without a guard, its include patterns would sweep up ``PLAN.md``,
``app/``, ``chroma_db/``, ``logs/``, ``state_db/``, and the token file, and the
knowledge base would start treating the system's own source and runtime
artifacts as professional evidence about its user (``PLAN.md`` §5.3, hazard 1).

Two layers, because either alone leaves a hole:

``PROJECT_ROOT`` is *protected*
    :func:`is_protected` answers the question for a single path, whatever
    produced it, and does not consult the registry at all. This is the layer
    that keeps the invariant true by construction rather than by pattern.

The registry is *validated against protected paths at load time*
    :func:`protected_probes` gives the concrete paths that must not be
    admitted, and loading refuses a registry in which any source would admit
    one. This is the layer that turns a misconfiguration into a startup
    failure instead of a silent leak (``PLAN.md`` Step 2: "rejected at load
    time, not at ingestion time").
"""
from pathlib import Path

from app.errors import RegistryError
from app.paths import PROJECT_ROOT
from app.sources.patterns import is_admitted

__all__ = [
    "PROTECTED_ROOT",
    "assert_path_admissible",
    "is_protected",
    "probes_admitted_by",
    "protected_probes",
]

PROTECTED_ROOT = PROJECT_ROOT.resolve()
"""The application's own directory is never admissible as evidence."""

_PROTECTED_PROBES: tuple[str, ...] = (
    # The application's own source and its packaging.
    "app/__init__.py",
    "app/config.py",
    "app/errors.py",
    "app/paths.py",
    "app/ingestion/pipeline.py",
    "app/retrieval/engine.py",
    "app/state/store.py",
    "app/sources/registry.py",
    "config.py",
    "requirements.txt",
    "tests/conftest.py",
    # Planning documents: they *describe* the work, they are not the work.
    "PLAN.md",
    "README.md",
    "docs/implementation-status.md",
    "docs/architecture/system-overview.md",
    # The source registry itself — the map is not the territory.
    "sources.yaml",
    # Runtime state and derived artifacts, none of which is rebuildable
    # evidence and one of which (state_db/) is authoritative in the other
    # direction.
    "chroma_db/chroma.sqlite3",
    "logs/app.log",
    "state_db/operational_state.db",
    ".venv/lib/python3.10/site-packages/somepkg/__init__.py",
    "app/__pycache__/store.cpython-310.pyc",
    # Credentials.
    ".env",
    "Auth_handling/linkedin_tokens.json",
    "Auth_handling/test_post.py",
    # The knowledge base itself. data/ is a *digest* of the sources; feeding
    # it back in as a source would make the corpus its own evidence, which is
    # the loop §6.1 exists to prevent.
    "data/completed_projects/quizey.md",
    "data/evidence/backend/fastapi.md",
)
"""Paths under :data:`PROTECTED_ROOT` that no source may ever admit.

Concrete paths rather than directory names on purpose: a probe is checked by
running it through the same :func:`~app.sources.patterns.is_admitted` the
synchronizer will use, so a registry that would leak ``.env`` fails the load
with the offending pattern named — not with a directory-level approximation
that may or may not correspond to what matching actually does.
"""


def protected_probes() -> tuple[str, ...]:
    """The protected paths, relative to :data:`PROTECTED_ROOT` (posix)."""
    return _PROTECTED_PROBES


def is_protected(path: Path | str) -> bool:
    """True when ``path`` is inside the application's own directory.

    Symlinks are resolved first, so a source cannot reach the application
    through a link that only *looks* like it points elsewhere.

    The path need not exist: patterns are evaluated against paths that have
    not been read yet, and the guard must be able to refuse one before it is
    ever touched.
    """
    try:
        resolved = Path(path).expanduser().resolve()
    except (OSError, RuntimeError):  # pragma: no cover - defensive
        return True  # unresolvable is treated as protected: fail closed
    return resolved == PROTECTED_ROOT or resolved.is_relative_to(PROTECTED_ROOT)


def assert_path_admissible(source_name: str, path: Path | str) -> None:
    """Raise :class:`RegistryError` if ``path`` is inside the application.

    Called for the source root at load time, and available to the
    synchronizer for every candidate file — the second layer of the guard
    being a runtime check rather than a load-time promise.
    """
    if is_protected(path):
        raise RegistryError(
            f"source {source_name!r} resolves to {path}, which is inside the "
            f"application's own directory ({PROTECTED_ROOT}). The Personal "
            "Branding Agent must never ingest itself (PLAN.md §5.3)."
        )


def probes_admitted_by(
    source_root: Path, include: tuple[str, ...], exclude: tuple[str, ...]
) -> list[str]:
    """Protected paths this pattern set would admit, as source-relative paths.

    Returns an empty list when the source root does not contain the
    application — which is the common case, and the reason this check is
    cheap for the twenty-odd sources that are nowhere near this repository.
    """
    if not (PROTECTED_ROOT == source_root or PROTECTED_ROOT.is_relative_to(source_root)):
        return []

    admitted = []
    for probe in _PROTECTED_PROBES:
        relative = (PROTECTED_ROOT / probe).relative_to(source_root).as_posix()
        if is_admitted(relative, include, exclude):
            admitted.append(relative)
    return admitted
