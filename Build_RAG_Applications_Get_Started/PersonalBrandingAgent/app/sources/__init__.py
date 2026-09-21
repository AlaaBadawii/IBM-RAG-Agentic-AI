"""Source registry: which directories are evidence about the user.

The layer between the filesystem and the synchronizer. Its whole job is to
replace "the workspace roots" — eight directories holding ~28 git
repositories, virtual environments, coursework, and this application itself —
with a short list of sources someone can actually read and disagree with
(``PLAN.md`` §5.3, Step 2).

    from app.sources import load_registry, plan_for

    registry = load_registry()
    for source in registry:
        plan = plan_for(source, has_changes=source.name in changed)
        ...  # plan.ingest is always True; plan.needs_review may be

The registry file (``sources.yaml``) is committed configuration; the
per-source sync state it names is *not* here. Last-processed revisions live in
``app.state``'s ``sync_checkpoints`` table and lifecycle transitions in
``source_lifecycle`` — definition and state are never conflated (Step 2,
Data/state).
"""
from app.sources.enums import SourceType, SyncDisposition, SyncPriority
from app.sources.guard import (
    PROTECTED_ROOT,
    assert_path_admissible,
    is_protected,
    probes_admitted_by,
    protected_probes,
)
from app.sources.lifecycle import (
    StatusReviewSignal,
    SyncPlan,
    plan_for,
    review_signal_for,
)
from app.sources.models import (
    ExcludeRule,
    NotRegisteredEntry,
    Registry,
    SourceDefinition,
)
from app.sources.patterns import PatternError, is_admitted, matches
from app.sources.registry import (
    load_registry,
    looks_like_credential,
    sanitize_repo_url,
    validate_registry,
)

__all__ = [
    "ExcludeRule",
    "NotRegisteredEntry",
    "PROTECTED_ROOT",
    "PatternError",
    "Registry",
    "SourceDefinition",
    "SourceType",
    "StatusReviewSignal",
    "SyncDisposition",
    "SyncPlan",
    "SyncPriority",
    "assert_path_admissible",
    "is_admitted",
    "is_protected",
    "load_registry",
    "looks_like_credential",
    "matches",
    "plan_for",
    "probes_admitted_by",
    "protected_probes",
    "review_signal_for",
    "sanitize_repo_url",
    "validate_registry",
]
