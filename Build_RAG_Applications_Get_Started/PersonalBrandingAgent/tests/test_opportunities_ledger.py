"""M1: tracked work, review cursors, and the coverage ledger.

All state is isolated per test (a temporary store); the production database
is never touched. These tests pin the M1 contract: per-development coverage
independent of projects and of publication history.
"""
import pytest

from app.errors import StateConstraintError
from app.opportunities.baseline import ensure_baseline
from app.state import SCHEMA_VERSION, StateStore


@pytest.fixture
def store(tmp_path):
    with StateStore(tmp_path / "m1.db") as state:
        yield state


def _seed(store, entries):
    return ensure_baseline(store, entries)


def test_schema_is_at_v7_with_the_ledger_tables(store):
    assert SCHEMA_VERSION == 7
    assert store.schema_version == 7
    tables = {
        row[0] for row in store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert {"tracked_work", "review_cursors", "developments"} <= tables


def test_tracked_work_create_and_read(store):
    created = store.ensure_tracked_work(
        "quizey", "Quizey", "A quiz platform.",
        sources=("quizey-v2", "quizey-platform"),
    )

    assert created.work_id == "quizey"
    assert created.sources == ("quizey-v2", "quizey-platform")
    assert created.enabled is True
    assert store.get_tracked_work("quizey") == created
    assert store.get_tracked_work("nope") is None


def test_one_tracked_work_references_multiple_sources(store):
    store.ensure_tracked_work(
        "ai-hackathon", "AI Hackathon",
        sources=("hackathon-lectures", "hackathon-practice-lab"),
    )

    tracked = store.get_tracked_work("ai-hackathon")
    assert tracked is not None
    assert set(tracked.sources) == {
        "hackathon-lectures", "hackathon-practice-lab",
    }


def test_review_cursor_is_independent_of_the_sync_checkpoint(store):
    store.ensure_tracked_work("quizey", "Quizey", sources=("quizey-v2",))
    store.record_sync_success("quizey-v2", "rev-sync-1")

    assert store.get_review_cursor("quizey", "quizey-v2") is None

    cursor = store.set_review_cursor("quizey", "quizey-v2", "rev-sync-1")
    assert cursor.reviewed_revision == "rev-sync-1"

    # A later sync advances the checkpoint but never the cursor.
    store.record_sync_success("quizey-v2", "rev-sync-2")
    assert store.get_checkpoint("quizey-v2").last_revision == "rev-sync-2"
    assert (
        store.get_review_cursor("quizey", "quizey-v2").reviewed_revision
        == "rev-sync-1"
    )

    advanced = store.set_review_cursor("quizey", "quizey-v2", "rev-sync-2")
    assert advanced.reviewed_revision == "rev-sync-2"


def test_review_cursor_for_unknown_work_is_refused(store):
    with pytest.raises(StateConstraintError):
        store.set_review_cursor("ghost", "quizey-v2", "rev-1")


def test_development_covered_independently_of_its_project(store):
    store.ensure_tracked_work("quizey", "Quizey")
    store.ensure_development("quizey", "phase-2", "Phase 2 work")

    assert store.get_development("quizey", "phase-2").covered is False
    covered = store.set_development_covered("quizey", "phase-2", covered=True)
    assert covered.covered is True
    assert covered.covered_at is not None
    assert store.get_tracked_work("quizey").enabled is True


def test_many_developments_under_one_project(store):
    store.ensure_tracked_work("quizey", "Quizey")
    for key in ("phase-2.1", "phase-2.2", "phase-2.3"):
        store.ensure_development("quizey", key, f"Quizey {key}")

    assert len(store.list_developments("quizey")) == 3


def test_covered_and_uncovered_coexist(store):
    store.ensure_tracked_work("quizey", "Quizey")
    store.ensure_development("quizey", "phase-2.1", "Phase 2.1", covered=True)
    store.ensure_development("quizey", "phase-2.2", "Phase 2.2")

    assert [
        (dev.development_key, dev.covered)
        for dev in store.list_developments("quizey")
    ] == [("phase-2.1", True), ("phase-2.2", False)]
    assert [
        dev.development_key
        for dev in store.list_developments("quizey", uncovered_only=True)
    ] == ["phase-2.2"]


def test_baseline_creates_no_publication_records(store):
    _seed(store, [{
        "id": "quizey", "display_name": "Quizey",
        "developments": [{
            "key": "historical-baseline", "covered": True,
            "coverage_kind": "baseline",
        }],
    }])

    assert store._conn.execute(
        "SELECT COUNT(*) FROM publications").fetchone()[0] == 0
    assert store._conn.execute(
        "SELECT COUNT(*) FROM publish_intents").fetchone()[0] == 0
    baseline = store.get_development("quizey", "historical-baseline")
    assert baseline.covered is True
    assert baseline.coverage_kind == "baseline"
    assert baseline.publication_id is None


def test_abu_prompt_introduction_is_an_uncovered_seed(store):
    _seed(store, [{
        "id": "personal-branding-agent", "display_name": "PBA",
        "developments": [
            {"key": "historical-baseline", "covered": True},
            {"key": "abu-prompt-introduction",
             "display_name": "Abu Prompt introduction"},
        ],
    }])

    introduction = store.get_development(
        "personal-branding-agent", "abu-prompt-introduction")
    assert introduction is not None
    assert introduction.covered is False
    assert introduction.publication_id is None


def test_future_project_needs_config_not_code(store, tmp_path):
    config = tmp_path / "future.yaml"
    config.write_text(
        "tracked_work:\n"
        "  - id: quantum-notes\n"
        "    display_name: Quantum Notes\n"
        "    sources: []\n"
        "    developments:\n"
        "      - key: first-notes\n",
        encoding="utf-8",
    )
    from app.opportunities.baseline import load_tracked_work_config

    entries = load_tracked_work_config(config)
    summary = ensure_baseline(store, entries)

    assert summary == {"tracked_work": 1, "developments": 1}
    assert store.get_tracked_work("quantum-notes") is not None


def test_unknown_source_in_config_is_refused(store):
    with pytest.raises(ValueError, match="unknown source"):
        ensure_baseline(store, [{
            "id": "quizey", "display_name": "Quizey",
            "sources": ["quizey-v9-does-not-exist"],
        }])


def test_committed_baseline_seeds_conservatively(store):
    from app.opportunities.baseline import DEFAULT_CONFIG_PATH

    summary = ensure_baseline(store, path=DEFAULT_CONFIG_PATH)

    assert summary["tracked_work"] >= 9
    works = {work.work_id: work for work in store.list_tracked_work()}
    assert set(works) >= {
        "quizey", "personal-branding-agent", "ai-hackathon", "ai-agents",
        "ibm-genai-coursework", "fastapi", "kodekloud-devops",
        "dsa-python", "style-finder",
    }
    # Every seeded development is either a covered baseline or an
    # explicitly uncovered seed — never a claimed publication.
    for work_id in works:
        for development in store.list_developments(work_id):
            assert development.coverage_kind == "baseline"
            assert development.publication_id is None
            if development.covered:
                assert development.covered_at is not None
    assert store.get_development(
        "personal-branding-agent",
        "abu-prompt-introduction").covered is False


def test_design_check_quizey_three_states(store):
    """Covered baseline, uncovered present, unknown future — together."""
    store.ensure_tracked_work("quizey", "Quizey")
    store.ensure_development(
        "quizey", "historical-baseline", "Historical", covered=True)
    store.ensure_development("quizey", "phase-2.2", "Phase 2.2")

    assert store.get_development("quizey", "historical-baseline").covered is True
    assert store.get_development("quizey", "phase-2.2").covered is False
    assert store.get_development("quizey", "phase-2.3") is None
    assert [
        dev.development_key
        for dev in store.list_developments("quizey", uncovered_only=True)
    ] == ["phase-2.2"]


def test_design_check_ai_work_is_separately_trackable(store):
    """One parent directory, independently trackable work."""
    _seed(store, [
        {"id": "ai-hackathon", "display_name": "H",
         "developments": [{"key": "initial-project", "covered": True}]},
        {"id": "ai-agents", "display_name": "A",
         "developments": [{"key": "new-development"}]},
        {"id": "ibm-genai-coursework", "display_name": "I",
         "developments": [{"key": "historical-baseline", "covered": True}]},
    ])

    assert store.get_development(
        "ai-hackathon", "initial-project").covered is True
    assert store.get_development(
        "ai-agents", "new-development").covered is False
    assert [w.work_id for w in store.list_tracked_work()] == [
        "ai-agents", "ai-hackathon", "ibm-genai-coursework",
    ]
