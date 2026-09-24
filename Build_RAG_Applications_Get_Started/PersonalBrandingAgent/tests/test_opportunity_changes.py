"""M2: change detection against branding review cursors.

All repositories and stores are temporary; production state is never
touched. These tests pin detection and classification behavior, never
implementation details: what changed, what kind it is, and what the
detector refuses to claim.
"""
import pytest

from app.opportunities.changes import (
    ChangeClassification,
    detect_changes,
)
from app.sources.enums import SourceType
from app.sources.models import Registry
from app.state import StateStore
from app.sync.enums import ChangeType


@pytest.fixture
def store(tmp_path):
    with StateStore(tmp_path / "m2.db") as state:
        yield state


def _registry(tmp_path, *sources):
    return Registry(sources=tuple(sources), path=tmp_path)


def _commit(repo, *files, message="change"):
    for relative, text in files:
        repo.write(relative, text)
    return repo.commit(message)


def _single(changeset):
    assert len(changeset.changes) == 1
    return changeset.changes[0]


def test_unchanged_revision_is_no_change(store, tmp_path, make_git_repo,
                                         make_source):
    repo = make_git_repo("stampless")
    _commit(repo, ("notes.md", "# notes\n"))
    head = repo.head()
    src = make_source(repo.path, name="stampless")
    store.ensure_tracked_work("w", "W", sources=("stampless",))
    store.set_review_cursor("w", "stampless", head)

    change = _single(detect_changes(
        store, "w", registry=_registry(tmp_path, src)))

    assert change.classification is ChangeClassification.NO_CHANGE
    assert change.paths == ()
    assert change.before_revision == change.after_revision == head


def test_added_file_is_detected(store, tmp_path, make_git_repo, make_source):
    repo = make_git_repo("added")
    _commit(repo, ("README.md", "# base\n"))
    base = repo.head()
    _commit(repo, ("feature.py", "VALUE = 1\n" * 20))
    src = make_source(repo.path, name="added")
    store.ensure_tracked_work("w", "W", sources=("added",))
    store.set_review_cursor("w", "added", base)

    change = _single(detect_changes(store, "w", registry=_registry(tmp_path, src)))

    assert change.classification is ChangeClassification.MEANINGFUL_CHANGE
    assert [(p.path, p.change_type) for p in change.paths] == [
        ("feature.py", ChangeType.ADDED)]


def test_modified_file_is_detected(store, tmp_path, make_git_repo,
                                   make_source):
    repo = make_git_repo("modified")
    _commit(repo, ("app.py", "A = 1\n" * 30))
    base = repo.head()
    _commit(repo, ("app.py", "A = 2\n" * 30))
    src = make_source(repo.path, name="modified")
    store.ensure_tracked_work("w", "W", sources=("modified",))
    store.set_review_cursor("w", "modified", base)

    change = _single(detect_changes(store, "w", registry=_registry(tmp_path, src)))

    assert change.classification is ChangeClassification.MEANINGFUL_CHANGE
    assert [p.change_type for p in change.paths] == [ChangeType.MODIFIED]


def test_deleted_file_is_detected_as_removal_only(
        store, tmp_path, make_git_repo, make_source):
    repo = make_git_repo("deleted")
    _commit(repo, ("old.py", "X = 1\n"), ("keep.py", "Y = 2\n"))
    base = repo.head()
    (repo.path / "old.py").unlink()
    repo.commit("remove")
    src = make_source(repo.path, name="deleted")
    store.ensure_tracked_work("w", "W", sources=("deleted",))
    store.set_review_cursor("w", "deleted", base)

    change = _single(detect_changes(store, "w", registry=_registry(tmp_path, src)))

    assert [(p.path, p.change_type) for p in change.paths] == [
        ("old.py", ChangeType.DELETED)]
    assert change.classification is ChangeClassification.MINOR_CHANGE


def test_renamed_file_is_detected_as_rename(
        store, tmp_path, make_git_repo, make_source):
    repo = make_git_repo("renamed")
    _commit(repo, ("before.py", "SAME = 1\n" * 30))
    base = repo.head()
    repo.move("before.py", "after.py")
    repo.commit("rename")
    src = make_source(repo.path, name="renamed")
    store.ensure_tracked_work("w", "W", sources=("renamed",))
    store.set_review_cursor("w", "renamed", base)

    change = _single(detect_changes(store, "w", registry=_registry(tmp_path, src)))

    assert [(p.path, p.change_type) for p in change.paths] == [
        ("after.py", ChangeType.RENAMED)]
    assert change.paths[0].previous_path == "before.py"
    assert change.classification is ChangeClassification.MINOR_CHANGE


def test_multiple_changes_are_all_preserved(
        store, tmp_path, make_git_repo, make_source):
    repo = make_git_repo("multi")
    _commit(repo, ("a.py", "A = 1\n" * 5), ("b.py", "B = 1\n" * 5),
            ("c.py", "C = 1\n" * 5))
    base = repo.head()
    _commit(repo, ("a.py", "A = 2\n" * 5), ("d.py", "D = 1\n" * 5))
    (repo.path / "c.py").unlink()
    repo.commit("mixed")
    src = make_source(repo.path, name="multi")
    store.ensure_tracked_work("w", "W", sources=("multi",))
    store.set_review_cursor("w", "multi", base)

    kinds = {(p.path, p.change_type) for p in _single(
        detect_changes(store, "w", registry=_registry(tmp_path, src))).paths}

    assert kinds == {
        ("a.py", ChangeType.MODIFIED), ("d.py", ChangeType.ADDED),
        ("c.py", ChangeType.DELETED),
    }


def test_same_range_has_stable_identity(store, tmp_path, make_git_repo,
                                        make_source):
    repo = make_git_repo("stable")
    _commit(repo, ("a.py", "A = 1\n" * 5))
    base = repo.head()
    _commit(repo, ("a.py", "A = 2\n" * 5))
    src = make_source(repo.path, name="stable")
    store.ensure_tracked_work("w", "W", sources=("stable",))
    store.set_review_cursor("w", "stable", base)
    registry = _registry(tmp_path, src)

    first = _single(detect_changes(store, "w", registry=registry))
    second = _single(detect_changes(store, "w", registry=registry))

    assert first.change_id == second.change_id
    assert first.classification == second.classification
    assert first.paths == second.paths


def test_sync_advance_does_not_move_detection_basis(
        store, tmp_path, make_git_repo, make_source):
    repo = make_git_repo("basis")
    _commit(repo, ("a.py", "A = 1\n" * 5))
    rev_a = repo.head()
    _commit(repo, ("b.py", "B = 1\n" * 5))
    rev_b = repo.head()
    src = make_source(repo.path, name="basis")
    store.ensure_tracked_work("w", "W", sources=("basis",))
    store.set_review_cursor("w", "basis", rev_a)
    store.record_sync_success("basis", rev_b)

    change = _single(detect_changes(store, "w", registry=_registry(tmp_path, src)))

    assert change.before_revision == rev_a
    assert change.after_revision == rev_b
    assert [p.path for p in change.paths] == ["b.py"]
    assert store.get_review_cursor("w", "basis").reviewed_revision == rev_a


def test_detection_leaves_the_cursor_alone(store, tmp_path, make_git_repo,
                                           make_source):
    repo = make_git_repo("untouched")
    _commit(repo, ("a.py", "A = 1\n" * 5))
    src = make_source(repo.path, name="untouched")
    store.ensure_tracked_work("w", "W", sources=("untouched",))

    change = _single(detect_changes(store, "w", registry=_registry(tmp_path, src)))

    assert change.unreviewed is True
    assert change.classification is ChangeClassification.NO_CHANGE
    assert store.get_review_cursor("w", "untouched") is None

    # The explicitly named review operation is what advances it.
    head = repo.head()
    store.set_review_cursor("w", "untouched", head)
    again = _single(detect_changes(store, "w", registry=_registry(tmp_path, src)))
    assert again.unreviewed is False
    assert again.classification is ChangeClassification.NO_CHANGE


def test_trivial_edit_is_minor(store, tmp_path, make_git_repo, make_source):
    repo = make_git_repo("typo")
    _commit(repo, ("README.md", "# Title\n\nSome body text here.\n"))
    base = repo.head()
    _commit(repo, ("README.md", "# Title\n\nSome body text here!\n"))
    src = make_source(repo.path, name="typo")
    store.ensure_tracked_work("w", "W", sources=("typo",))
    store.set_review_cursor("w", "typo", base)

    change = _single(detect_changes(store, "w", registry=_registry(tmp_path, src)))

    assert change.classification is ChangeClassification.MINOR_CHANGE


def test_new_top_level_directory_is_a_milestone(
        store, tmp_path, make_git_repo, make_source):
    repo = make_git_repo("newproj")
    _commit(repo, ("README.md", "# base\n"))
    base = repo.head()
    _commit(repo, ("newservice/app.py", "APP = 1\n" * 20))
    src = make_source(repo.path, name="newproj")
    store.ensure_tracked_work("w", "W", sources=("newproj",))
    store.set_review_cursor("w", "newproj", base)

    change = _single(detect_changes(store, "w", registry=_registry(tmp_path, src)))

    assert change.classification is ChangeClassification.MILESTONE


def test_quizey_phase_style_change_is_meaningful(
        store, tmp_path, make_git_repo, make_source):
    """Phase-2.2-style work: focused new files inside a large repository.

    Thirty pre-existing files must not make the verdict, and must not hide
    the two files that are the actual change.
    """
    repo = make_git_repo("quizey")
    baseline = [("README.md", "# Quizey\n")]
    baseline += [(f"app/legacy_{n}.py", f"LEGACY_{n} = 1\n")
                 for n in range(30)]
    _commit(repo, *baseline)
    base = repo.head()
    _commit(repo,
            ("app/versioning.py", "STRATEGY = 'copy-on-write'\n" * 15),
            ("app/tests/test_versioning.py", "def test_copy():\n    pass\n" * 10),
            message="phase 2.2 version management")
    src = make_source(repo.path, name="quizey-v2")
    store.ensure_tracked_work("quizey", "Quizey", sources=("quizey-v2",))
    store.set_review_cursor("quizey", "quizey-v2", base)

    change = _single(detect_changes(
        store, "quizey", registry=_registry(tmp_path, src)))

    assert change.classification is ChangeClassification.MEANINGFUL_CHANGE
    assert sorted(p.path for p in change.paths) == [
        "app/tests/test_versioning.py", "app/versioning.py"]


def test_baseline_existence_is_not_a_change(store, tmp_path):
    from app.opportunities.baseline import ensure_baseline

    ensure_baseline(store, [{
        "id": "quizey", "display_name": "Quizey",
        "developments": [
            {"key": "historical-baseline", "covered": True},
            {"key": "phase-2.2"},
        ],
    }])

    assert store.get_development(
        "quizey", "historical-baseline").covered is True
    # Coverage rows are ledger state, not change evidence: without a cursor
    # there is nothing to compare, not an opportunity.
    assert store.get_review_cursor("quizey", "quizey-v2") is None


def test_small_project_detected_independently_of_big_neighbor(
        store, tmp_path, make_git_repo, make_source):
    big = make_git_repo("big")
    _commit(big, *[(
        f"mod_{n}.py", f"V_{n} = 1\n") for n in range(60)])
    big_base = big.head()
    small = make_git_repo("small")
    _commit(small, ("a.py", "A = 1\n"), ("b.py", "B = 1\n"))
    small_base = small.head()
    _commit(small, ("c.py", "C = 1\n" * 25))
    big_src = make_source(big.path, name="big")
    small_src = make_source(small.path, name="small")
    registry = _registry(tmp_path, big_src, small_src)
    store.ensure_tracked_work("big-work", "Big", sources=("big",))
    store.ensure_tracked_work("small-work", "Small", sources=("small",))
    store.set_review_cursor("big-work", "big", big_base)
    store.set_review_cursor("small-work", "small", small_base)

    big_change = _single(detect_changes(store, "big-work", registry=registry))
    small_change = _single(
        detect_changes(store, "small-work", registry=registry))

    assert big_change.classification is ChangeClassification.NO_CHANGE
    assert small_change.classification is ChangeClassification.MEANINGFUL_CHANGE
    assert [p.path for p in small_change.paths] == ["c.py"]


def test_llms_subprojects_stay_independent(
        store, tmp_path, make_git_repo, make_source):
    hack = make_git_repo("hack")
    _commit(hack, ("lab.py", "LAB = 1\n"))
    hack_base = hack.head()
    agents = make_git_repo("agents")
    _commit(agents, ("exp.py", "EXP = 1\n"))
    agents_base = agents.head()
    _commit(agents, ("exp2.py", "EXP2 = 1\n" * 20))
    hack_src = make_source(hack.path, name="hackathon-lab")
    agents_src = make_source(agents.path, name="ai-agents")
    registry = _registry(tmp_path, hack_src, agents_src)
    store.ensure_tracked_work("ai-hackathon", "H", sources=("hackathon-lab",))
    store.ensure_tracked_work("ai-agents", "A", sources=("ai-agents",))
    store.set_review_cursor("ai-hackathon", "hackathon-lab", hack_base)
    store.set_review_cursor("ai-agents", "ai-agents", agents_base)

    assert _single(detect_changes(
        store, "ai-hackathon",
        registry=registry)).classification is ChangeClassification.NO_CHANGE
    assert _single(detect_changes(
        store, "ai-agents",
        registry=registry)).classification is ChangeClassification.MEANINGFUL_CHANGE


def test_future_project_uses_the_same_pipeline(
        store, tmp_path, make_git_repo, make_source):
    repo = make_git_repo("future")
    _commit(repo, ("notes.md", "# new\n"))
    src = make_source(repo.path, name="future-proj")
    store.ensure_tracked_work("future-work", "Future", sources=("future-proj",))

    change = _single(detect_changes(
        store, "future-work", registry=_registry(tmp_path, src)))

    assert change.unreviewed is True
    store.set_review_cursor("future-work", "future-proj", repo.head())
    again = _single(detect_changes(
        store, "future-work", registry=_registry(tmp_path, src)))
    assert again.classification is ChangeClassification.NO_CHANGE


def test_filesystem_source_detects_content_change(
        store, tmp_path, make_source):
    from app.sources.enums import SourceType
    from app.sync.revision import read_revision

    root = tmp_path / "plain"
    root.mkdir()
    (root / "notes.md").write_text("# v1\n")
    src = make_source(root, name="plain", type=SourceType.FILESYSTEM)
    store.ensure_tracked_work("w", "W", sources=("plain",))
    store.set_review_cursor(
        "w", "plain", read_revision(src).revision)
    registry = _registry(tmp_path, src)

    assert _single(
        detect_changes(store, "w", registry=registry)
    ).classification is ChangeClassification.NO_CHANGE

    (root / "notes.md").write_text("# v1\n\nMore work documented here.\n")
    change = _single(detect_changes(store, "w", registry=registry))

    assert change.classification is ChangeClassification.MEANINGFUL_CHANGE
    assert change.paths == ()
    assert "per-file" in change.detail


def test_excluded_material_is_not_a_change(
        store, tmp_path, make_git_repo, make_source):
    repo = make_git_repo("excluded")
    _commit(repo, ("app.py", "A = 1\n"))
    base = repo.head()
    # Matches the include glob but is vetoed by the exclude rule: generated
    # output must never become a branding change.
    _commit(repo, ("build/gen.py", "BUNDLE = 1\n" * 200))
    src = make_source(repo.path, name="excluded",
                      exclude=(("build/", "generated output"),))
    store.ensure_tracked_work("w", "W", sources=("excluded",))
    store.set_review_cursor("w", "excluded", base)

    change = _single(detect_changes(store, "w", registry=_registry(tmp_path, src)))

    assert change.classification is ChangeClassification.NO_CHANGE
    assert change.paths == ()


def test_state_invariants_intact(store):
    from app.state import SCHEMA_VERSION

    assert SCHEMA_VERSION == 7
    assert store.schema_version == 7
    store.ensure_tracked_work("w", "W", sources=("s",))
    store.ensure_development("w", "d", "D")
    assert len(store.list_tracked_work()) == 1
