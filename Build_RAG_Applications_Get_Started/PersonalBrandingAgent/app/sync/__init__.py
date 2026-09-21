"""Incremental knowledge synchronization (``PLAN.md`` Step 3).

Deciding *what* changed in the registered sources, and handing exactly that to
the ingestion pipeline that already knows *how* to index it:

    Source registry → change detection → candidate files → relevance policy
                    → existing ingestion pipeline → content hashes → Chroma

Two questions this package refuses to conflate:

    Git                what changed since the last processed revision?
    Application state  what revision did the system successfully process?

Every public name is re-exported here so a caller (Step 11's workflow, a test)
never has to know which module a piece lives in.

    read_revision     where a source is now
    changed_paths     what differs between two revisions, per git
    decide            whether one path enters the knowledge base, and why not
    candidate_files   the pipeline's input, named and guarded
    sync_source       one source, start to finish
    sync_all          every registered source, isolated from each other
"""
from app.sync.candidates import SourceCandidate, candidate_files
from app.sync.enums import ChangeType, RevisionKind, SyncErrorCategory, SyncStatus
from app.sync.models import ChangedPath, SourceSyncResult, SyncRunResult
from app.sync.namespace import (
    NAMESPACE_PREFIX,
    is_source_key,
    source_key,
    source_namespace,
)
from app.sync.relevance import (
    Admission,
    ChangePlan,
    annotate,
    decide,
    full_resync_plan,
    plan_changes,
)
from app.sync.revision import (
    CONTENT_REVISION_PREFIX,
    SourceRevision,
    changed_paths,
    content_revision,
    iter_admitted_files,
    read_admitted_paths,
    read_revision,
)
from app.sync.synchronizer import SyncContext, pipeline_ingest, sync_all, sync_source

__all__ = [
    "CONTENT_REVISION_PREFIX",
    "NAMESPACE_PREFIX",
    "Admission",
    "ChangePlan",
    "ChangeType",
    "ChangedPath",
    "RevisionKind",
    "SourceCandidate",
    "SourceRevision",
    "SourceSyncResult",
    "SyncContext",
    "SyncErrorCategory",
    "SyncRunResult",
    "SyncStatus",
    "annotate",
    "candidate_files",
    "changed_paths",
    "content_revision",
    "decide",
    "full_resync_plan",
    "is_source_key",
    "iter_admitted_files",
    "pipeline_ingest",
    "plan_changes",
    "read_admitted_paths",
    "read_revision",
    "source_key",
    "source_namespace",
    "sync_all",
    "sync_source",
]
