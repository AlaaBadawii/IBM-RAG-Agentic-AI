"""Operational state layer: what the system has *done*.

Distinct from — and never mixed with — the knowledge layer, which holds what
is known about the user. Knowledge lives in `data/` and Chroma; operational
state lives here, in SQLite (``PLAN.md`` §6).

    from app.state import StateStore, RunOutcome

    with StateStore() as store:
        run = store.start_run(Workflow.BRANDING)
        ...
        store.finish_run(run.run_id, RunOutcome.DO_NOT_PUBLISH)

The store is created automatically on first use, in a gitignored location
(``state_db/``). Unlike ``chroma_db/``, it is **not** rebuildable: local
publication history is authoritative, because LinkedIn does not grant the
read access that would allow reconciliation (§5.1).
"""
from app.state.enums import (
    TERMINAL_PUBLISH_STATES,
    CredentialDerivation,
    DeliveryState,
    LifecycleState,
    PublishState,
    RunOutcome,
    SyncOutcome,
    Workflow,
)
from app.state.models import (
    CredentialExpiry,
    Development,
    EvidenceRef,
    Lock,
    LockAcquisition,
    MissedWindow,
    Notification,
    OperationalFailure,
    Publication,
    PublicationRecord,
    PublishIntent,
    ReviewCursor,
    SchedulePolicy,
    SourceLifecycleState,
    SyncCheckpoint,
    TrackedWork,
    WorkflowPhase,
    WorkflowRun,
    utc_now_iso,
)
from app.state.schema import MIGRATIONS, SCHEMA_VERSION, TABLES
from app.state.store import StateStore, content_hash_of

__all__ = [
    "TERMINAL_PUBLISH_STATES",
    "CredentialDerivation",
    "CredentialExpiry",
    "DeliveryState",
    "Development",
    "EvidenceRef",
    "LifecycleState",
    "Lock",
    "LockAcquisition",
    "MIGRATIONS",
    "MissedWindow",
    "Notification",
    "OperationalFailure",
    "Publication",
    "PublicationRecord",
    "PublishIntent",
    "PublishState",
    "ReviewCursor",
    "RunOutcome",
    "SCHEMA_VERSION",
    "SchedulePolicy",
    "SourceLifecycleState",
    "StateStore",
    "SyncCheckpoint",
    "SyncOutcome",
    "TABLES",
    "TrackedWork",
    "Workflow",
    "WorkflowPhase",
    "WorkflowRun",
    "content_hash_of",
    "utc_now_iso",
]
