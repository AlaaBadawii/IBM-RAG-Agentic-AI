"""The weekly publishing cadence check.

Two runs a week, one post per run, two posts a week. After each run the
workflow asks whether the week can still reach the target; if no scheduled run
remains to make up a shortfall it records the miss and notifies a person. These
tests drive the pure status computation and the enforcement entry point against
a temporary store — no network, no scheduler, no live state.
"""
import pytest

from app.state import PublishState, StateStore, Workflow
from app.state.models import utc_now
from app.workflows.branding import (
    BrandingConfig,
    _enforce_weekly_target,
    _week_start,
    _weekly_target_status,
)


def _store(tmp_path):
    return StateStore(tmp_path / "weekly.db")


def _publish_one(store, content):
    """One published post in its own run (one intent per run)."""
    run = store.start_run(Workflow.BRANDING)
    intent = store.create_publish_intent(run.run_id, content)
    store.mark_attempt_started(intent.intent_id)
    store.record_publication(
        intent.intent_id, PublishState.PUBLISHED,
        linkedin_post_id=f"urn:li:share:{content}")
    return run


def _start_run(store):
    return store.start_run(Workflow.BRANDING)


class RecordingNotifier:
    def __init__(self):
        self.failures = []

    def notify_failure(self, failure):
        self.failures.append(failure)


def test_week_start_is_monday_midnight_utc():
    start = _week_start(utc_now())
    assert start.weekday() == 0
    assert (start.hour, start.minute, start.second) == (0, 0, 0)


def test_status_is_met_when_the_target_is_reached(tmp_path):
    with _store(tmp_path) as store:
        _publish_one(store, "first")
        _publish_one(store, "second")
        status = _weekly_target_status(store, target=2, runs_per_week=2)
    assert status.published == 2
    assert status.runs_this_week == 2
    assert status.remaining_runs == 0
    assert status.in_jeopardy is False


def test_status_is_not_yet_jeopardy_while_a_run_remains(tmp_path):
    with _store(tmp_path) as store:
        _publish_one(store, "only-one")
        status = _weekly_target_status(store, target=2, runs_per_week=2)
    assert status.published == 1
    assert status.remaining_runs == 1
    # 1 recorded + 1 run still to come can still reach 2.
    assert status.in_jeopardy is False


def test_status_is_jeopardy_when_no_run_remains(tmp_path):
    with _store(tmp_path) as store:
        _start_run(store)
        _start_run(store)
        status = _weekly_target_status(store, target=2, runs_per_week=2)
    assert status.published == 0
    assert status.remaining_runs == 0
    assert status.in_jeopardy is True


def test_enforce_records_and_notifies_a_miss(tmp_path):
    notifier = RecordingNotifier()
    with _store(tmp_path) as store:
        run = _start_run(store)
        _start_run(store)
        cfg = BrandingConfig(weekly_target=2, branding_runs_per_week=2)
        _enforce_weekly_target(cfg, store, notifier, run.run_id)
        failures = store.list_failures()

    assert len(failures) == 1
    assert failures[0].error_category == "weekly_target_jeopardy"
    assert failures[0].requires_human_intervention is True
    assert len(notifier.failures) == 1
    assert notifier.failures[0].failure_id == failures[0].failure_id


def test_enforce_deduplicates_within_the_week(tmp_path):
    notifier = RecordingNotifier()
    with _store(tmp_path) as store:
        run = _start_run(store)
        _start_run(store)
        cfg = BrandingConfig(weekly_target=2, branding_runs_per_week=2)
        _enforce_weekly_target(cfg, store, notifier, run.run_id)
        _enforce_weekly_target(cfg, store, notifier, run.run_id)
        failures = store.list_failures()

    # One row per week, its occurrence count incremented — not a row per run.
    assert len(failures) == 1
    assert failures[0].occurrence_count == 2


def test_enforce_is_silent_when_the_target_is_met(tmp_path):
    notifier = RecordingNotifier()
    with _store(tmp_path) as store:
        _publish_one(store, "first")
        run = _publish_one(store, "second")
        cfg = BrandingConfig(weekly_target=2, branding_runs_per_week=2)
        _enforce_weekly_target(cfg, store, notifier, run.run_id)
        failures = store.list_failures()

    assert failures == []
    assert notifier.failures == []


def test_enforce_is_disabled_when_the_target_is_zero(tmp_path):
    notifier = RecordingNotifier()
    with _store(tmp_path) as store:
        run = _start_run(store)
        _start_run(store)
        cfg = BrandingConfig(weekly_target=0, branding_runs_per_week=2)
        _enforce_weekly_target(cfg, store, notifier, run.run_id)
        failures = store.list_failures()

    assert failures == []
    assert notifier.failures == []


@pytest.mark.parametrize("target,runs_per_week", [(2, 2)])
def test_bare_config_disables_the_check(tmp_path, target, runs_per_week):
    """A default ``BrandingConfig`` never emits a cadence notification."""
    notifier = RecordingNotifier()
    with _store(tmp_path) as store:
        run = _start_run(store)
        _enforce_weekly_target(BrandingConfig(), store, notifier, run.run_id)
        assert store.list_failures() == []
    assert notifier.failures == []
