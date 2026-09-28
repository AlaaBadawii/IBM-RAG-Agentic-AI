"""Focused Step 11 tests: the two workflow orchestrations.

``PLAN.md`` Step 11. Every test runs offline with fakes — no real LinkedIn,
no SMTP, no ingestion, no external sync, no real LLM calls. The state store
is real (a temporary file), because persistence of the outcome and of every
phase transition is what is under test.
"""
from dataclasses import dataclass, field

import pytest

from app.agent.enums import (
    AgentDecision,
    AgentFailureCategory,
    NoPublishReason,
)
from app.agent.models import AgentFailure, AgentResult
from app.notify.enums import NotificationDecision
from app.notify.models import NotificationReport
from app.publishing.enums import PublishDecision
from app.state import RunOutcome, StateStore
from app.state.enums import Workflow
from app.verification.errors import VerificationError
from app.workflows import (
    EXIT_OK,
    EXIT_REQUIRES_HUMAN_INTERVENTION,
    EXIT_WORKFLOW_FAILED,
    BrandingConfig,
    SyncConfig,
    run_branding,
    run_sync,
)


# ------------------------------------------------------------------ fakes ---

@dataclass
class FakeSyncResult:
    """Duck-typed stand-in for ``SyncRunResult``: only what the workflow reads."""

    n_synced: int = 1
    n_unchanged: int = 0
    failed_names: tuple[str, ...] = ()
    human_names: tuple[str, ...] = ()

    @property
    def synced(self):
        return (object(),) * self.n_synced

    @property
    def unchanged(self):
        return (object(),) * self.n_unchanged

    @property
    def failed(self):
        return [FakeSource(name) for name in self.failed_names]

    @property
    def results(self):
        out = [FakeSource(name, human=False) for name in self.failed_names]
        out += [FakeSource(name, human=True) for name in self.human_names]
        return out

    @property
    def requires_human_intervention(self):
        return bool(self.human_names)


@dataclass
class FakeSource:
    source_name: str
    human: bool = False

    @property
    def requires_human_intervention(self):
        return self.human


class CapturingNotifier:
    """Fake notification service: records calls, sends nothing."""

    def __init__(self, store):
        self.store = store
        self.run_calls: list[str] = []
        self.publication_calls: list = []
        self.no_publish_calls: list = []

    def notify_run(self, run_id):
        self.run_calls.append(run_id)
        return NotificationReport(
            decision=NotificationDecision.SENT,
            message=f"notified about {run_id}",
        )

    def notify_publication(self, post, *, run_id=None):
        self.publication_calls.append((post, run_id))
        return NotificationReport(
            decision=NotificationDecision.SENT,
            message="reported the publication",
        )

    def notify_no_publish(self, notice, *, run_id=None):
        self.no_publish_calls.append((notice, run_id))
        return NotificationReport(
            decision=NotificationDecision.SENT,
            message=f"reported no publish for {run_id}",
        )


def make_store(tmp_path, name="state.db"):
    return StateStore(tmp_path / name)


def sync_config(tmp_path, *, sync_result=None, registry=None, sync_raises=None,
                registry_raises=None):
    """A sync workflow wired entirely to fakes."""
    holder: dict = {}

    def fake_sync(_registry, _store):
        if sync_raises is not None:
            raise sync_raises
        return sync_result or FakeSyncResult()

    def fake_registry():
        if registry_raises is not None:
            raise registry_raises
        return registry or object()

    def fake_notifier(store):
        notifier = CapturingNotifier(store)
        holder["notifier"] = notifier
        return notifier

    cfg = SyncConfig(
        store_factory=lambda: make_store(tmp_path),
        registry_loader=fake_registry,
        sync_fn=fake_sync,
        notifier_factory=fake_notifier,
    )
    return cfg, holder


@dataclass
class FakePublishReport:
    decision: PublishDecision = PublishDecision.PUBLISHED
    message: str = "published to LinkedIn as post_123"
    post_id: str | None = "post_123"
    human: bool = False

    @property
    def published(self):
        return self.decision is PublishDecision.PUBLISHED

    @property
    def refused(self):
        return self.decision is PublishDecision.REFUSED

    @property
    def requires_review(self):
        return self.decision is PublishDecision.UNKNOWN_REQUIRES_REVIEW

    @property
    def requires_human_intervention(self):
        return self.human or self.requires_review

    @property
    def linkedin_post_id(self):
        return self.post_id


@dataclass
class FakeAgent:
    """Stand-in for ``BrandingAgent``: returns or raises on demand."""

    result: object = None
    error: Exception | None = None
    calls: list = field(default_factory=list)

    def run(self, context):
        self.calls.append(context)
        if self.error is not None:
            raise self.error
        return self.result


def declined_result(reason=NoPublishReason.NO_VALUE):
    return AgentResult(decision=AgentDecision.DO_NOT_PUBLISH, reason=reason)


def failed_result():
    return AgentResult(
        decision=AgentDecision.DO_NOT_PUBLISH,
        reason=NoPublishReason.REASONING_FAILED,
        failure=AgentFailure(
            category=AgentFailureCategory.REASONING_UNAVAILABLE,
            detail="the model could not be reached",
        ),
    )


@dataclass
class PublishableStub:
    """A publishable agent result without building a real verification.

    Only the fields the workflow reads: the decision, the draft text, and
    the proposal labels recorded with the publication.
    """

    text: str = "A grounded post about retrieval."
    topic: str = "retrieval"
    failed: bool = False
    is_publishable: bool = True
    reason: object = None
    attempts_made: int = 0
    draft: object = None
    proposal: object = None

    def __post_init__(self):
        self.draft = FakeDraft(self.text)
        self.proposal = FakeProposal(self.topic)


@dataclass
class FakeDraft:
    content: str


@dataclass
class FakeProposal:
    topic: str
    angle: str | None = None
    project: str | None = None
    evidence: tuple = ()


def branding_config(tmp_path, *, agent_result=None, agent_error=None,
                    context_raises=None, publish_report=None,
                    publish_calls=None, publish_raises=None,
                    pending_review=()):
    """A branding workflow wired entirely to fakes."""
    holder: dict = {}
    agent = FakeAgent(result=agent_result, error=agent_error)

    def fake_assemble(_store):
        if context_raises is not None:
            raise context_raises
        return object()

    def fake_publish(_result, _run_id, _store):
        (publish_calls if publish_calls is not None else []).append(_run_id)
        if publish_raises is not None:
            raise publish_raises
        return publish_report or FakePublishReport()

    class FakeHistory:
        def requires_review(self, limit=None):
            return list(pending_review)

    def fake_notifier(store):
        notifier = CapturingNotifier(store)
        holder["notifier"] = notifier
        return notifier

    cfg = BrandingConfig(
        store_factory=lambda: make_store(tmp_path),
        assemble_fn=fake_assemble,
        agent_factory=lambda _store: agent,
        publish_fn=fake_publish,
        history_fn=lambda _store: FakeHistory(),
        notifier_factory=fake_notifier,
    )
    return cfg, holder, agent


def stored_outcome(tmp_path, run_id):
    """The persisted outcome — never inferred from the exit code."""
    with StateStore(tmp_path / "state.db") as store:
        run = store.get_run(run_id)
        phases = [p.phase for p in store.list_phases(run_id)]
        failures = store.list_failures(run_id=run_id)
    return run, phases, failures


def stored_trail(tmp_path, run_id):
    """Every persisted phase transition as ``(phase, outcome)`` pairs."""
    with StateStore(tmp_path / "state.db") as store:
        return [(p.phase, p.outcome) for p in store.list_phases(run_id)]


def assert_trail_matches_outcome(tmp_path, result):
    """The trail agrees with the terminal outcome: the failed phase's latest
    row is ``failed``; every other row is ``ok``; exactly one run-linked
    failure exists naming that phase."""
    trail = stored_trail(tmp_path, result.run_id)
    run, _, failures = stored_outcome(tmp_path, result.run_id)
    assert run.outcome is result.outcome
    assert run.failed_phase == result.failed_phase
    assert trail[-1] == (result.failed_phase, "failed")
    assert all(outcome == "ok" for _, outcome in trail[:-1])
    assert len(failures) == 1
    assert failures[0].phase == result.failed_phase
    return trail


# ------------------------------------------------------------- sync happy ---

def test_sync_completes_with_fakes(tmp_path):
    cfg, holder = sync_config(tmp_path)
    result = run_sync(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    assert result.exit_code == EXIT_OK == 0
    assert holder["notifier"].run_calls == []
    run, phases, _ = stored_outcome(tmp_path, result.run_id)
    assert run.outcome is RunOutcome.DO_NOT_PUBLISH
    assert phases == ["load_registry", "synchronize"]
    assert result.phases == ("load_registry", "synchronize")
    # Sync scope guard: a clean sync is a quiet success, not a branding
    # no-publish — the DNP helper lives in branding.py and never fires here.
    assert holder["notifier"].no_publish_calls == []


def test_branding_no_opportunity_is_a_success_with_no_notification(tmp_path):
    cfg, holder, _ = branding_config(
        tmp_path, agent_result=declined_result(NoPublishReason.NO_VALUE)
    )
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    assert result.exit_code == EXIT_OK == 0
    assert holder["notifier"].run_calls == []
    assert holder["notifier"].publication_calls == []
    run, phases, _ = stored_outcome(tmp_path, result.run_id)
    assert run.outcome is RunOutcome.DO_NOT_PUBLISH
    assert run.failed_phase is None
    assert phases == ["context", "decide"]
    assert run.no_publish_reason == NoPublishReason.NO_VALUE.value
    assert result.detail.get("no_publish_reason") == (
        NoPublishReason.NO_VALUE.value
    )
    assert len(holder["notifier"].no_publish_calls) == 1


@pytest.mark.parametrize("reason", [
    NoPublishReason.NO_EVIDENCE,
    NoPublishReason.NO_VALUE,
    NoPublishReason.GENERATION_DECLINED,
    NoPublishReason.GATE_REJECTED,
    NoPublishReason.REVISION_EXHAUSTED,
])
def test_single_shot_decline_persists_its_reason_on_the_run(tmp_path, reason):
    """S1: every non-failure decline persists its exact reason on the run row.

    The persisted value must equal the Agent's decision — never inferred
    afterwards. Failure reasons travel the WORKFLOW_FAILED path instead and
    are covered by test_branding_reasoning_failure_is_a_workflow_failure.
    """
    cfg, _, _ = branding_config(tmp_path, agent_result=declined_result(reason))
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    run, _, _ = stored_outcome(tmp_path, result.run_id)
    assert run.no_publish_reason == reason.value
    assert result.detail.get("no_publish_reason") == reason.value


def test_single_shot_decline_sends_exactly_one_no_publish_notification(tmp_path):
    """S1 wiring: one quiet run → one no-publish report, and nothing else."""
    cfg, holder, _ = branding_config(
        tmp_path, agent_result=declined_result(NoPublishReason.GENERATION_DECLINED)
    )
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    assert result.exit_code == EXIT_OK == 0
    assert holder["notifier"].run_calls == []
    assert holder["notifier"].publication_calls == []
    calls = holder["notifier"].no_publish_calls
    assert len(calls) == 1
    notice, run_id = calls[0]
    assert run_id == result.run_id
    assert notice.reason == NoPublishReason.GENERATION_DECLINED.value
    assert not notice.refused


def test_no_publish_notification_failure_leaves_the_run_successful(tmp_path):
    """A dead DNP alerting path must not rewrite the run it was reporting."""

    class ExplodingNotifier(CapturingNotifier):
        def notify_no_publish(self, notice, *, run_id=None):
            raise RuntimeError("SMTP down")

    cfg, _, _ = branding_config(tmp_path, agent_result=declined_result())
    cfg.notifier_factory = lambda store: ExplodingNotifier(store)
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    assert result.exit_code == EXIT_OK == 0
    run, _, _ = stored_outcome(tmp_path, result.run_id)
    assert run.outcome is RunOutcome.DO_NOT_PUBLISH
    assert run.no_publish_reason == NoPublishReason.NO_VALUE.value


# ------------------------------------------------------- failures by phase ---

@pytest.mark.parametrize("phase_raises,phase", [
    ("registry", "load_registry"),
    ("sync", "synchronize"),
])
def test_sync_failure_identifies_its_phase(tmp_path, phase_raises, phase):
    boom = RuntimeError(f"{phase} exploded")
    if phase_raises == "registry":
        cfg, holder = sync_config(tmp_path, registry_raises=boom)
    else:
        cfg, holder = sync_config(tmp_path, sync_raises=boom)
    result = run_sync(cfg)

    assert result.outcome is RunOutcome.WORKFLOW_FAILED
    assert result.exit_code == EXIT_WORKFLOW_FAILED != EXIT_OK
    assert result.failed_phase == phase
    assert holder["notifier"].run_calls == [result.run_id]
    run, phases, failures = stored_outcome(tmp_path, result.run_id)
    assert run.outcome is RunOutcome.WORKFLOW_FAILED
    assert run.failed_phase == phase
    assert phase in phases
    assert any(f.phase == phase for f in failures)


@pytest.mark.parametrize("phase", ["context", "decide", "publish"])
def test_branding_failure_identifies_its_phase(tmp_path, phase):
    if phase == "context":
        cfg, holder, _ = branding_config(
            tmp_path, context_raises=RuntimeError("retrieval is down")
        )
    elif phase == "decide":
        cfg, holder, _ = branding_config(
            tmp_path, agent_error=VerificationError("the gate crashed")
        )
    else:
        cfg, holder, _ = branding_config(
            tmp_path, agent_result=PublishableStub(),
            publish_raises=RuntimeError("transport exploded"),
        )
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.WORKFLOW_FAILED
    assert result.exit_code == EXIT_WORKFLOW_FAILED != EXIT_OK
    assert result.failed_phase == phase
    assert holder["notifier"].run_calls == [result.run_id]
    run, phases, failures = stored_outcome(tmp_path, result.run_id)
    assert run.outcome is RunOutcome.WORKFLOW_FAILED
    assert run.failed_phase == phase
    assert phase in phases
    assert any(f.phase == phase for f in failures)


def test_branding_reasoning_failure_is_a_workflow_failure(tmp_path):
    cfg, holder, _ = branding_config(tmp_path, agent_result=failed_result())
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.WORKFLOW_FAILED
    assert result.failed_phase == "decide"
    assert holder["notifier"].run_calls == [result.run_id]
    run, _, failures = stored_outcome(tmp_path, result.run_id)
    assert run.outcome is RunOutcome.WORKFLOW_FAILED
    assert any(f.phase == "decide" for f in failures)


def test_sync_failed_source_is_a_workflow_failure(tmp_path):
    cfg, holder = sync_config(
        tmp_path, sync_result=FakeSyncResult(failed_names=("quizey",))
    )
    result = run_sync(cfg)

    assert result.outcome is RunOutcome.WORKFLOW_FAILED
    assert result.exit_code == EXIT_WORKFLOW_FAILED
    assert result.failed_phase == "synchronize"
    assert holder["notifier"].run_calls == [result.run_id]
    run, phases, failures = stored_outcome(tmp_path, result.run_id)
    assert run.outcome is RunOutcome.WORKFLOW_FAILED
    assert run.failed_phase == "synchronize"
    assert phases == ["load_registry", "synchronize", "synchronize"]
    assert any(f.phase == "synchronize" for f in failures)


def test_sync_failed_synchronize_is_persisted_as_failed(tmp_path):
    cfg, holder = sync_config(
        tmp_path, sync_result=FakeSyncResult(failed_names=("quizey",))
    )
    result = run_sync(cfg)

    assert result.outcome is RunOutcome.WORKFLOW_FAILED
    trail = assert_trail_matches_outcome(tmp_path, result)
    assert trail == [
        ("load_registry", "ok"),
        ("synchronize", "ok"),
        ("synchronize", "failed"),
    ]
    assert holder["notifier"].run_calls == [result.run_id]


def test_sync_review_signal_persists_synchronize_as_failed(tmp_path):
    cfg, holder = sync_config(
        tmp_path, sync_result=FakeSyncResult(human_names=("ibm-monorepo",))
    )
    result = run_sync(cfg)

    assert result.outcome is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    assert result.exit_code == EXIT_REQUIRES_HUMAN_INTERVENTION
    trail = assert_trail_matches_outcome(tmp_path, result)
    assert trail[-1] == ("synchronize", "failed")
    _, _, failures = stored_outcome(tmp_path, result.run_id)
    assert failures[0].requires_human_intervention
    assert holder["notifier"].run_calls == [result.run_id]


def test_reasoning_failure_persists_decide_as_failed(tmp_path):
    cfg, holder, _ = branding_config(tmp_path, agent_result=failed_result())
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.WORKFLOW_FAILED
    trail = assert_trail_matches_outcome(tmp_path, result)
    assert trail == [
        ("context", "ok"),
        ("decide", "ok"),
        ("decide", "failed"),
    ]
    assert holder["notifier"].run_calls == [result.run_id]


def test_unresolved_guard_persists_publish_as_failed(tmp_path):
    cfg, holder, _ = branding_config(
        tmp_path,
        agent_result=PublishableStub(),
        pending_review=(object(),),
    )
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    assert result.failed_phase == "publish"
    # The guard blocks before the publish phase is entered, so its failed
    # row is the phase's first — and only — trail entry.
    trail = assert_trail_matches_outcome(tmp_path, result)
    assert trail == [
        ("context", "ok"),
        ("decide", "ok"),
        ("publish", "failed"),
    ]
    assert holder["notifier"].run_calls == [result.run_id]


@pytest.mark.parametrize("decision,human", [
    (PublishDecision.UNKNOWN_REQUIRES_REVIEW, True),
    (PublishDecision.FAILED, False),
])
def test_publish_report_outcome_persists_publish_as_failed(
        tmp_path, decision, human):
    cfg, holder, _ = branding_config(
        tmp_path,
        agent_result=PublishableStub(),
        publish_report=FakePublishReport(
            decision=decision,
            post_id=None,
            message="publication did not resolve cleanly",
        ),
    )
    result = run_branding(cfg)

    expected = (RunOutcome.REQUIRES_HUMAN_INTERVENTION if human
                else RunOutcome.WORKFLOW_FAILED)
    assert result.outcome is expected
    trail = assert_trail_matches_outcome(tmp_path, result)
    assert trail[-1] == ("publish", "failed")
    _, _, failures = stored_outcome(tmp_path, result.run_id)
    assert failures[0].requires_human_intervention is human
    assert holder["notifier"].run_calls == [result.run_id]


# ------------------------------------------------- human intervention paths ---

def test_branding_ambiguous_publication_is_human_not_failed(tmp_path):
    calls: list = []
    cfg, holder, _ = branding_config(
        tmp_path,
        agent_result=PublishableStub(),
        publish_report=FakePublishReport(
            decision=PublishDecision.UNKNOWN_REQUIRES_REVIEW,
            post_id=None,
            message="LinkedIn accepted the request but returned no post id",
        ),
        publish_calls=calls,
    )
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    assert result.exit_code == EXIT_REQUIRES_HUMAN_INTERVENTION
    assert result.exit_code != EXIT_WORKFLOW_FAILED
    assert result.failed_phase == "publish"
    # Never automatically retried: exactly one attempt.
    assert calls == [result.run_id]
    assert holder["notifier"].run_calls == [result.run_id]
    run, phases, failures = stored_outcome(tmp_path, result.run_id)
    assert run.outcome is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    assert run.failed_phase == "publish"
    assert "publish" in phases
    assert any(
        f.phase == "publish" and f.requires_human_intervention
        for f in failures
    )


def test_branding_unresolved_earlier_attempt_blocks_publish(tmp_path):
    calls: list = []
    cfg, holder, _ = branding_config(
        tmp_path,
        agent_result=PublishableStub(),
        publish_calls=calls,
        pending_review=(object(),),
    )
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    assert result.exit_code == EXIT_REQUIRES_HUMAN_INTERVENTION
    assert calls == []  # no request left the machine
    assert holder["notifier"].run_calls == [result.run_id]
    run, _, _ = stored_outcome(tmp_path, result.run_id)
    assert run.outcome is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    assert run.failed_phase == "publish"


def test_sync_source_needing_a_person_is_human_not_failed(tmp_path):
    cfg, holder = sync_config(
        tmp_path, sync_result=FakeSyncResult(human_names=("ibm-monorepo",))
    )
    result = run_sync(cfg)

    assert result.outcome is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    assert result.exit_code == EXIT_REQUIRES_HUMAN_INTERVENTION
    assert result.exit_code != EXIT_WORKFLOW_FAILED
    assert holder["notifier"].run_calls == [result.run_id]
    run, _, _ = stored_outcome(tmp_path, result.run_id)
    assert run.outcome is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    assert run.failed_phase == "synchronize"


def test_all_three_outcomes_are_distinct_and_persisted(tmp_path):
    ok_cfg, _ = sync_config(tmp_path, sync_result=FakeSyncResult())
    ok = run_sync(ok_cfg)
    fail_cfg, _ = sync_config(tmp_path, sync_result=FakeSyncResult(
        failed_names=("x",)))
    fail = run_sync(fail_cfg)
    human_cfg, _ = sync_config(tmp_path, sync_result=FakeSyncResult(
        human_names=("y",)))
    human = run_sync(human_cfg)

    assert {ok.outcome, fail.outcome, human.outcome} == {
        RunOutcome.DO_NOT_PUBLISH,
        RunOutcome.WORKFLOW_FAILED,
        RunOutcome.REQUIRES_HUMAN_INTERVENTION,
    }
    assert len({ok.exit_code, fail.exit_code, human.exit_code}) == 3
    for result in (ok, fail, human):
        run, _, _ = stored_outcome(tmp_path, result.run_id)
        assert run.outcome is result.outcome


# ------------------------------------------------------------- publish path ---

def test_branding_publishes_at_most_one_post(tmp_path):
    calls: list = []
    cfg, holder, _ = branding_config(
        tmp_path, agent_result=PublishableStub(), publish_calls=calls
    )
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    assert result.exit_code == EXIT_OK
    assert calls == [result.run_id]
    assert result.detail.get("linkedin_post_id") == "post_123"
    # A published post is reported once as a publication — never as a failure.
    assert holder["notifier"].run_calls == []
    assert len(holder["notifier"].publication_calls) == 1
    # S3: a run that published stays DO_NOT_PUBLISH with a NULL reason —
    # the publication row is the record, not the reason column.
    run, _, _ = stored_outcome(tmp_path, result.run_id)
    assert run.no_publish_reason is None
    # A published run reports the post — and nothing else.
    assert holder["notifier"].no_publish_calls == []


def test_branding_duplicate_refusal_is_a_quiet_success(tmp_path):
    cfg, holder, _ = branding_config(
        tmp_path,
        agent_result=PublishableStub(),
        publish_report=FakePublishReport(
            decision=PublishDecision.REFUSED,
            post_id=None,
            message="exact_duplicate: this text already went out",
        ),
    )
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.DO_NOT_PUBLISH
    assert result.exit_code == EXIT_OK
    assert holder["notifier"].run_calls == []
    assert holder["notifier"].publication_calls == []
    # S2 (pinned): a duplicate refusal keeps the reason column NULL — there
    # is no closed-vocabulary NoPublishReason for a refused verified draft —
    # while detail carries the refusal flag and message.
    run, _, _ = stored_outcome(tmp_path, result.run_id)
    assert run.no_publish_reason is None
    assert result.detail.get("refused") is True
    assert result.detail.get("refusal") == (
        "exact_duplicate: this text already went out"
    )
    # The refusal is still reported — once, with the refusal message and no
    # invented reason.
    calls = holder["notifier"].no_publish_calls
    assert len(calls) == 1
    notice, run_id = calls[0]
    assert run_id == result.run_id
    assert notice.reason is None
    assert notice.refused is True
    assert notice.refusal == "exact_duplicate: this text already went out"


def test_branding_failed_publication_is_a_workflow_failure(tmp_path):
    cfg, holder, _ = branding_config(
        tmp_path,
        agent_result=PublishableStub(),
        publish_report=FakePublishReport(
            decision=PublishDecision.FAILED,
            post_id=None,
            message="LinkedIn refused the request",
        ),
    )
    result = run_branding(cfg)

    assert result.outcome is RunOutcome.WORKFLOW_FAILED
    assert result.failed_phase == "publish"
    assert holder["notifier"].run_calls == [result.run_id]
    # Failure regression: the failure email goes out exactly as before, and
    # no quiet-run report is added on top of it.
    assert holder["notifier"].no_publish_calls == []


# ------------------------------------------------------------- boundaries ---

def _module_source(module_name):
    import importlib
    from pathlib import Path

    module = importlib.import_module(module_name)
    return Path(module.__file__).read_text()


def test_sync_never_publishes_and_never_reasons():
    source = _module_source("app.workflows.sync")
    for forbidden in (
        "app.publishing", "app.agent", "app.generation", "app.verification",
        "publish_to_linkedin", "BrandingAgent", "PostGenerator",
        "EvidenceVerifier", "PublishingService",
    ):
        assert forbidden not in source, f"sync workflow reaches {forbidden}"


def test_branding_never_ingests_or_syncs():
    source = _module_source("app.workflows.branding")
    for forbidden in (
        "app.sync", "app.ingestion", "app.sources", "sync_all", "sync_source",
        "run_ingestion", "SyncContext",
    ):
        assert forbidden not in source, f"branding workflow reaches {forbidden}"


def test_agent_never_decides_notification():
    import app.agent as agent_package
    from pathlib import Path

    package_dir = Path(agent_package.__file__).parent
    for module in package_dir.glob("*.py"):
        text = module.read_text()
        assert "app.notify" not in text, f"{module.name} reaches notify"
        assert "notify_run" not in text, f"{module.name} notifies"
    # Behaviourally: the workflow notifies on a reasoning failure the Agent
    # merely exposed — the Agent itself sends nothing.


# ------------------------------------------------------------- entry points ---

def test_sync_entry_point_maps_outcome_to_exit_code(tmp_path, monkeypatch):
    from app.workflows import sync as sync_module

    cfg, _ = sync_config(tmp_path, sync_result=FakeSyncResult())
    monkeypatch.setattr(sync_module, "run_sync", lambda *a, **k: run_sync(cfg))
    assert sync_module.main([]) == EXIT_OK


def test_branding_entry_point_maps_outcome_to_exit_code(tmp_path, monkeypatch):
    from app.workflows import branding as branding_module

    cfg, _, _ = branding_config(tmp_path, agent_result=declined_result())
    monkeypatch.setattr(
        branding_module, "run_branding", lambda *a, **k: run_branding(cfg)
    )
    assert branding_module.main([]) == EXIT_OK


def test_entry_points_are_independently_invocable(tmp_path, monkeypatch):
    """Each module runs without the other being imported or configured."""
    import sys

    from app.workflows import branding as branding_module
    from app.workflows import sync as sync_module

    sync_cfg, _ = sync_config(tmp_path, sync_result=FakeSyncResult())
    branding_cfg, _, _ = branding_config(
        tmp_path, agent_result=declined_result()
    )
    monkeypatch.setattr(
        sync_module, "run_sync", lambda *a, **k: run_sync(sync_cfg))
    monkeypatch.setattr(
        branding_module, "run_branding",
        lambda *a, **k: run_branding(branding_cfg),
    )
    monkeypatch.delitem(sys.modules, "app.workflows.branding", raising=False)
    assert sync_module.main([]) == EXIT_OK
    monkeypatch.delitem(sys.modules, "app.workflows.sync", raising=False)
    assert branding_module.main([]) == EXIT_OK


# --------------------------------------------------------------- milestone ---

def test_milestone_sync_then_branding_back_to_back(tmp_path):
    """Both workflows run back-to-back on one store with deterministic fakes."""
    sync_cfg, sync_holder = sync_config(tmp_path, sync_result=FakeSyncResult())
    branding_cfg, branding_holder, _ = branding_config(
        tmp_path, agent_result=declined_result(NoPublishReason.NO_EVIDENCE)
    )

    first_sync = run_sync(sync_cfg)
    first_branding = run_branding(branding_cfg)
    second_sync = run_sync(sync_cfg)
    second_branding = run_branding(branding_cfg)

    for result in (first_sync, second_sync, first_branding, second_branding):
        assert result.outcome is RunOutcome.DO_NOT_PUBLISH
        assert result.exit_code == EXIT_OK
    assert (first_sync.outcome, first_branding.outcome) == (
        second_sync.outcome, second_branding.outcome)
    assert sync_holder["notifier"].run_calls == []
    assert branding_holder["notifier"].run_calls == []

    with StateStore(tmp_path / "state.db") as store:
        runs = store.list_runs(limit=10)
        assert len(runs) == 4
        workflows = sorted(r.workflow for r in runs)
        assert workflows == ["branding", "branding", "sync", "sync"]
        for run in runs:
            assert run.outcome is RunOutcome.DO_NOT_PUBLISH
            phase_names = [p.phase for p in store.list_phases(run.run_id)]
            if run.workflow == Workflow.SYNC.value:
                assert phase_names == ["load_registry", "synchronize"]
            else:
                assert phase_names == ["context", "decide"]
