"""Scheduled-invocation guard: overlap protection, stale recovery, and
interrupted-run detection (``PLAN.md`` Step 12).

The scheduler (cron — see ``ops/personal-branding-agent.cron``) invokes the
Step 11 entry points directly::

    python -m app.workflows.sync
    python -m app.workflows.branding

so the guard lives *inside* those invocations: no scheduler is required for
locking, and calling ``run_sync()`` / ``run_branding()`` directly executes
guarded as well. There is no long-running Python scheduler anywhere here —
this module runs once per invocation and exits.

Source of truth is the Step 1 ``locks`` table. Per workflow, at most one live
owner:

* a second invocation while the lock is held is rejected: it records the
  rejection, never enters the workflow, and exits ``EXIT_LOCKED`` (distinct
  from the Step 11 ``0/1/2`` outcomes, which are preserved untouched);
* a stale lock is reclaimed only after the previous owner is shown to be gone.

The reclaim rule is deliberately **not** a naive timeout. Step 1's
``acquire_lock`` reclaims on expiry alone, which would silently hand a second
live process the lock if the first merely overran its TTL. This layer therefore
never calls it while the owner is demonstrably alive: every owner this layer
writes is ``hostname:pid:token``, and an expired lock whose pid is still alive
on this host is treated as held — the new invocation is rejected, never
granted. Only an expired lock whose owner is dead (or unidentifiable-but-gone
is *not* enough: an unparseable owner is treated as held, fail-closed) may be
reclaimed, and the reclaim itself goes through the atomic Step 1 transaction,
so two simultaneous recovery attempts cannot both take ownership.

Residual risk, stated plainly: pid reuse. If the dead owner's pid has been
recycled by an unrelated long-lived process, the lock looks live and
invocations keep being rejected — a missed run, never an overlap. It
self-heals when that pid dies, and the rejection rows say exactly whose pid
is squatting so an operator can clear the row by hand.

Interrupted runs: after a successful acquisition, any still-unfinished run of
the same workflow is reported (one row per run id, occurrence-counted,
``run_id`` left empty so it never leaks into a run's notification) and left
untouched — never resolved, never retried. In particular the guard never
touches publish state, so an ambiguous publication cannot be blindly retried
by recovery; the branding workflow's own pre-publish guard still applies.
An unfinished run seen while the lock is held is the live holder's own run in
progress, so it is *not* reported as interrupted.
"""
import os
import socket
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from app.errors import StateStoreError
from app.logging_config import get_logger
from app.state.enums import Workflow
from app.state.models import utc_now_iso
from app.state.store import StateStore

logger = get_logger(__name__)

#: How long one invocation may hold a workflow lock. Deliberately shorter
#: than the shortest schedule interval (8h branding): a holder that died is
#: always reclaim-eligible by the next tick. The timeout alone never grants
#: ownership while the owner is alive — see the module docstring.
LOCK_TTL_SECONDS = 6 * 3600.0

#: Phase names for rows this layer writes. ``run_id`` is always empty on
#: them, so they never leak into a workflow run's failure notification.
LOCK_PHASE = "lock"
RECOVERY_PHASE = "recovery"

#: A locked-out invocation exits without running the workflow. Distinct from
#: the Step 11 ``0/1/2`` outcomes so a scheduler can tell "did not run" from
#: every recorded workflow outcome.
EXIT_LOCKED = 3

__all__ = [
    "EXIT_LOCKED",
    "LOCK_PHASE",
    "LOCK_TTL_SECONDS",
    "RECOVERY_PHASE",
    "GuardInfo",
    "WorkflowLocked",
    "acquire_workflow_lock",
    "lock_name_for",
    "release_workflow_lock",
    "try_acquire",
    "workflow_lock",
]


class WorkflowLocked(Exception):
    """A scheduled invocation that must not run: the workflow is locked.

    Raised after recording the rejection. The entry point converts it to
    ``EXIT_LOCKED``; it never becomes a workflow run, an outcome, or a retry.
    """

    def __init__(self, lock_name: str, holder: str | None, message: str):
        super().__init__(message)
        self.lock_name = lock_name
        self.holder = holder


@dataclass(frozen=True)
class GuardInfo:
    """What a successful acquisition established."""

    owner: str
    recovered_stale: bool = False
    interrupted_run_ids: tuple[str, ...] = ()


def lock_name_for(workflow: Workflow | str) -> str:
    """The one lock name owned by a workflow. One name per workflow is what
    makes "two invocations cannot execute concurrently" a property of the
    state rather than of the callers remembering to coordinate."""
    wid = workflow.value if isinstance(workflow, Workflow) else str(workflow)
    return f"workflow:{wid}"


def _workflow_id(workflow: Workflow | str) -> str:
    return workflow.value if isinstance(workflow, Workflow) else str(workflow)


def _make_owner() -> str:
    """An identifiable owner: where, which process, which invocation."""
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def _parse_owner(owner: str) -> tuple[str, int, str] | None:
    """Split an owner back into ``(hostname, pid, token)``.

    Returns ``None`` for anything this layer did not write — which is treated
    as held, fail-closed, rather than reclaimed on a guess.
    """
    parts = owner.split(":")
    if len(parts) != 3:
        return None
    host, pid_raw, token = parts
    if not host.strip() or not token.strip():
        return None
    try:
        pid = int(pid_raw)
    except ValueError:
        return None
    if pid <= 0:
        return None
    return host, pid, token


def _pid_alive(pid: int) -> bool:
    """Whether a pid is demonstrably alive on this host.

    Signal ``0`` performs no action — it only asks the kernel. An explicit
    "no such process" is the one answer trusted as dead; every other outcome
    (including permission errors and uninterpretable values) is treated as
    alive, because the safe direction on doubt is to refuse, never to steal.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (ValueError, OverflowError):
        return False
    except OSError:
        return True
    return True


def try_acquire(store: StateStore, lock_name: str, owner: str,
                ttl_seconds: float = LOCK_TTL_SECONDS) -> Any:
    """Atomic take-or-refuse for one lock, with liveness-gated reclaim.

    Returns the Step 1 acquisition (``acquired`` is exactly one winner across
    simultaneous callers). Refusal — held, live-but-stale, foreign, or lost
    race — raises :class:`WorkflowLocked` *after recording the rejection*.
    Never grants a lock whose owner is demonstrably alive.
    """
    existing = store.get_lock(lock_name)
    if existing is None:
        acquisition = store.acquire_lock(lock_name, owner, ttl_seconds)
        if not acquisition.acquired:
            _record_rejection(
                store, lock_name, acquisition.holder,
                f"{lock_name} is already running "
                f"(owner {acquisition.holder}); invocation exits without running",
            )
            raise WorkflowLocked(
                lock_name, acquisition.holder,
                f"{lock_name} is already running (owner {acquisition.holder})",
            )
        return acquisition

    if existing.expires_at > utc_now_iso():
        _record_rejection(
            store, lock_name, existing.owner,
            f"{lock_name} is already running (owner {existing.owner}); "
            f"invocation exits without running",
        )
        raise WorkflowLocked(
            lock_name, existing.owner,
            f"{lock_name} is already running (owner {existing.owner})",
        )

    parsed = _parse_owner(existing.owner)
    if parsed is not None:
        host, pid, _token = parsed
        if host == socket.gethostname() and _pid_alive(pid):
            _record_rejection(
                store, lock_name, existing.owner,
                f"{lock_name} is stale but its owner process {pid} is still "
                f"running on this host; refusing to reclaim so two live "
                f"processes can never overlap",
            )
            raise WorkflowLocked(
                lock_name, existing.owner,
                f"{lock_name} is held by live process {pid}; not reclaiming",
            )
    else:
        _record_rejection(
            store, lock_name, existing.owner,
            f"{lock_name} is stale but its owner {existing.owner!r} cannot be "
            f"identified; refusing to reclaim on a guess",
        )
        raise WorkflowLocked(
            lock_name, existing.owner,
            f"{lock_name} has an unidentifiable owner; not reclaiming",
        )

    previous_owner = existing.owner
    acquisition = store.acquire_lock(lock_name, owner, ttl_seconds)
    if not acquisition.acquired:
        _record_rejection(
            store, lock_name, acquisition.holder,
            f"{lock_name} was reclaimed by a competing invocation "
            f"(owner {acquisition.holder}); this invocation exits",
        )
        raise WorkflowLocked(
            lock_name, acquisition.holder,
            f"{lock_name} was taken by a competing invocation",
        )
    store.record_failure(
        phase=LOCK_PHASE,
        error_category="stale_lock_recovered",
        message=(f"reclaimed stale {lock_name} from {previous_owner}; the "
                 f"previous holder is not running"),
        retryable=False,
        requires_human_intervention=False,
        workflow=_workflow_from_lock(lock_name),
    )
    logger.warning(
        "Reclaimed stale %s from %s; previous holder not running",
        lock_name, previous_owner,
    )
    return acquisition


def acquire_workflow_lock(store: StateStore, workflow: Workflow | str, *,
                          ttl_seconds: float = LOCK_TTL_SECONDS,
                          owner: str | None = None) -> GuardInfo:
    """Acquire a workflow's lock and report this workflow's interrupted runs.

    Raises :class:`WorkflowLocked` (after recording) when the workflow may
    not run. On success, pre-existing unfinished runs of the same workflow
    are reported — one occurrence-counted row each, left unresolved — and
    their ids returned for the log line. Publish state is never touched.
    """
    wid = _workflow_id(workflow)
    name = lock_name_for(workflow)
    me = owner or _make_owner()
    acquisition = try_acquire(store, name, me, ttl_seconds)
    interrupted = _report_interrupted_runs(store, wid)
    return GuardInfo(
        owner=me,
        recovered_stale=bool(acquisition.recovered_stale),
        interrupted_run_ids=tuple(interrupted),
    )


def release_workflow_lock(store: StateStore, workflow: Workflow | str,
                          owner: str) -> bool:
    """Release a lock held by ``owner``. Never raises: a release failure must
    not mask the workflow's own result or exception — the row stays for the
    next invocation's stale recovery, which is exactly what it is for."""
    name = lock_name_for(workflow)
    try:
        released = store.release_lock(name, owner)
    except Exception as exc:  # noqa: BLE001 — see the docstring
        logger.warning(
            "Could not release %s for owner %s: %s; leaving it for stale "
            "recovery", name, owner, exc,
        )
        return False
    if not released:
        logger.warning(
            "Lock %s is no longer held by this invocation; not releasing "
            "another owner's lock", name,
        )
    return released


@contextmanager
def workflow_lock(store: StateStore, workflow: Workflow | str, *,
                  ttl_seconds: float = LOCK_TTL_SECONDS,
                  owner: str | None = None) -> Iterator[GuardInfo]:
    """Acquire a workflow's lock for the duration of the body.

    Raises :class:`WorkflowLocked` before entering when the workflow may not
    run. The lock is released on exit — including on exception — but only
    when this invocation still owns it.
    """
    guard = acquire_workflow_lock(
        store, workflow, ttl_seconds=ttl_seconds, owner=owner
    )
    try:
        yield guard
    finally:
        release_workflow_lock(store, workflow, guard.owner)


def _report_interrupted_runs(store: StateStore, workflow_id: str) -> list[str]:
    """Report unfinished runs of this workflow without resolving them.

    An unfinished run is how an interrupted run is *found*. Reporting leaves
    the run unfinished for forensics: resolving it here — as success or as
    failure — would be inventing an outcome nobody observed. One row per run
    id (occurrence-counted), so repeated ticks do not accumulate rows.
    """
    found: list[str] = []
    for run in store.list_unfinished_runs():
        if run.workflow != workflow_id:
            continue
        try:
            phases = [phase.phase for phase in store.list_phases(run.run_id)]
        except StateStoreError as exc:
            logger.warning(
                "Could not read the phase trail of unfinished run %s: %s",
                run.run_id, exc,
            )
            phases = []
        trail = ", ".join(phases) if phases else "no recorded phases"
        store.record_failure(
            phase=RECOVERY_PHASE,
            error_category="interrupted_run",
            message=(f"workflow {workflow_id} run {run.run_id} never finished "
                     f"(completed phases: {trail}); leaving it untouched and "
                     f"proceeding with a fresh run"),
            retryable=False,
            requires_human_intervention=False,
            workflow=workflow_id,
            dedupe_key=f"interrupted-run:{run.run_id}",
        )
        logger.warning(
            "Previous %s run %s never finished (%s); reported and left "
            "untouched", workflow_id, run.run_id, trail,
        )
        found.append(run.run_id)
    return found


def _record_rejection(store: StateStore, lock_name: str,
                      holder: str | None, message: str) -> None:
    """Record a lock rejection. Occurrence-counted per lock so a long-held
    lock produces one row, not one per tick. The row carries no ``run_id``,
    so it can never leak into a workflow run's notification."""
    store.record_failure(
        phase=LOCK_PHASE,
        error_category="lock_held",
        message=message,
        retryable=True,
        requires_human_intervention=False,
        workflow=_workflow_from_lock(lock_name),
        dedupe_key=f"lock-held:{lock_name}",
    )
    logger.warning("Lock rejection: %s", message)


def _workflow_from_lock(lock_name: str) -> str | None:
    """The workflow id a lock name belongs to, or ``None`` when it says
    nothing usable — a best-effort label for the recorded row, never a
    decision input."""
    prefix = "workflow:"
    if lock_name.startswith(prefix) and len(lock_name) > len(prefix):
        return lock_name[len(prefix):]
    return None


@dataclass(frozen=True)
class ScheduledResult:
    """The outcome of one scheduled-style invocation (Step 12).

    Distinct from the Step 11 ``WorkflowResult``: it describes the
    *invocation* — whether the workflow ran at all — while the workflow's own
    result (when it ran) keeps its outcome, exit code, and notification
    semantics untouched.
    """

    workflow: str
    exit_code: int
    locked: bool = False
    """True when the invocation was rejected without running the workflow."""
    recovered_stale: bool = False
    interrupted_run_ids: tuple[str, ...] = ()
    run_id: str | None = None
    holder: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
