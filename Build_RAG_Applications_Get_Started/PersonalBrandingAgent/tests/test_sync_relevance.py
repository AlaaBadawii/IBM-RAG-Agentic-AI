"""Step 3: the relevance policy, including the deliberate rename policy.

Include is the floor, exclude is a veto, and a veto cannot be outvoted —
gathered here because the *reason* a path was refused has to survive into the
synchronization result, and because a rename is the one change that can add and
remove content in the same breath.
"""
from app.sources.patterns import is_admitted
from app.sync.enums import ChangeType
from app.sync.models import ChangedPath
from app.sync.relevance import (
    annotate,
    decide,
    full_resync_plan,
    plan_changes,
)


def _change(path, change_type=ChangeType.ADDED, previous_path=None, similarity=None):
    return ChangedPath(
        path=path,
        change_type=change_type,
        previous_path=previous_path,
        similarity=similarity,
    )


# ------------------------------------------------------------------ decide ---

def test_decide_admits_an_included_path(tmp_path, make_source):
    source = make_source(tmp_path)
    verdict = decide(source, "docs/guide.md")
    assert verdict.admitted
    assert verdict.rule is None
    assert verdict.reason is None
    assert not verdict.vetoed


def test_decide_names_the_exclusion_and_carries_its_reason(tmp_path, make_source):
    source = make_source(
        tmp_path,
        exclude=(("vendor/", "third-party code, not the user's work"),),
    )
    verdict = decide(source, "vendor/lib.md")
    assert not verdict.admitted
    assert verdict.rule == "vendor/"
    assert verdict.reason == "third-party code, not the user's work"
    assert verdict.vetoed


def test_decide_exclusion_beats_include(tmp_path, make_source):
    """Deny wins, however the two lists are ordered."""
    source = make_source(
        tmp_path,
        include=("**/*.md",),
        exclude=(("secrets.md", "credentials"),),
    )
    assert decide(source, "secrets.md").vetoed


def test_decide_reports_a_path_no_include_matched_as_unvetoed(tmp_path, make_source):
    """Not every rejection is a decision: some paths were simply never in scope."""
    source = make_source(tmp_path, include=("**/*.md",))
    verdict = decide(source, "script.sh")
    assert not verdict.admitted
    assert verdict.rule is None
    assert not verdict.vetoed
    assert "include patterns" in verdict.reason


def test_decide_agrees_with_the_registry_matcher(tmp_path, make_source):
    """The reason is recovered here; the decision stays the registry's."""
    source = make_source(
        tmp_path,
        include=("**/*.md", "**/*.py"),
        exclude=(("build/", "generated"), ("**/.env", "credentials")),
    )
    paths = [
        "a.md", "src/b.py", "build/c.py", "deep/nested/.env",
        "notes.txt", "build/deep/d.md", "src/nested/e.py", ".env",
    ]
    for path in paths:
        assert decide(source, path).admitted == source.admits(path), path
        assert decide(source, path).admitted == is_admitted(
            path, source.include, source.exclude_patterns
        ), path


def test_decide_on_a_source_with_no_include_admits_nothing(tmp_path, make_source):
    source = make_source(tmp_path, include=())
    assert not decide(source, "anything.md").admitted


# ----------------------------------------------------------------- annotate ---

def test_annotate_gives_every_path_a_verdict(tmp_path, make_source):
    source = make_source(tmp_path, include=("**/*.md",))
    changes = [_change("kept.md"), _change("dropped.py")]
    annotated = annotate(source, changes)

    assert [c.admitted for c in annotated] == [True, False]
    assert annotated[1].reason is not None
    assert annotated[0].reason is None


def test_annotate_preserves_change_details(tmp_path, make_source):
    source = make_source(tmp_path)
    annotated = annotate(
        source,
        [_change("new.md", ChangeType.RENAMED, previous_path="old.md", similarity=100)],
    )
    assert annotated[0].previous_path == "old.md"
    assert annotated[0].similarity == 100
    assert annotated[0].is_exact_rename


# ------------------------------------------------------------- plan_changes ---

def test_plan_changes_adds_and_modifies_are_candidates(tmp_path, make_source):
    source = make_source(tmp_path)
    plan = plan_changes(
        source,
        annotate(source, [_change("a.md"), _change("b.md", ChangeType.MODIFIED)]),
    )
    assert plan.candidates == ("a.md", "b.md")
    assert plan.purges == ()


def test_plan_changes_deletion_is_a_purge(tmp_path, make_source):
    source = make_source(tmp_path)
    plan = plan_changes(source, annotate(source, [_change("gone.md", ChangeType.DELETED)]))

    assert plan.candidates == ()
    assert plan.purges == ("gone.md",)
    assert plan.is_empty is False


def test_plan_changes_ignores_an_irrelevant_commit_entirely(tmp_path, make_source):
    """A commit touching only excluded files produces no ingestion work."""
    source = make_source(tmp_path, include=("**/*.md",), exclude=(("vendor/", "not ours"),))
    plan = plan_changes(
        source,
        annotate(source, [_change("vendor/a.py"), _change("vendor/b.py", ChangeType.MODIFIED)]),
    )
    assert plan.candidates == ()
    assert plan.purges == ()
    assert plan.is_empty
    # ...and the paths are still reported, each with the rule that refused it.
    assert len(plan.changes) == 2
    assert all(c.reason == "not ours" for c in plan.changes)


def test_plan_changes_does_not_purge_a_deleted_file_that_was_never_admitted(
    tmp_path, make_source
):
    source = make_source(tmp_path, include=("**/*.md",))
    plan = plan_changes(source, annotate(source, [_change("gone.py", ChangeType.DELETED)]))
    assert plan.purges == ()


# -- the rename policy --------------------------------------------------------

def test_rename_candidate_and_purge_when_both_sides_are_admitted(tmp_path, make_source):
    """The ordinary case: the content moves, so the old key must go."""
    source = make_source(tmp_path)
    plan = plan_changes(
        source,
        annotate(source, [_change("new.md", ChangeType.RENAMED,
                                  previous_path="old.md", similarity=57)]),
    )
    assert plan.candidates == ("new.md",)
    assert plan.purges == ("old.md",)


def test_exact_rename_still_purges_the_old_path(tmp_path, make_source):
    """The deliberate part of the policy.

    An exact rename yields identical content addresses at the new path, so the
    pipeline must delete the old key *before* claiming those ids — which is
    exactly what its delete-then-add ordering does. Skipping the purge would
    leave correctness resting on Chroma accepting an add over an existing id,
    which is a convenience, not a guarantee.
    """
    source = make_source(tmp_path)
    plan = plan_changes(
        source,
        annotate(source, [_change("new.md", ChangeType.RENAMED,
                                  previous_path="old.md", similarity=100)]),
    )
    assert plan.candidates == ("new.md",)
    assert plan.purges == ("old.md",)


def test_rename_out_of_the_admitted_set_purges_without_adding(tmp_path, make_source):
    source = make_source(tmp_path, include=("**/*.md",), exclude=(("build/", "generated"),))
    plan = plan_changes(
        source,
        annotate(source, [_change("build/new.md", ChangeType.RENAMED,
                                  previous_path="old.md", similarity=100)]),
    )
    assert plan.candidates == ()
    assert plan.purges == ("old.md",)


def test_rename_into_the_admitted_set_adds_without_purging(tmp_path, make_source):
    source = make_source(tmp_path, include=("**/*.md",))
    plan = plan_changes(
        source,
        annotate(source, [_change("new.md", ChangeType.RENAMED,
                                  previous_path="old.py", similarity=100)]),
    )
    assert plan.candidates == ("new.md",)
    assert plan.purges == ()


def test_rename_wholly_outside_the_admitted_set_is_no_work(tmp_path, make_source):
    source = make_source(tmp_path, include=("**/*.md",), exclude=(("build/", "generated"),))
    plan = plan_changes(
        source,
        annotate(source, [_change("build/new.py", ChangeType.RENAMED,
                                  previous_path="build/old.py", similarity=100)]),
    )
    assert plan.is_empty


def test_rename_whose_old_path_is_re_added_is_both_a_candidate_and_a_purge(
    tmp_path, make_source
):
    """`git mv a b` followed by a fresh `a` is two changes, and converges."""
    source = make_source(tmp_path)
    plan = plan_changes(
        source,
        annotate(source, [
            _change("b.md", ChangeType.RENAMED, previous_path="a.md", similarity=100),
            _change("a.md", ChangeType.ADDED),
        ]),
    )
    assert plan.candidates == ("b.md", "a.md")
    assert plan.purges == ("a.md",)


# -------------------------------------------------------------- deduplication ---

def test_plan_changes_collapses_repeated_paths(tmp_path, make_source):
    source = make_source(tmp_path)
    plan = plan_changes(
        source,
        annotate(source, [_change("a.md"), _change("a.md", ChangeType.MODIFIED)]),
    )
    assert plan.candidates == ("a.md",)


# --------------------------------------------------------- full_resync_plan ---

def test_full_resync_plan_is_the_whole_admitted_inventory(tmp_path, make_source):
    (tmp_path / "a.md").write_text("a")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "b.py").write_text("b")
    (tmp_path / "ignored.txt").write_text("c")
    source = make_source(tmp_path)

    plan = full_resync_plan(source)
    assert plan.candidates == ("a.md", "nested/b.py")
    assert plan.purges == ()
    # No per-path history exists, so nothing can be named as removed; stale
    # keys are handled by the pipeline's scoped sweep instead, which the
    # synchronizer enables only for a plan built here.
    assert plan.changes == ()
    assert plan.is_empty is False


def test_full_resync_plan_of_an_empty_source_is_empty(tmp_path, make_source):
    assert full_resync_plan(make_source(tmp_path)).is_empty
