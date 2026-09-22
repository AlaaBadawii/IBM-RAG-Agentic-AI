"""Focused Step 12 tests: overlap protection, stale recovery, and scheduling.

``PLAN.md`` Step 12. Everything runs offline with fakes and isolated
temporary state — no scheduler daemon, no LinkedIn, no SMTP, no ingestion,
no external network calls. Real subprocesses are spawned only to obtain a
provably-dead pid for the liveness probe (never for work).
"""
import os
import socket
import subprocess
import sys
import threading
import time

import pytest

from app.agent.enums import AgentDecision, NoPublishReason
from app.agent.models import AgentResult
from app.notify.enums import NotificationDecision
from app.notify.models import NotificationReport
from app.state import RunOutcome, StateStore
from app.state.enums import PublishState, Workflow
from app.workflows import (
    EXIT_LOCKED,
    EXIT_OK,
    BrandingConfig,
    SyncConfig,
    WorkflowResult,
    run_branding,
    run_sync,
)
from app.workflows.scheduled import (
    LOCK_PHASE,
    RECOVERY_PHASE,
    WorkflowLocked,
    acquire_workflow_lock,
    lock_name_for,
    release_workflow_lock,
    try_acquire,
    workflow_lock,
)


# ------------------------------------------------------------------ fakes ---

class FakeSyncResult:
    def __init__(self):
        self.calls = 0

    def __call__(self, _registry, _store):
        self.calls += 1
        return _CleanSync()


class _CleanSync:
    synced = (object(),)
    unchanged = ()
    failed = ()
    results = ()
    requires_human_intervention = False


class CapturingNotifier:
    def __init__(self, store):
        self.run_calls = []

    def notify_run(self, run_id):
        self.run_calls.append(run_id)
        return NotificationReport(
            decision=NotificationDecision.SENT, message="sent"
        )


def sync_config(path, sync_fn):
    holder = {}

    def fake_notifier(store):
        notifier = CapturingNotifier(store)
        holder["notifier"] = notifier
        return notifier

    return SyncConfig(
        store_factory=lambda: StateStore(path),
        registry_loader=object,
        sync_fn=sync_fn,
        notifier_factory=fake_notifier,
    ), holder


class FakeAgent:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def run(self, _context):
        self.calls += 1
        return self.result


def branding_config(path, agent_result):
    holder = {}
    agent = FakeAgent(agent_result)

    def fake_notifier(store):
        notifier = CapturingNotifier(store)
        holder["notifier"] = notifier
        return notifier

    class EmptyHistory:
        def requires_review(self, limit=None):
            return []

    def no_publish(*_args):
        raise AssertionError("publish must not be called on this path")

    return BrandingConfig(
        store_factory=lambda: StateStore(path),
        assemble_fn=lambda _store: object(),
        agent_factory=lambda _store: agent,
        publish_fn=no_publish,
        history_fn=lambda _store: EmptyHistory(),
        notifier_factory=fake_notifier,
    ), holder, agent


def _dead_pid():
    """A pid that is provably not running: a reaped local child."""
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


def _hold(path, workflow, owner, ttl_seconds=3600.0):
    """Simulate another invocation holding a lock. Returns the owner."""
    with StateStore(path) as store:
        acquired = store.acquire_lock(
            lock_name_for(workflow), owner, ttl_seconds
        )
        assert acquired.acquired
    return owner


def _failures(path, phase=None):
    with StateStore(path) as store:
        rows = store.list_failures(limit=100)
    if phase is not None:
        rows = [row for row in rows if row.phase == phase]
    return rows


# ------------------------------------------------------- overlap protection ---

def test_second_invocation_while_locked_is_rejected(tmp_path):
    path = tmp_path / "sched.db"
    sync_fn = FakeSyncResult()
    live = f"otherhost:{os.getpid()}:live0001"
    _hold(path, Workflow.SYNC, live)
    cfg, _ = sync_config(path, sync_fn)

    with pytest.raises(WorkflowLocked):
        run_sync(cfg)
    # Rejection is sticky: a second attempt is rejected the same way, and the
    # two rejections collapse into one occurrence-counted row.
    with pytest.raises(WorkflowLocked):
        run_sync(cfg)

    assert sync_fn.calls == 0
    with StateStore(path) as store:
        assert store.list_runs() == []
        assert store.get_lock(lock_name_for(Workflow.SYNC)).owner == live
    rejections = _failures(path, LOCK_PHASE)
    assert len(rejections) == 1
    assert rejections[0].error_category == "lock_held"
    assert rejections[0].occurrence_count == 2
    assert rejections[0].run_id is None


def test_lock_rejection_exits_without_running_and_maps_to_exit_locked(
        tmp_path, monkeypatch):
    from app.workflows import sync as sync_module

    locked = WorkflowLocked("workflow:sync", "h:1:t", "already running")

    def raise_locked(*_args, **_kwargs):
        raise locked

    monkeypatch.setattr(sync_module, "run_sync", raise_locked)
    assert sync_module.main([]) == EXIT_LOCKED
    assert EXIT_LOCKED not in (0, 1, 2)


@pytest.mark.parametrize("code,outcome", [
    (0, RunOutcome.DO_NOT_PUBLISH),
    (1, RunOutcome.WORKFLOW_FAILED),
    (2, RunOutcome.REQUIRES_HUMAN_INTERVENTION),
])
def test_command_wrapper_passes_through_workflow_exit_code(
        tmp_path, monkeypatch, code, outcome):
    from app.workflows import branding as branding_module
    from app.workflows import sync as sync_module

    for module, runner in (
        (sync_module, "run_sync"), (branding_module, "run_branding"),
    ):
        canned = WorkflowResult(
            run_id="run_test", workflow="sync", outcome=outcome,
            exit_code=code,
        )
        monkeypatch.setattr(module, runner, lambda *a, **k: canned)
        assert module.main([]) == code


# ------------------------------------------------------------ stale recovery ---

def test_stale_lock_is_recovered_and_recorded(tmp_path):
    path = tmp_path / "sched.db"
    sync_fn = FakeSyncResult()
    old_owner = f"{socket.gethostname()}:{_dead_pid()}:old00001"
    _hold(path, Workflow.SYNC, old_owner, ttl_seconds=0)
    time.sleep(0.02)
    cfg, holder = sync_config(path, sync_fn)

    result = run_sync(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    assert sync_fn.calls == 1
    recoveries = [
        row for row in _failures(path, LOCK_PHASE)
        if row.error_category == "stale_lock_recovered"
    ]
    assert len(recoveries) == 1
    assert old_owner in recoveries[0].message
    assert recoveries[0].run_id is None
    with StateStore(path) as store:
        assert store.get_lock(lock_name_for(Workflow.SYNC)) is None
        phases = [p.phase for p in store.list_phases(result.run_id)]
        assert phases == ["load_registry", "synchronize"]
    assert holder["notifier"].run_calls == []


def test_stale_but_live_lock_is_never_reclaimed(tmp_path):
    path = tmp_path / "sched.db"
    sync_fn = FakeSyncResult()
    live_owner = f"{socket.gethostname()}:{os.getpid()}:live0002"
    _hold(path, Workflow.SYNC, live_owner, ttl_seconds=0)
    time.sleep(0.02)
    cfg, _ = sync_config(path, sync_fn)

    # Expired, but its owner process is this very test process: reclaiming
    # would hand a second live process the lock, so this must refuse.
    with pytest.raises(WorkflowLocked):
        run_sync(cfg)

    assert sync_fn.calls == 0
    with StateStore(path) as store:
        assert store.get_lock(lock_name_for(Workflow.SYNC)).owner == live_owner
        assert store.list_runs() == []


def test_unidentifiable_owner_is_never_reclaimed(tmp_path):
    path = tmp_path / "sched.db"
    sync_fn = FakeSyncResult()
    _hold(path, Workflow.SYNC, "not-our-format", ttl_seconds=0)
    time.sleep(0.02)
    cfg, _ = sync_config(path, sync_fn)

    with pytest.raises(WorkflowLocked):
        run_sync(cfg)

    assert sync_fn.calls == 0
    with StateStore(path) as store:
        assert (store.get_lock(lock_name_for(Workflow.SYNC)).owner
                == "not-our-format")


def test_competing_stale_recoveries_cannot_both_succeed(tmp_path):
    path = tmp_path / "sched.db"
    _hold(path, Workflow.SYNC, f"{socket.gethostname()}:{_dead_pid()}:old",
          ttl_seconds=0)
    time.sleep(0.02)
    barrier = threading.Barrier(2)
    outcomes = []

    def contender(index):
        with StateStore(path) as store:
            barrier.wait(timeout=30)
            try:
                acquisition = try_acquire(
                    store, lock_name_for(Workflow.SYNC),
                    f"racer:{os.getpid()}:{index}",
                )
                outcomes.append(bool(acquisition.acquired))
            except WorkflowLocked:
                outcomes.append(False)

    threads = [threading.Thread(target=contender, args=(i,)) for i in (0, 1)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert sorted(outcomes) == [False, True]


def test_pid_liveness_probe():
    from app.workflows.scheduled import _pid_alive

    assert _pid_alive(os.getpid()) is True
    assert _pid_alive(_dead_pid()) is False


# ---------------------------------------------------------- interrupted runs ---

def test_interrupted_run_is_reported_but_left_untouched(tmp_path):
    path = tmp_path / "sched.db"
    with StateStore(path) as old:
        stale = old.start_run(Workflow.SYNC)
        intent = old.create_publish_intent(
            stale.run_id, "words about work", topic="t"
        )
    sync_fn = FakeSyncResult()
    cfg, _ = sync_config(path, sync_fn)

    first = run_sync(cfg)
    second = run_sync(cfg)

    assert first.outcome is RunOutcome.DO_NOT_PUBLISH
    assert second.outcome is RunOutcome.DO_NOT_PUBLISH
    with StateStore(path) as store:
        # Never resolved: still unfinished, never a false success.
        assert store.get_run(stale.run_id).outcome is None
        # Publish state untouched by recovery: no blind retry of anything.
        assert (store.get_publish_intent(intent.intent_id).state
                is PublishState.INTENT_CREATED)
        unfinished = [r for r in store.list_runs(limit=10)
                      if r.outcome is None]
        finished = [r for r in store.list_runs(limit=10)
                    if r.outcome is not None]
        assert [r.run_id for r in unfinished] == [stale.run_id]
        assert len(finished) == 2
    reports = _failures(path, RECOVERY_PHASE)
    assert len(reports) == 1
    assert stale.run_id in reports[0].message
    assert reports[0].occurrence_count == 2
    assert reports[0].run_id is None


def test_live_holders_unfinished_run_is_not_reported(tmp_path):
    path = tmp_path / "sched.db"
    with StateStore(path) as old:
        live_run = old.start_run(Workflow.SYNC)
    _hold(path, Workflow.SYNC, f"otherhost:{os.getpid()}:live0003")
    sync_fn = FakeSyncResult()
    cfg, _ = sync_config(path, sync_fn)

    with pytest.raises(WorkflowLocked):
        run_sync(cfg)

    assert sync_fn.calls == 0
    assert _failures(path, RECOVERY_PHASE) == []
    with StateStore(path) as store:
        assert store.get_run(live_run.run_id).outcome is None


# ------------------------------------------------------------------ branding ---

def test_branding_runs_guarded_and_releases(tmp_path):
    path = tmp_path / "sched.db"
    cfg, holder, agent = branding_config(
        path,
        AgentResult(decision=AgentDecision.DO_NOT_PUBLISH,
                    reason=NoPublishReason.NO_VALUE),
    )
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    assert result.exit_code == 0
    assert agent.calls == 1
    assert holder["notifier"].run_calls == []
    with StateStore(path) as store:
        assert store.get_lock(lock_name_for(Workflow.BRANDING)) is None
        phases = [p.phase for p in store.list_phases(result.run_id)]
        assert phases == ["context", "decide"]


# ----------------------------------------------------------------- scheduler ---

def test_cron_invokes_both_workflows_without_masking():
    from pathlib import Path

    from app.paths import PROJECT_ROOT

    text = (Path(PROJECT_ROOT) / "ops" / "personal-branding-agent.cron"
            ).read_text()
    assert "app.workflows.sync" in text
    assert "app.workflows.branding" in text
    assert "*/8" in text
    commands = [line for line in text.splitlines()
                if line.strip() and not line.lstrip().startswith("#")
                and "=" not in line.split()[0]]
    assert len(commands) == 2
    for command in commands:
        for forbidden in ("|| true", "; exit 0"):
            assert forbidden not in command


# ----------------------------------------------------------------- milestone ---

def test_milestone_one_run_and_one_rejection(tmp_path):
    path = tmp_path / "sched.db"
    sync_fn = FakeSyncResult()
    _hold(path, Workflow.SYNC, f"otherhost:{os.getpid()}:first0001")
    cfg, holder = sync_config(path, sync_fn)

    with pytest.raises(WorkflowLocked):
        run_sync(cfg)
    with StateStore(path) as store:
        assert store.release_lock(
            lock_name_for(Workflow.SYNC), f"otherhost:{os.getpid()}:first0001")
    result = run_sync(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    assert sync_fn.calls == 1
    with StateStore(path) as store:
        runs = store.list_runs()
        assert len(runs) == 1
        assert runs[0].outcome is RunOutcome.DO_NOT_PUBLISH
        phases = [p.phase for p in store.list_phases(runs[0].run_id)]
        assert phases == ["load_registry", "synchronize"]
        assert store.get_lock(lock_name_for(Workflow.SYNC)) is None
    assert len(_failures(path, LOCK_PHASE)) == 1
    assert holder["notifier"].run_calls == []
