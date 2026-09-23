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
    workflow_lock / WorkflowLocked / EXIT_LOCKED   the Step 12 overlap guard

Exports are resolved lazily (PEP 562) so that executing
``python -m app.workflows.<name>`` imports the submodule exactly once:
an eager import here would execute the module both as
``app.workflows.<name>`` and as ``__main__``.
"""
import importlib

_LAZY_EXPORTS = {
    "BrandingConfig": ("app.workflows.branding", "BrandingConfig"),
    "EXIT_LOCKED": ("app.workflows.scheduled", "EXIT_LOCKED"),
    "EXIT_OK": ("app.workflows.common", "EXIT_OK"),
    "EXIT_REQUIRES_HUMAN_INTERVENTION": (
        "app.workflows.common", "EXIT_REQUIRES_HUMAN_INTERVENTION"),
    "EXIT_WORKFLOW_FAILED": ("app.workflows.common", "EXIT_WORKFLOW_FAILED"),
    "SyncConfig": ("app.workflows.sync", "SyncConfig"),
    "WorkflowLocked": ("app.workflows.scheduled", "WorkflowLocked"),
    "WorkflowResult": ("app.workflows.common", "WorkflowResult"),
    "run_branding": ("app.workflows.branding", "run_branding"),
    "run_sync": ("app.workflows.sync", "run_sync"),
    "workflow_lock": ("app.workflows.scheduled", "workflow_lock"),
}


def __getattr__(name: str):
    """Import a public name on first use, keeping ``__all__`` unchanged."""
    try:
        module_name, attr = _LAZY_EXPORTS[name]
    except KeyError:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}") from None
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def __dir__():
    return sorted(list(globals()) + list(_LAZY_EXPORTS))

__all__ = [
    "EXIT_LOCKED",
    "EXIT_OK",
    "EXIT_REQUIRES_HUMAN_INTERVENTION",
    "EXIT_WORKFLOW_FAILED",
    "BrandingConfig",
    "SyncConfig",
    "WorkflowLocked",
    "WorkflowResult",
    "run_branding",
    "run_sync",
    "workflow_lock",
]
