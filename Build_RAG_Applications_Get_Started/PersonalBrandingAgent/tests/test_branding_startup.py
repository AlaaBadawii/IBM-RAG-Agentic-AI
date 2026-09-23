"""Startup regression tests: default workflow configuration must construct.

Covers the entry-point failure where ``BrandingConfig()`` (and identically
``SyncConfig()``) raised ``TypeError`` because the ``notifier_factory``
field used a one-argument lambda as a zero-argument dataclass
``default_factory``. All tests run offline with fakes and temporary state —
no LinkedIn, no SMTP, no network.
"""
import subprocess
import sys

import pytest

from app.notify.service import NotificationService
from app.state import StateStore
from app.workflows import (
    EXIT_LOCKED,
    EXIT_OK,
    BrandingConfig,
    SyncConfig,
    run_branding,
    run_sync,
)
from app.workflows.branding import (
    _default_agent,
    _default_assemble,
    _default_history,
    _default_notifier,
    _default_publish,
)
from app.workflows.scheduled import WorkflowLocked
from app.workflows.sync import (
    _default_notifier as _sync_default_notifier,
)
from app.workflows.sync import (
    _default_registry_loader,
    _default_sync,
)
from tests.conftest import PROJECT_ROOT


def test_branding_config_constructs_with_normal_defaults(tmp_path):
    """The reported bug: this raised TypeError before the fix."""
    cfg = BrandingConfig()

    assert cfg.assemble_fn is _default_assemble
    assert cfg.agent_factory is _default_agent
    assert cfg.publish_fn is _default_publish
    assert cfg.history_fn is _default_history
    assert cfg.notifier_factory is _default_notifier
    with StateStore(tmp_path / "state.db") as store:
        assert isinstance(cfg.notifier_factory(store), NotificationService)


def test_sync_config_constructs_with_normal_defaults(tmp_path):
    """The identical defect on the sync entry point."""
    cfg = SyncConfig()

    assert cfg.registry_loader is _default_registry_loader
    assert cfg.sync_fn is _default_sync
    assert cfg.notifier_factory is _sync_default_notifier
    with StateStore(tmp_path / "state.db") as store:
        assert isinstance(cfg.notifier_factory(store), NotificationService)


def _declining_agent():
    from app.agent.enums import AgentDecision, NoPublishReason
    from app.agent.models import AgentResult

    class Agent:
        def __init__(self):
            self.calls = 0

        def run(self, _context):
            self.calls += 1
            return AgentResult(decision=AgentDecision.DO_NOT_PUBLISH,
                               reason=NoPublishReason.NO_VALUE)

    return Agent()


def _quiet_notifier(holder):
    from app.notify.enums import NotificationDecision
    from app.notify.models import NotificationReport

    class Notifier:
        def notify_run(self, run_id):
            holder.append(run_id)
            return NotificationReport(decision=NotificationDecision.SENT,
                                      message="sent")

    return Notifier()


def test_run_branding_starts_through_default_configuration_path(tmp_path):
    """Default-constructed config + temp store runs to a recorded outcome."""
    notified = []
    agent = _declining_agent()
    cfg = BrandingConfig()
    cfg.store_factory = lambda: StateStore(tmp_path / "state.db")
    cfg.assemble_fn = lambda _store: object()
    cfg.agent_factory = lambda _store: agent
    cfg.publish_fn = lambda *_args: (_ for _ in ()).throw(
        AssertionError("must not publish on a decline"))
    cfg.notifier_factory = lambda _store: _quiet_notifier(notified)

    result = run_branding(cfg)

    from app.state import RunOutcome
    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    assert result.exit_code == EXIT_OK
    assert agent.calls == 1
    assert notified == []
    with StateStore(tmp_path / "state.db") as store:
        assert store.get_run(result.run_id).outcome is result.outcome


def test_run_sync_starts_through_default_configuration_path(tmp_path):
    from app.state import RunOutcome

    class CleanSync:
        synced = (object(),)
        unchanged = ()
        failed = ()
        results = ()
        requires_human_intervention = False

    calls = []
    cfg = SyncConfig()
    cfg.store_factory = lambda: StateStore(tmp_path / "state.db")
    cfg.registry_loader = object

    def sync_fn(_registry, _store):
        calls.append(True)
        return CleanSync()

    cfg.sync_fn = sync_fn
    cfg.notifier_factory = lambda _store: _quiet_notifier([])

    result = run_sync(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    assert result.exit_code == EXIT_OK
    assert calls == [True]


def test_explicitly_injected_seams_still_win(tmp_path):
    """Dependency injection is preserved: explicit fakes are used as given."""
    from app.state import RunOutcome

    sentinel = object()
    seen = []
    notified = []
    agent = _declining_agent()
    cfg = BrandingConfig(
        store_factory=lambda: StateStore(tmp_path / "state.db"),
        assemble_fn=lambda _store: sentinel,
        agent_factory=lambda _store: agent,
        publish_fn=lambda *_args: None,
        history_fn=lambda _store: None,
        notifier_factory=lambda _store: _quiet_notifier(notified),
    )

    received = {}

    original_run = agent.run

    def spy_run(context):
        received["context"] = context
        return original_run(context)

    agent.run = spy_run
    result = run_branding(cfg)

    assert received["context"] is sentinel
    assert result.outcome is RunOutcome.DO_NOT_PUBLISH


def test_module_entry_point_imports_without_warning_or_double_execution():
    """Reproduces the `python -m` import sequence with warnings as errors.

    Before the fix, `import app.workflows` eagerly executed the submodule,
    so runpy re-executed it as `__main__` with a RuntimeWarning. The
    workflow itself is never executed here (that would touch real state).
    """
    code = (
        "import sys;"
        "import app.workflows;"
        "assert 'app.workflows.branding' not in sys.modules;"
        "assert 'app.workflows.sync' not in sys.modules;"
        "import app.workflows.branding as branding;"
        "import app.workflows.sync as sync;"
        "assert callable(branding.main) and callable(branding.run_branding);"
        "assert callable(sync.main) and callable(sync.run_sync);"
        "from app.workflows import run_sync, run_branding, EXIT_LOCKED;"
        "assert EXIT_LOCKED == 3"
    )
    subprocess.run(
        [sys.executable, "-W", "error::RuntimeWarning", "-c", code],
        check=True, cwd=str(PROJECT_ROOT), capture_output=True, text=True,
    )


def test_locked_entry_point_still_maps_to_exit_locked(tmp_path, monkeypatch):
    from app.workflows import branding as branding_module

    def raise_locked(*_args, **_kwargs):
        raise WorkflowLocked("workflow:branding", "h:1:t", "held")

    monkeypatch.setattr(branding_module, "run_branding", raise_locked)
    assert branding_module.main([]) == EXIT_LOCKED


@pytest.mark.parametrize("factory", [BrandingConfig, SyncConfig])
def test_default_store_factory_is_the_real_store(factory):
    """Defaults still point at the real layers, not at test doubles."""
    assert factory().store_factory is StateStore
