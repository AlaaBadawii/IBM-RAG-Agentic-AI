"""Loading and validating the source registry.

The registry answers one question — *which directories are evidence about this
user?* — and its failure mode is silence. A source that is dropped because its
path moved produces no error, no signal, and a knowledge base that quietly
stops covering part of the user's work; the user finds out months later, from a
gap. So every check here collects its findings and refuses the whole file
rather than skipping an entry (``PLAN.md`` Step 2, Failure/recovery).

Four properties this module exists to establish, none of which a pattern alone
can give:

*Declared roots are places to look, not sources.* Validated directly: no
source may *be* a declared workspace root.

*The application cannot ingest itself.* Validated against the guard's probes,
so a pattern that would sweep up ``.env`` or ``app/`` fails the load.

*Nested repositories are declared, not absorbed.* A repository inside a source
must be registered in its own right or excluded with a reason, because
otherwise the outer source's revision silently speaks for content it does not
control.

*No credential ever reaches the registry file.* The file is committed, and
fourteen of the inspected repositories carry a token embedded in their git
remote URL — so the sanitizer is not hypothetical.
"""
import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.errors import RegistryError
from app.sources.enums import SourceType
from app.sources.guard import PROTECTED_ROOT, assert_path_admissible, probes_admitted_by
from app.sources.models import (
    ExcludeRule,
    NotRegisteredEntry,
    Registry,
    SourceDefinition,
)
from app.sources.patterns import PatternError, compile_pattern
from app.state.enums import LifecycleState

__all__ = [
    "MAX_SCAN_DEPTH",
    "SourceTreeScan",
    "is_virtualenv",
    "load_registry",
    "looks_like_credential",
    "sanitize_repo_url",
    "scan_source_tree",
    "validate_registry",
]

MAX_SCAN_DEPTH = 8
"""How far below a source root the nested-repository scan will descend.

Exceeding it is a *validation failure*, not a truncation: the scan exists to
prove a negative, and a scan that stopped early has proved nothing. The fix
the error message suggests — exclude the deep subtree — is also the fix that
makes synchronization faster, so the failure is worth having."""

_NESTED_SCAN_PRUNE = frozenset(
    {".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
     ".mypy_cache", ".ruff_cache", ".tox", "site-packages", ".terraform"}
)
"""Directories never descended into while scanning a source tree.

Deliberately narrow: this prunes *scanning cost*, not admissibility. Whether
their contents enter the knowledge base is decided by include/exclude alone —
pruning here must never be mistaken for a policy decision. A virtualenv is
pruned structurally instead (see :func:`is_virtualenv`), because this
workspace contains ``my_env/`` and ``fastapi_venv/`` as well as ``.venv/``,
and a prune list of names would have to guess which names someone will pick
next."""

_CREDENTIAL_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{16,}"),          # GitHub tokens
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),        # GitHub fine-grained PAT
    re.compile(r"sk-[A-Za-z0-9-]{16,}"),                # OpenAI / OpenRouter
    re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"),        # Slack
    re.compile(r"AKIA[0-9A-Z]{16}"),                    # AWS access key id
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),  # any PEM private key
)
_USERINFO_IN_URL = re.compile(r"^(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*)://[^/@]*@")


def looks_like_credential(text: str) -> bool:
    """True when ``text`` contains something that must never be committed."""
    return any(pattern.search(text) for pattern in _CREDENTIAL_PATTERNS)


def sanitize_repo_url(url: str) -> str:
    """Strip any embedded credentials from a git remote URL.

    ``https://user:ghp_xxx@github.com/o/r`` becomes ``https://github.com/o/r``.

    This is the *only* sanctioned way to turn a local repository's remote into
    a ``repo_identity``. Reading the remote verbatim and writing it into
    ``sources.yaml`` would commit a live token: fourteen inspected
    repositories are in exactly that state.
    """
    match = _USERINFO_IN_URL.match(url)
    if not match:
        return url
    return f"{match.group('scheme')}://{url[match.end():]}"


# --- the registry file ------------------------------------------------------

def load_registry(path: Path | str | None = None) -> Registry:
    """Read, build, and fully validate the registry.

    Args:
        path: registry file; defaults to ``app.paths.SOURCES_FILE``.

    Raises:
        RegistryError: the file is unreadable, malformed, or invalid. The
            message names every problem found, not just the first.
    """
    from app.paths import SOURCES_FILE

    registry_path = Path(path) if path is not None else SOURCES_FILE
    try:
        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RegistryError(f"source registry not found: {registry_path}") from exc
    except yaml.YAMLError as exc:
        raise RegistryError(f"source registry {registry_path} is not valid YAML: {exc}") from exc
    except OSError as exc:
        raise RegistryError(f"source registry {registry_path} is unreadable: {exc}") from exc

    if not isinstance(raw, dict):
        raise RegistryError(
            f"source registry {registry_path} must be a mapping, got "
            f"{type(raw).__name__}"
        )

    defaults = _default_excludes(raw.get("defaults"))
    sources = _build_sources(raw.get("sources"), defaults, registry_path)
    declared_roots = _declared_roots(raw.get("workspace_roots"), registry_path)
    not_registered = _not_registered(raw.get("not_registered"), registry_path)

    registry = Registry(
        sources=tuple(sources),
        path=registry_path,
        declared_roots=declared_roots,
        not_registered=not_registered,
    )
    validate_registry(registry, check_filesystem=True)
    return registry


def _default_excludes(defaults) -> tuple[ExcludeRule, ...]:
    """Shared exclusion rules inherited by every source.

    Stated once because they are universal — no source's virtualenv, bytecode
    cache, or ``.env`` is evidence about anyone — while source-specific
    exclusions stay written out per source. Every rule still carries its own
    reason, and the merged, effective rule set per source is what gets
    validated and can be printed.
    """
    if defaults is None:
        return ()
    if not isinstance(defaults, dict):
        raise RegistryError("'defaults' must be a mapping")
    return _parse_exclude_rules(defaults.get("exclude") or [], context="defaults")


def _build_sources(raw_sources, defaults, registry_path: Path) -> list[SourceDefinition]:
    if raw_sources is None:
        raise RegistryError(f"source registry {registry_path} declares no 'sources'")
    if not isinstance(raw_sources, list):
        raise RegistryError("'sources' must be a list")

    sources: list[SourceDefinition] = []
    for index, entry in enumerate(raw_sources):
        if not isinstance(entry, dict):
            raise RegistryError(f"sources[{index}] must be a mapping")
        name = entry.get("name") or f"sources[{index}]"
        try:
            sources.append(_parse_source(entry, defaults, where=f"sources[{index}]"))
        except RegistryError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise RegistryError(f"{name}: malformed registry entry — {exc}") from exc
    return sources


def _parse_source(entry: dict, defaults: tuple[ExcludeRule, ...], *, where: str) -> SourceDefinition:
    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        raise RegistryError(f"{where}: 'name' must be a non-empty string")

    raw_type = entry.get("type")
    try:
        source_type = SourceType(raw_type)
    except ValueError:
        allowed = ", ".join(member.value for member in SourceType)
        raise RegistryError(
            f"{name}: 'type' must be one of {allowed}; got {raw_type!r}"
        ) from None

    raw_path = entry.get("local_path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise RegistryError(f"{name}: 'local_path' must be a non-empty string")
    local_path = Path(raw_path).expanduser()

    raw_lifecycle = entry.get("lifecycle")
    try:
        lifecycle = LifecycleState(raw_lifecycle)
    except ValueError:
        allowed = ", ".join(member.value for member in LifecycleState)
        raise RegistryError(
            f"{name}: 'lifecycle' must be one of {allowed}; got {raw_lifecycle!r}. "
            "Lifecycle is declared, never inferred (PLAN.md §5.5)."
        ) from None

    include = entry.get("include") or []
    if not isinstance(include, list) or not all(isinstance(p, str) for p in include):
        raise RegistryError(f"{name}: 'include' must be a list of strings")
    if not include:
        raise RegistryError(
            f"{name}: 'include' is empty, so the source would admit nothing. "
            "State what the source is for, or remove the entry."
        )

    exclude = defaults + _parse_exclude_rules(entry.get("exclude") or [], context=name)

    repo_identity = entry.get("repo_identity")
    ref = entry.get("ref")
    if source_type is SourceType.GIT:
        if not repo_identity:
            raise RegistryError(
                f"{name}: a git source needs 'repo_identity' (remote or root identity)"
            )
        if not ref:
            raise RegistryError(f"{name}: a git source needs a 'ref' to synchronize")
    elif repo_identity or ref:
        raise RegistryError(
            f"{name}: 'repo_identity'/'ref' are meaningless for a filesystem "
            "source — it has no revision to name"
        )

    return SourceDefinition(
        name=name,
        type=source_type,
        local_path=local_path,
        lifecycle=lifecycle,
        include=tuple(include),
        exclude=exclude,
        repo_identity=str(repo_identity) if repo_identity else None,
        ref=str(ref) if ref else None,
        description=str(entry.get("description") or ""),
    )


def _parse_exclude_rules(raw_rules, *, context: str) -> tuple[ExcludeRule, ...]:
    if not isinstance(raw_rules, list):
        raise RegistryError(f"{context}: 'exclude' must be a list")
    rules = []
    for index, rule in enumerate(raw_rules):
        if isinstance(rule, str):
            raise RegistryError(
                f"{context}: exclude[{index}] is a bare pattern with no reason. "
                "Every exclusion must say why, or it cannot be reviewed later."
            )
        if not isinstance(rule, dict):
            raise RegistryError(f"{context}: exclude[{index}] must be a mapping")
        pattern = rule.get("pattern")
        reason = rule.get("reason")
        if not isinstance(pattern, str) or not pattern.strip():
            raise RegistryError(f"{context}: exclude[{index}] needs a 'pattern'")
        if not isinstance(reason, str) or not reason.strip():
            raise RegistryError(f"{context}: exclude[{index}] ({pattern!r}) needs a 'reason'")
        rules.append(ExcludeRule(pattern=pattern, reason=reason))
    return tuple(rules)


def _not_registered(raw_entries, registry_path: Path) -> tuple[NotRegisteredEntry, ...]:
    """Workspace directories considered and deliberately left out."""
    if raw_entries is None:
        return ()
    if not isinstance(raw_entries, list):
        raise RegistryError("'not_registered' must be a list")
    entries = []
    for index, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            raise RegistryError(f"not_registered[{index}] must be a mapping")
        path = entry.get("path")
        reason = entry.get("reason")
        if not isinstance(path, str) or not path.strip():
            raise RegistryError(f"not_registered[{index}] needs a 'path'")
        if not isinstance(reason, str) or not reason.strip():
            raise RegistryError(
                f"not_registered[{index}] ({path!r}) needs a 'reason'. Recording "
                "that something was considered is only useful alongside why."
            )
        entries.append(
            NotRegisteredEntry(path=Path(path).expanduser(), reason=reason)
        )
    return tuple(entries)


def _declared_roots(raw_roots, registry_path: Path) -> tuple[Path, ...]:
    if raw_roots is None:
        return ()
    if not isinstance(raw_roots, list):
        raise RegistryError("'workspace_roots' must be a list")
    roots = []
    for index, entry in enumerate(raw_roots):
        path = entry.get("path") if isinstance(entry, dict) else entry
        if not isinstance(path, str) or not path.strip():
            raise RegistryError(f"workspace_roots[{index}] needs a 'path'")
        roots.append(Path(path).expanduser())
    return tuple(roots)


# --- validation -------------------------------------------------------------

def validate_registry(registry: Registry, *, check_filesystem: bool = True) -> None:
    """Check every source; raise once, listing everything wrong.

    ``check_filesystem=False`` runs the purely declarative half — pattern
    shape, vocabulary, self-ingestion, declared roots — which is what a test
    can assert on any machine, including one that has none of these paths.
    """
    problems: list[str] = []
    problems.extend(_check_names(registry))
    problems.extend(_check_declared_roots(registry))
    problems.extend(_check_not_registered(registry))

    registered = {source.local_path.resolve() for source in registry.sources}
    for source in registry.sources:
        problems.extend(_check_patterns(source))
        problems.extend(_check_self_ingestion(source))
        problems.extend(_check_credentials(source))
        if check_filesystem:
            problems.extend(_check_path(source))
            problems.extend(_check_source_tree(source, registered))

    if problems:
        listed = "\n".join(f"  - {problem}" for problem in problems)
        raise RegistryError(
            f"source registry {registry.path} failed validation "
            f"({len(problems)} problem(s)); synchronization refuses to run "
            f"against a partial registry:\n{listed}"
        )


def _check_names(registry: Registry) -> list[str]:
    problems = []
    seen: set[str] = set()
    for source in registry.sources:
        if source.name in seen:
            problems.append(f"duplicate source name {source.name!r}")
        seen.add(source.name)
    return problems


def _check_declared_roots(registry: Registry) -> list[str]:
    """Acceptance: a declared root is a place to look, never a source.

    Stated as "no *filesystem* source may be a declared root", because the
    workspace itself draws that line. Three declared roots are git
    repositories — ``~/LLMs/IBM`` (which contains this application),
    ``~/LLMs/AI_Agents`` and ``~/Portfolio`` — and a repository rooted exactly
    at a declared root is a single revision history, which is precisely what a
    source is. The hazard the rule exists for is different: a *plain
    directory* taken wholesale as a source, which would sweep up the unrelated
    repositories, virtual environments and coursework that live loose inside
    it. A git source that is not really a repository is caught separately by
    :func:`_check_path`, so the two rules compose rather than overlap.
    """
    problems = []
    roots = {root.resolve() for root in registry.declared_roots}
    for source in registry.sources:
        if source.is_git:
            continue
        if source.local_path.resolve() in roots:
            problems.append(
                f"{source.name}: {source.local_path} is a declared workspace root. "
                "Roots are places to inspect and are never ingested wholesale — "
                "name the exact sources inside it instead."
            )
    return problems


def _check_not_registered(registry: Registry) -> list[str]:
    """The two lists must not contradict each other.

    A path that is both a registered source and an entry in
    ``not_registered`` means one of the two was edited without the other, and
    whichever the loader happened to read first would silently win.
    """
    problems = []
    registered = {source.local_path.resolve() for source in registry.sources}
    for entry in registry.not_registered:
        if entry.path.resolve() in registered:
            problems.append(
                f"{entry.path} appears in 'not_registered' but is also a "
                "registered source; remove it from one of the two"
            )
    return problems


def _check_patterns(source: SourceDefinition) -> list[str]:
    problems = []
    for pattern in source.include:
        try:
            compile_pattern(pattern)
        except PatternError as exc:
            problems.append(f"{source.name}: include pattern invalid — {exc}")
    for rule in source.exclude:
        try:
            compile_pattern(rule.pattern)
        except PatternError as exc:
            problems.append(f"{source.name}: exclude pattern invalid — {exc}")
    return problems


def _check_self_ingestion(source: SourceDefinition) -> list[str]:
    """Acceptance: the application cannot ingest itself, checked at load time."""
    problems = []
    try:
        assert_path_admissible(source.name, source.local_path)
    except RegistryError as exc:
        problems.append(str(exc))
        return problems

    admitted = probes_admitted_by(
        source.local_path.resolve(), source.include, source.exclude_patterns
    )
    if admitted:
        shown = ", ".join(admitted[:4])
        more = f" (+{len(admitted) - 4} more)" if len(admitted) > 4 else ""
        problems.append(
            f"{source.name}: patterns would admit the application's own files "
            f"({shown}{more}). The application must never ingest itself; narrow "
            "'include' or add an exclusion that covers "
            f"{PROTECTED_ROOT.relative_to(source.local_path) if PROTECTED_ROOT.is_relative_to(source.local_path) else PROTECTED_ROOT}."
        )
    return problems


def _check_credentials(source: SourceDefinition) -> list[str]:
    """Acceptance: the committed registry never carries a secret value."""
    problems = []
    for field_name, value in (
        ("repo_identity", source.repo_identity),
        ("description", source.description),
    ):
        if value and looks_like_credential(value):
            problems.append(
                f"{source.name}: {field_name} looks like it contains a credential. "
                "The registry is committed — sanitize it with sanitize_repo_url()."
            )
    for pattern in source.include:
        if looks_like_credential(pattern):
            problems.append(f"{source.name}: include pattern carries a credential")
    return problems


def _check_path(source: SourceDefinition) -> list[str]:
    """A registered-but-missing path is a reported failure, not a silent skip."""
    problems = []
    path = source.local_path
    if not path.exists():
        problems.append(
            f"{source.name}: registered path does not exist — {path}. "
            "Fix the registry or restore the source."
        )
        return problems
    if not path.is_dir():
        problems.append(f"{source.name}: {path} is not a directory")
        return problems

    declared_git = source.is_git
    actual_git = (path / ".git").exists()
    if declared_git and not actual_git:
        problems.append(
            f"{source.name}: declared type 'git' but {path} has no .git — "
            "the registry and the filesystem disagree"
        )
    elif not declared_git and actual_git:
        problems.append(
            f"{source.name}: declared type 'filesystem' but {path} is a git "
            "repository; declare it as 'git' so its revision can be tracked"
        )
    return problems


def _check_source_tree(source: SourceDefinition, registered: set[Path]) -> list[str]:
    """Nested repositories are declared, and virtualenvs are excluded.

    Both are the same failure: something inside the source that the pattern
    set does not name, and that would therefore be synchronized as if the
    user had written it. A nested repository would additionally be
    *mis-attributed* — the outer source's revision would appear to speak for
    content whose history it does not contain.
    """
    problems = []
    scan = scan_source_tree(source.local_path, source.exclude_patterns)

    for nested in scan.nested_repositories:
        if nested.resolve() in registered:
            continue  # registered in its own right; not absorbed
        relative = nested.relative_to(source.local_path).as_posix()
        problems.append(
            f"{source.name}: nested git repository at {relative}/ is neither "
            "registered as its own source nor excluded. Register it so it gets "
            "its own revision, or exclude it and say why."
        )

    for venv in scan.virtualenvs:
        relative = venv.relative_to(source.local_path).as_posix()
        problems.append(
            f"{source.name}: virtual environment at {relative}/ is not excluded. "
            "Its contents are third-party library code, not authored work, and "
            "its .py files would otherwise match the include patterns. Exclude "
            "it explicitly (patterns cannot rely on the directory being called "
            "'.venv')."
        )
    return problems


def is_virtualenv(path: Path) -> bool:
    """True when ``path`` is a Python virtual environment.

    ``pyvenv.cfg`` is the marker ``venv``/``virtualenv`` writes at the root,
    and it is checked instead of a list of directory names on purpose: this
    workspace holds virtualenvs called ``.venv``, ``venv``, ``my_env`` and
    ``fastapi_venv``, so matching on names would miss whichever one came
    next — and a missed virtualenv is hundreds of megabytes of third-party
    library code pulled into a corpus of the user's own work.
    """
    return (path / "pyvenv.cfg").is_file()


@dataclass(frozen=True)
class SourceTreeScan:
    """What a source's directory tree contains that the registry must own up to."""

    nested_repositories: tuple[Path, ...] = ()
    virtualenvs: tuple[Path, ...] = ()


def scan_source_tree(
    root: Path,
    exclude_patterns: tuple[str, ...] | list[str] = (),
    *,
    max_depth: int = MAX_SCAN_DEPTH,
) -> SourceTreeScan:
    """Find nested repositories and unexcluded virtualenvs at or below ``root``.

    One walk answering both questions, because they are the same question —
    *is there something in this tree that a pattern must name explicitly
    before synchronization can be trusted?* — and because walking a 617 MB
    virtualenv to answer it twice would defeat the purpose.

    Descends breadth-first so that hitting :data:`MAX_SCAN_DEPTH` reports the
    true minimum depth rather than whichever branch was walked first.

    Raises:
        RegistryError: the scan hit ``max_depth`` with directories still
            unexplored. Returning a short list here would be a false
            negative, and a false negative is the one answer this scan must
            never give.
    """
    from app.sources.patterns import matches

    nested: list[Path] = []
    virtualenvs: list[Path] = []
    frontier: list[tuple[Path, int]] = [(root, 0)]

    while frontier:
        current, depth = frontier.pop(0)
        if depth >= max_depth:
            if any(current.iterdir()):
                raise RegistryError(
                    f"source-tree scan under {root} reached the "
                    f"{max_depth}-directory depth limit at {current} and cannot "
                    "prove there is no repository or virtualenv below it. "
                    "Exclude that subtree, or raise MAX_SCAN_DEPTH deliberately."
                )
            continue

        try:
            entries = sorted(os.scandir(current), key=lambda e: e.name)
        except OSError:
            continue  # unreadable subtree: reported by the path check instead

        for entry in entries:
            if not entry.is_dir(follow_symlinks=False):
                continue
            child = Path(entry.path)
            if entry.name == ".git":
                # The root's own .git makes the root a repository, not a
                # repository nested inside itself.
                if current != root:
                    nested.append(current)
                continue

            relative = child.relative_to(root).as_posix()
            if any(matches(relative, pattern) for pattern in exclude_patterns):
                continue  # excluded, so its contents are not this source's

            if is_virtualenv(child):
                virtualenvs.append(child)
                continue
            if entry.name in _NESTED_SCAN_PRUNE:
                continue
            frontier.append((child, depth + 1))

    return SourceTreeScan(
        nested_repositories=tuple(sorted(set(nested))),
        virtualenvs=tuple(sorted(set(virtualenvs))),
    )

