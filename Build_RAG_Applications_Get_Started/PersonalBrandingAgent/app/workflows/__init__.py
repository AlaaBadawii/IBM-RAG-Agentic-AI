"""Top-level workflow orchestration (``PLAN.md`` Step 11).

Two independent, separately executable workflows with different periods,
different failure domains, and different blast radii:

    python -m app.workflows.sync        (24h knowledge synchronization)
    python -m app.workflows.branding    (8h branding pipeline)

The split is the point. Sync must never publish; branding must never ingest.
Each workflow owns sequencing, phase/error handling, workflow-run recording,
the final outcome, and notification policy — and nothing else:

* **No reasoning.** The Agent (Step 10) decides content; the workflow decides
  sequencing. The workflow never re-derives what the layers below already
  decided, and never duplicates their deterministic rules.
* **No scheduler.** Both entry points run once and exit. Scheduling is Step 12.
* **Three outcomes, recorded — never inferred.** Every run ends as exactly one
  of ``DO_NOT_PUBLISH`` (success, exit 0, no failure notification),
  ``WORKFLOW_FAILED`` (exit 1, persist + notify), or
  ``REQUIRES_HUMAN_INTERVENTION`` (exit 2, persist + notify, distinct code).

Public surface, and deliberately nothing more:

    run_sync / SyncConfig          the 24h entry point and its seams
    run_branding / BrandingConfig  the 8h entry point and its seams
    WorkflowResult                 the structured run result
    EXIT_OK / EXIT_WORKFLOW_FAILED / EXIT_REQUIRES_HUMAN_INTERVENTION
"""
from app.workflows.branding import BrandingConfig, run_branding
from app.workflows.common import (
    EXIT_OK,
    EXIT_REQUIRES_HUMAN_INTERVENTION,
    EXIT_WORKFLOW_FAILED,
    WorkflowResult,
)
from app.workflows.sync import SyncConfig, run_sync

__all__ = [
    "EXIT_OK",
    "EXIT_REQUIRES_HUMAN_INTERVENTION",
    "EXIT_WORKFLOW_FAILED",
    "BrandingConfig",
    "SyncConfig",
    "WorkflowResult",
    "run_branding",
    "run_sync",
]
