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
    BACKLOG_OPPORTUNITY_STATES,
    MAX_OPPORTUNITY_ATTEMPTS,
    TERMINAL_OPPORTUNITY_STATES,
    TERMINAL_PUBLISH_STATES,
    CredentialDerivation,
    DeliveryState,
    LifecycleState,
    OpportunityStatus,
    PublishState,
    RunOutcome,
    SyncOutcome,
    Workflow,
)
from app.state.models import (
    ContentOpportunity,
    CredentialExpiry,
    Development,
    EvidenceRef,
    Lock,
    LockAcquisition,
    MissedWindow,
    Notification,
    OperationalFailure,
    OpportunityOutcome,
    Publication,
    PublicationMetric,
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
    "BACKLOG_OPPORTUNITY_STATES",
    "MAX_OPPORTUNITY_ATTEMPTS",
    "MIGRATIONS",
    "SCHEMA_VERSION",
    "TABLES",
    "TERMINAL_OPPORTUNITY_STATES",
    "TERMINAL_PUBLISH_STATES",
    "ContentOpportunity",
    "CredentialDerivation",
    "CredentialExpiry",
    "DeliveryState",
    "Development",
    "EvidenceRef",
    "LifecycleState",
    "Lock",
    "LockAcquisition",
    "MissedWindow",
    "Notification",
    "OperationalFailure",
    "OpportunityOutcome",
    "OpportunityStatus",
    "Publication",
    "PublicationMetric",
    "PublicationRecord",
    "PublishIntent",
    "PublishState",
    "ReviewCursor",
    "RunOutcome",
    "SchedulePolicy",
    "SourceLifecycleState",
    "StateStore",
    "SyncCheckpoint",
    "SyncOutcome",
    "TrackedWork",
    "Workflow",
    "WorkflowPhase",
    "WorkflowRun",
    "content_hash_of",
    "utc_now_iso",
]
