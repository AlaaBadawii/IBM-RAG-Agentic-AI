"""Shared orchestration machinery for the two Step 11 workflows.

What lives here, and why it is shared rather than duplicated:

* the exit-code vocabulary (``0`` / ``1`` / ``2``), so the two entry points
  cannot drift into disagreeing about what "needs a human" looks like to a
  scheduler;
* :class:`WorkflowResult`, the structured run result both workflows return;
* :class:`HumanIntervention`, the escalation a phase raises when the system
  cannot safely resolve the condition on its own;
* :func:`requires_human`, the one classifier that turns an exception into an
  outcome — the workflow, never the Agent, classifies;
* :func:`run_phase`, the wrapper that makes every phase boundary identify its
  phase: the transition is recorded, and a failure leaves a structured failure
  row carrying the phase name;
* :func:`finish`, which records the final outcome on the run and applies the
  notification policy exactly once.

What deliberately does **not** live here: sequencing (each workflow owns its
own phases), reasoning, publishing, ingestion, or any import of the sync,
publishing, agent, generation, or verification layers — this module depends
only on the state store and the notification service, which both workflows
are allowed to use.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

from app.errors import RegistryError, SourceUnavailableError, StateStoreError
from app.logging_config import get_logger
from app.state.enums import RunOutcome, Workflow
from app.state.models import WorkflowRun
from app.state.store import StateStore

logger = get_logger(__name__)

#: A normal no-op. Successful exit, no failure notification.
EXIT_OK = 0
#: A phase could not complete. Non-zero exit, persist + exactly one notification.
EXIT_WORKFLOW_FAILED = 1
#: The system cannot safely resolve the condition on its own. Non-zero and
#: distinct from an ordinary failure, persist + exactly one notification, and
#: never automatically retried.
EXIT_REQUIRES_HUMAN_INTERVENTION = 2

OUTCOME_EXIT = {
    RunOutcome.DO_NOT_PUBLISH: EXIT_OK,
    RunOutcome.WORKFLOW_FAILED: EXIT_WORKFLOW_FAILED,
    RunOutcome.REQUIRES_HUMAN_INTERVENTION: EXIT_REQUIRES_HUMAN_INTERVENTION,
}

__all__ = [
    "EXIT_OK",
    "EXIT_REQUIRES_HUMAN_INTERVENTION",
    "EXIT_WORKFLOW_FAILED",
    "OUTCOME_EXIT",
    "Escalation",
    "HumanIntervention",
    "WorkflowResult",
    "finish",
    "requires_human",
    "run_phase",
]


class HumanIntervention(Exception):
    """A phase raises this when a person must resolve the condition.

    ``PLAN.md`` §2 names the conditions: an expired credential, an ambiguous
    publication outcome, an unrecoverable configuration problem, a missing
    source, an unavailable store. Retrying cannot help, so the workflow records
    ``REQUIRES_HUMAN_INTERVENTION`` — never ``WORKFLOW_FAILED`` — and does not
    retry.
    """

    def __init__(self, message: str, *, error_category: str = "human_intervention"):
        super().__init__(message)
        self.error_category = error_category


class Escalation(Exception):
    """A phase failure, already recorded, awaiting outcome + notification.

    Raised internally by :func:`run_phase` so the workflow body stays a
    straight-line sequence: either every phase succeeds, or the first failure
    carries its outcome, phase, and message to :func:`finish`.
    """

    def __init__(self, outcome: RunOutcome, phase: str, error: str,
                 error_category: str):
        super().__init__(f"{phase}: {error}")
        self.outcome = outcome
        self.phase = phase
        self.error = error
        self.error_category = error_category


@dataclass(frozen=True)
class WorkflowResult:
    """The structured result of one workflow run.

    Returned by both entry points and therefore the shape a scheduler, a test,
    or Step 12 reads — never the exit code alone. The outcome is also recorded
    on the workflow run, so it is never inferred from this object at read time.
    """

    run_id: str
    workflow: str
    outcome: RunOutcome
    failed_phase: str | None = None
    error: str | None = None
    phases: tuple[str, ...] = ()
    """Every phase the run entered, in order — the recorded trail."""
    exit_code: int = EXIT_OK
    notified: bool = False
    """True when a failure notification was sent for this run."""
    detail: dict[str, Any] = field(default_factory=dict)
    """Workflow-specific record: sync counts, publication ids, agent reasons."""


T = TypeVar("T")


def requires_human(exc: Exception) -> bool:
    """True when the failure needs a person rather than another run.

    The check is structural, never prose matching:

    * an explicit :class:`HumanIntervention` escalation;
    * anything carrying ``requires_human_intervention is True`` (the
      generation layer's configuration failures, the publishing service's
      ambiguous/auth outcomes);
    * a source that is missing or no longer a repository
      (:class:`SourceUnavailableError`);
    * an unrecoverable configuration problem (:class:`RegistryError`);
    * a state store that is unavailable or corrupted
      (:class:`StateStoreError`) — without durable state the run cannot
      record what it did, so failing closed means asking a person.

    Everything else is an ordinary phase failure the next scheduled run may
    retry.
    """
    if isinstance(exc, HumanIntervention):
        return True
    if getattr(exc, "requires_human_intervention", False) is True:
        return True
    if isinstance(exc, (SourceUnavailableError, RegistryError, StateStoreError)):
        return True
    return False


def _category_of(exc: Exception, phase: str) -> str:
    """A recordable category for a phase failure, without parsing prose."""
    category = getattr(exc, "category", None)
    if category is not None:
        return str(getattr(category, "value", category))
    explicit = getattr(exc, "error_category", None)
    if isinstance(explicit, str) and explicit.strip():
        return explicit
    return f"{phase}_failed"


def run_phase(store: StateStore, run: WorkflowRun, phase: str,
              fn: Callable[[], T]) -> T:
    """Run one phase, recording the transition and attributing any failure.

    On success the phase is recorded as ``ok`` and its value returned. On
    failure the phase is recorded as ``failed``, a structured failure row is
    written carrying the phase name, and an :class:`Escalation` is raised with
    the already-classified outcome — so every phase boundary makes the failed
    phase identifiable, and the workflow body never branches on exceptions.
    """
    try:
        value = fn()
    except Escalation:
        raise
    except Exception as exc:
        human = requires_human(exc)
        message = str(exc) or f"{phase} failed with {type(exc).__name__}"
        store.record_phase(run.run_id, phase, "failed", error=message)
        try:
            store.record_failure(
                phase=phase,
                error_category=_category_of(exc, phase),
                message=message,
                retryable=not human,
                requires_human_intervention=human,
                run_id=run.run_id,
                workflow=run.workflow,
            )
        except StateStoreError as store_exc:
            logger.error(
                "Could not record the %s failure for run %s: %s",
                phase, run.run_id, store_exc,
            )
        raise Escalation(
            outcome=(RunOutcome.REQUIRES_HUMAN_INTERVENTION if human
                     else RunOutcome.WORKFLOW_FAILED),
            phase=phase,
            error=message,
            error_category=_category_of(exc, phase),
        ) from exc
    store.record_phase(run.run_id, phase, "ok")
    return value


def finish(store: StateStore, run: WorkflowRun, outcome: RunOutcome, *,
           failed_phase: str | None = None, error: str | None = None,
           error_category: str | None = None,
           notifier: Any | None = None,
           detail: dict[str, Any] | None = None) -> WorkflowResult:
    """Record the final outcome on the run and apply the notification policy.

    * ``DO_NOT_PUBLISH`` is a success: the run is recorded and **no
      notification is sent** — the notifier is not even called.
    * ``WORKFLOW_FAILED`` and ``REQUIRES_HUMAN_INTERVENTION`` persist the
      failure (when the caller did not already record one via
      :func:`run_phase`) and send **exactly one** failure notification through
      ``notifier.notify_run(run_id)``.

    The outcome is recorded on the workflow run, never inferred from the exit
    code at read time. A notification delivery failure is logged and reported
    via ``notified=False`` — it never masks the workflow outcome.
    """
    phases = tuple(p.phase for p in store.list_phases(run.run_id))
    if outcome is not RunOutcome.DO_NOT_PUBLISH and failed_phase:
        if not store.list_failures(run_id=run.run_id):
            store.record_failure(
                phase=failed_phase,
                error_category=error_category or f"{failed_phase}_failed",
                message=error or f"{failed_phase} failed",
                retryable=outcome is RunOutcome.WORKFLOW_FAILED,
                requires_human_intervention=(
                    outcome is RunOutcome.REQUIRES_HUMAN_INTERVENTION
                ),
                run_id=run.run_id,
                workflow=run.workflow,
            )
    store.finish_run(run.run_id, outcome, failed_phase=failed_phase)

    notified = False
    if outcome is not RunOutcome.DO_NOT_PUBLISH and notifier is not None:
        try:
            report = notifier.notify_run(run.run_id)
            notified = report.decision.name == "SENT"
        except Exception as exc:  # noqa: BLE001 — alerting must not mask outcome
            logger.warning(
                "Failure notification for run %s could not be delivered: %s",
                run.run_id, exc,
            )
    return WorkflowResult(
        run_id=run.run_id,
        workflow=run.workflow,
        outcome=outcome,
        failed_phase=failed_phase,
        error=error,
        phases=phases,
        exit_code=OUTCOME_EXIT[outcome],
        notified=notified,
        detail=dict(detail or {}),
    )


def start(store: StateStore, workflow: Workflow) -> WorkflowRun:
    """Record the start of a run. Thin wrapper, so workflows read as prose."""
    run = store.start_run(workflow)
    logger.info("Workflow %s started run %s", workflow.value, run.run_id)
    return run
