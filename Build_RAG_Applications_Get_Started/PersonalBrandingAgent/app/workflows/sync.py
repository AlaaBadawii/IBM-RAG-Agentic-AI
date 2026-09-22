"""The 24-hour knowledge-synchronization workflow (``PLAN.md`` Step 11).

Owns and sequences the existing sync capability — nothing more:

    load_registry  →  synchronize  →  record outcome + notify on failure

* Every phase transition is recorded; a failure identifies its phase.
* A ``workflow_runs`` row tracks the run from start to its recorded outcome.
* On failure the run persists the failure and sends exactly one notification.
* This workflow **never publishes** and **never invokes branding/agent
  logic** — asserted structurally by the test suite, not just behaviourally.

``python -m app.workflows.sync`` runs it once and exits with the outcome's
exit code. No scheduler lives here (Step 12).
"""
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

from app.errors import StateStoreError
from app.logging_config import get_logger
from app.notify.service import NotificationService
from app.sources.models import Registry
from app.state.enums import RunOutcome, Workflow
from app.state.store import StateStore
from app.sync.models import SyncRunResult
from app.workflows.common import (
    EXIT_OK,
    Escalation,
    WorkflowResult,
    finish,
    record_phase_failure,
    run_phase,
    start,
)
from app.workflows.scheduled import EXIT_LOCKED, WorkflowLocked, workflow_lock

logger = get_logger(__name__)

#: The sync workflow's phases, in order. The workflow enters each one, and
#: each transition is recorded — so a run's trail is queryable afterwards.
SYNC_PHASES = ("load_registry", "synchronize")

__all__ = ["SYNC_PHASES", "SyncConfig", "main", "run_sync"]


def _default_sync(registry: Registry, store: StateStore) -> SyncRunResult:
    """The real synchronization binding: the existing layer, called as-is."""
    from app.sync import SyncContext, sync_all

    return sync_all(registry, SyncContext(store=store))


def _default_registry_loader() -> Registry:
    """The real registry binding: committed configuration, validated on load."""
    from app.sources import load_registry

    return load_registry()


@dataclass
class SyncConfig:
    """The sync workflow's seams. Defaults are the real layers; tests inject
    fakes. No real LinkedIn, SMTP, ingestion, or LLM call happens unless the
    default bindings are used."""

    store_factory: Callable[[], StateStore] = field(
        default_factory=StateStore
    )
    registry_loader: Callable[[], Registry] = field(
        default_factory=lambda: _default_registry_loader
    )
    sync_fn: Callable[[Registry, StateStore], SyncRunResult] = field(
        default_factory=lambda: _default_sync
    )
    notifier_factory: Callable[[StateStore], Any] = field(
        default_factory=lambda store: NotificationService(store)
    )


def run_sync(config: SyncConfig | None = None) -> WorkflowResult:
    """Run one knowledge synchronization and return its structured result.

    Outcomes:

    * no source failed → ``DO_NOT_PUBLISH`` (exit 0, no notification — a sync
      never publishes, so a clean sync is a successful no-op);
    * a source failed transiently → ``WORKFLOW_FAILED`` (exit 1, persist the
      failed ``synchronize`` phase + exactly one notification);
    * a source needs a person (missing path, guard refusal, a ``COMPLETED``
      source with new activity) → ``REQUIRES_HUMAN_INTERVENTION`` (exit 2,
      persisted separately + exactly one notification).

    The whole run executes under the Step 12 overlap guard: a second
    invocation while this workflow is locked raises :class:`WorkflowLocked`
    without running anything.
    """
    cfg = config or SyncConfig()
    try:
        store = cfg.store_factory()
    except StateStoreError as exc:
        # No durable state means the run cannot be recorded at all — the one
        # failure that has no run row, reported without a store.
        logger.error("Sync workflow could not open the state store: %s", exc)
        raise
    with workflow_lock(store, Workflow.SYNC):
        run = start(store, Workflow.SYNC)
        notifier = cfg.notifier_factory(store)

        try:
            registry = run_phase(store, run, "load_registry", cfg.registry_loader)
            sync_result = run_phase(
                store, run, "synchronize", lambda: cfg.sync_fn(registry, store)
            )
        except Escalation as esc:
            return finish(
                store, run, esc.outcome,
                failed_phase=esc.phase, error=esc.error,
                error_category=esc.error_category, notifier=notifier,
            )

        synced = len(sync_result.synced)
        unchanged = len(sync_result.unchanged)
        failed = [r for r in sync_result.failed]
        detail: dict[str, Any] = {
            "synced": synced,
            "unchanged": unchanged,
            "failed": len(failed),
        }
        if sync_result.requires_human_intervention:
            names = ", ".join(
                r.source_name for r in sync_result.results
                if r.requires_human_intervention
            )
            error = (
                "synchronization needs a person: "
                f"{names or 'a source reported a condition the system cannot resolve'}"
            )
            logger.warning("Sync run %s requires human intervention: %s", run.run_id, error)
            record_phase_failure(store, run, "synchronize", error,
                                 "synchronize_needs_review", human=True)
            return finish(
                store, run, RunOutcome.REQUIRES_HUMAN_INTERVENTION,
                failed_phase="synchronize", error=error,
                error_category="synchronize_needs_review",
                notifier=notifier, detail=detail,
            )
        if failed:
            names = ", ".join(r.source_name for r in failed)
            error = f"synchronization failed for {len(failed)} source(s): {names}"
            logger.warning("Sync run %s failed: %s", run.run_id, error)
            record_phase_failure(store, run, "synchronize", error,
                                 "synchronize_failed", human=False)
            return finish(
                store, run, RunOutcome.WORKFLOW_FAILED,
                failed_phase="synchronize", error=error,
                error_category="synchronize_failed",
                notifier=notifier, detail=detail,
            )
        logger.info(
            "Sync run %s finished: %d synced, %d unchanged",
            run.run_id, synced, unchanged,
        )
        return finish(
            store, run, RunOutcome.DO_NOT_PUBLISH, notifier=notifier, detail=detail
        )


def main(argv: list[str] | None = None) -> int:
    """Module entry point: ``python -m app.workflows.sync``."""
    del argv  # no flags: the registry is the configuration.
    try:
        result = run_sync()
    except WorkflowLocked as locked:
        print(f"sync locked out: {locked}")
        return EXIT_LOCKED
    print(
        f"sync run {result.run_id}: {result.outcome.value} "
        f"(exit {result.exit_code})"
    )
    return result.exit_code if isinstance(result.exit_code, int) else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
