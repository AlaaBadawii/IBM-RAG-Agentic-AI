"""Step 3: per-source synchronization, checkpoints, and failure isolation.

The invariants under test are the ones an unattended nightly run depends on:
a no-change source does nothing at all, a source's checkpoint moves only after
a fully successful synchronization, and one source's failure leaves the other
twenty-eight alone.
"""
import pytest

from app.errors import IngestionError
from app.sources.enums import SourceType, SyncDisposition
from app.sources.models import Registry
from app.state.enums import LifecycleState
from app.sync.enums import RevisionKind, SyncErrorCategory, SyncStatus
from app.sync.synchronizer import SyncContext, sync_all, sync_source
from tests.conftest import PROJECT_ROOT, RecordingIngest


@pytest.fixture
def context(state_store, recording_ingest):
    """A context whose pipeline is a recorder: nothing is embedded or stored."""
    return SyncContext(store=state_store, ingest=recording_ingest)


# --------------------------------------------------------- first sync / full ---

def test_first_sync_has_no_checkpoint_and_submits_the_whole_inventory(
    tmp_path, make_git_repo, make_source, context, recording_ingest
):
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    repo.write("nested/b.md", "# Beta\n\nMore words.\n")
    repo.write("ignored.txt", "not admitted")
    commit = repo.commit()
    source = make_source(repo.path, name="alpha")

    result = sync_source(source, context)

    assert result.status is SyncStatus.SYNCED
    assert result.previous_revision is None
    assert result.current_revision == commit
    assert result.revision_kind is RevisionKind.GIT
    assert result.full_resync
    assert result.candidates == ("a.md", "nested/b.md")
    assert result.purged == ()
    assert recording_ingest.called
    assert recording_ingest.last["scope"] == "@source/alpha/"
    assert result.checkpoint.last_revision == commit


def test_a_repository_with_no_commits_is_synchronized_by_content(
    tmp_path, make_git_repo, make_source, context
):
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    result = sync_source(make_source(repo.path), context)

    assert result.revision_kind is RevisionKind.CONTENT
    assert result.candidates == ("a.md",)
    assert result.checkpoint.last_revision == result.current_revision


# ----------------------------------------------------------------- no change ---

def test_unchanged_source_is_a_no_op_with_no_state_write(
    tmp_path, make_git_repo, make_source, context, recording_ingest, state_store
):
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha")

    sync_source(source, context)
    first = state_store.get_checkpoint("alpha")
    recording_ingest.calls.clear()

    result = sync_source(source, context)

    assert result.status is SyncStatus.NO_CHANGE
    assert result.failed is False
    assert result.did_work is False
    assert recording_ingest.called is False, "a no-change sync must not touch Chroma"
    # Not even a state write: advancing a checkpoint already at this revision
    # would make an untouched source look busy.
    after = state_store.get_checkpoint("alpha")
    assert after.updated_at == first.updated_at
    assert after.last_attempt_at == first.last_attempt_at
    assert after.last_revision == first.last_revision


# --------------------------------------------------------------- what changed ---

def test_new_revision_submits_only_the_changed_files(
    tmp_path, make_git_repo, make_source, context, recording_ingest
):
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    repo.write("b.md", "# Beta\n\nMore words.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha")
    sync_source(source, context)
    recording_ingest.calls.clear()

    repo.write("a.md", "# Alpha\n\nRewritten words.\n")
    second = repo.commit("edit a")

    result = sync_source(source, context)

    assert result.status is SyncStatus.SYNCED
    assert result.full_resync is False
    assert result.candidates == ("a.md",)
    assert result.previous_revision != second
    assert result.checkpoint.last_revision == second
    # A diff, so no sweep: its keep-set would be a partial set of the source.
    assert recording_ingest.last["scope"] is None


def test_deleted_file_becomes_a_purge(tmp_path, make_git_repo, make_source, context,
                                      recording_ingest):
    repo = make_git_repo()
    repo.write("keep.md", "# Keep\n\nWords.\n")
    repo.write("drop.md", "# Drop\n\nWords.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha")
    sync_source(source, context)
    recording_ingest.calls.clear()

    repo.remove("drop.md")
    repo.commit("delete")

    result = sync_source(source, context)

    assert result.candidates == ()
    assert result.purged == ("drop.md",)
    assert recording_ingest.last["purge"] == ("@source/alpha/drop.md",)


def test_a_commit_of_only_irrelevant_files_does_no_ingestion_work(
    tmp_path, make_git_repo, make_source, context, recording_ingest, state_store
):
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha", include=("**/*.md",))
    sync_source(source, context)
    recording_ingest.calls.clear()

    repo.write("script.sh", "#!/bin/sh\necho hi\n")
    commit = repo.commit("a shell script, not admitted")

    result = sync_source(source, context)

    assert result.status is SyncStatus.SYNCED
    assert result.did_work is False
    assert recording_ingest.called is False
    assert result.candidates == () and result.purged == ()
    # The changed path is still reported, with the rule that refused it.
    assert [c.path for c in result.changed_paths] == ["script.sh"]
    assert result.changed_paths[0].admitted is False
    # ...and the checkpoint still advances: the revision *was* processed, and
    # leaving it behind would re-diff this commit on every future run.
    assert state_store.get_checkpoint("alpha").last_revision == commit


def test_a_rename_is_purged_and_re_added(tmp_path, make_git_repo, make_source,
                                         context, recording_ingest):
    repo = make_git_repo()
    repo.write("original.md", "# Document\n\n" + "Body.\n" * 40)
    repo.commit()
    source = make_source(repo.path, name="alpha")
    sync_source(source, context)
    recording_ingest.calls.clear()

    repo.move("original.md", "renamed.md")
    repo.commit("rename")

    result = sync_source(source, context)

    assert result.candidates == ("renamed.md",)
    assert result.purged == ("original.md",)
    assert [c.change_type.value for c in result.changed_paths] == ["renamed"]
    assert result.changed_paths[0].is_exact_rename


# ----------------------------------------------------------- filesystem source ---

def test_filesystem_source_uses_a_content_revision(tmp_path, make_source, context,
                                                  recording_ingest):
    (tmp_path / "a.md").write_text("# Alpha\n\nWords.\n", encoding="utf-8")
    source = make_source(tmp_path, name="files", type=SourceType.FILESYSTEM, ref=None)

    first = sync_source(source, context)
    assert first.status is SyncStatus.SYNCED
    assert first.revision_kind is RevisionKind.CONTENT
    assert first.candidates == ("a.md",)

    recording_ingest.calls.clear()
    assert sync_source(source, context).status is SyncStatus.NO_CHANGE
    assert recording_ingest.called is False


def test_filesystem_source_resubmits_its_inventory_and_lets_hashes_narrow(
    tmp_path, make_source, context, recording_ingest
):
    """No history to diff, so the whole inventory goes and the content hashes
    decide — which is where the narrowing already happens."""
    (tmp_path / "a.md").write_text("# Alpha\n\nWords.\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Beta\n\nMore words.\n", encoding="utf-8")
    source = make_source(tmp_path, name="files", type=SourceType.FILESYSTEM, ref=None)
    sync_source(source, context)
    recording_ingest.calls.clear()

    (tmp_path / "a.md").write_text("# Alpha\n\nRewritten.\n", encoding="utf-8")
    result = sync_source(source, context)

    assert result.full_resync
    assert result.candidates == ("a.md", "b.md")
    assert recording_ingest.last["scope"] == "@source/files/"


# ----------------------------------------------------------- completed projects ---

def test_first_sync_of_a_completed_project_does_not_fire_a_signal(
    tmp_path, make_git_repo, make_source, context
):
    """A baseline establishes where the source *is*; nothing has moved yet."""
    repo = make_git_repo()
    repo.write("legacy.md", "# Legacy\n\nDone long ago.\n")
    repo.commit()
    source = make_source(repo.path, name="done", lifecycle=LifecycleState.COMPLETED)

    result = sync_source(source, context)

    assert result.review_signal is None
    assert result.plan.disposition is SyncDisposition.NORMAL


def test_new_relevant_commits_in_a_completed_project_are_flagged_and_processed(
    tmp_path, make_git_repo, make_source, context, recording_ingest
):
    repo = make_git_repo()
    repo.write("legacy.md", "# Legacy\n\nDone long ago.\n")
    repo.commit()
    source = make_source(repo.path, name="done", lifecycle=LifecycleState.COMPLETED)
    sync_source(source, context)

    repo.write("legacy.md", "# Legacy\n\nActually, one more thing.\n")
    repo.commit("revived")

    result = sync_source(source, context)

    # Detected and flagged...
    assert result.needs_review
    assert result.plan.disposition is SyncDisposition.REVIEW_REQUIRED
    assert result.review_signal.lifecycle is LifecycleState.COMPLETED
    assert result.review_signal.changed_paths == ("legacy.md",)
    assert "completed" in result.review_signal.as_message()
    assert result.requires_human_intervention
    # ...and still processed, never ignored.
    assert result.candidates == ("legacy.md",)
    assert recording_ingest.called


def test_a_completed_project_that_did_not_move_is_not_flagged(tmp_path, make_git_repo,
                                                             make_source, context):
    """Firing on an unchanged source would train the reader to ignore signals."""
    repo = make_git_repo()
    repo.write("legacy.md", "# Legacy\n\nDone long ago.\n")
    repo.commit()
    source = make_source(repo.path, name="done", lifecycle=LifecycleState.COMPLETED)
    sync_source(source, context)

    assert sync_source(source, context).review_signal is None


def test_lifecycle_state_is_never_changed_by_synchronization(
    tmp_path, make_git_repo, make_source, context, state_store
):
    """PLAN.md Step 2: the signal is raised, the declaration is not edited."""
    repo = make_git_repo()
    repo.write("legacy.md", "# Legacy\n")
    repo.commit()
    source = make_source(repo.path, name="done", lifecycle=LifecycleState.COMPLETED)
    state_store.set_source_lifecycle("done", LifecycleState.COMPLETED, note="declared")

    sync_source(source, context)
    repo.write("legacy.md", "# Legacy\n\nRevived.\n")
    repo.commit()
    result = sync_source(source, context)

    assert result.needs_review
    stored = state_store.get_source_lifecycle("done")
    assert stored.lifecycle is LifecycleState.COMPLETED
    assert stored.note == "declared"


# ------------------------------------------------------------------- failures ---

def test_ingestion_failure_does_not_advance_the_checkpoint(
    tmp_path, make_git_repo, make_source, state_store
):
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha")

    good = SyncContext(store=state_store, ingest=RecordingIngest())
    sync_source(source, good)
    checkpoint_before = state_store.get_checkpoint("alpha")

    repo.write("a.md", "# Alpha\n\nRewritten.\n")
    repo.commit()

    failing = SyncContext(
        store=state_store, ingest=RecordingIngest(raises=IngestionError("embedder exploded"))
    )
    result = sync_source(source, failing)

    assert result.status is SyncStatus.FAILED
    assert result.error_category is SyncErrorCategory.INGESTION_FAILURE
    assert "embedder exploded" in result.error
    # The revision stays where it was, so the next run re-processes this range.
    after = state_store.get_checkpoint("alpha")
    assert after.last_revision == checkpoint_before.last_revision
    assert after.last_outcome.value == "FAILED"
    assert after.last_synced_at == checkpoint_before.last_synced_at


def test_a_failure_is_recorded_structurally_not_just_logged(
    tmp_path, make_git_repo, make_source, state_store
):
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha")
    failing = SyncContext(
        store=state_store, ingest=RecordingIngest(raises=IngestionError("nope"))
    )

    sync_source(source, failing)
    failures = state_store.list_failures()

    assert len(failures) == 1
    assert failures[0].phase == "sync"
    assert failures[0].error_category == "ingestion_failure"
    assert failures[0].workflow == "sync"
    assert failures[0].retryable
    assert not failures[0].requires_human_intervention


def test_repeated_failures_accumulate_on_one_row(tmp_path, make_git_repo, make_source,
                                                state_store):
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha")
    failing = SyncContext(
        store=state_store, ingest=RecordingIngest(raises=IngestionError("nope"))
    )

    sync_source(source, failing)
    sync_source(source, failing)
    failures = state_store.list_failures()

    assert len(failures) == 1
    assert failures[0].occurrence_count == 2


def test_missing_source_is_reported_as_needing_a_human(tmp_path, make_source,
                                                       state_store):
    source = make_source(tmp_path / "gone", name="gone")
    context = SyncContext(store=state_store, ingest=RecordingIngest())

    result = sync_source(source, context)

    assert result.status is SyncStatus.FAILED
    assert result.error_category is SyncErrorCategory.SOURCE_UNAVAILABLE
    assert result.requires_human_intervention
    assert state_store.list_failures()[0].requires_human_intervention
    assert state_store.list_failures()[0].retryable is False
    # A checkpoint row exists, recording the attempt, with no revision.
    assert state_store.get_checkpoint("gone").last_revision is None


def test_a_source_rooted_inside_the_application_is_refused(tmp_path, make_source,
                                                           state_store,
                                                           recording_ingest):
    """The self-ingestion guard, at the moment a candidate would be built."""
    source = make_source(PROJECT_ROOT, name="self", type=SourceType.FILESYSTEM,
                         ref=None, include=("**/*",))
    context = SyncContext(store=state_store, ingest=recording_ingest)

    result = sync_source(source, context)

    assert result.status is SyncStatus.FAILED
    assert result.error_category is SyncErrorCategory.GUARD_REFUSED
    assert result.requires_human_intervention
    assert recording_ingest.called is False


def test_an_unexpected_error_is_recorded_rather_than_escaping(tmp_path, make_git_repo,
                                                             make_source, state_store):
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha")
    context = SyncContext(
        store=state_store, ingest=RecordingIngest(raises=RuntimeError("who knows"))
    )

    result = sync_source(source, context)

    assert result.status is SyncStatus.FAILED
    assert result.error_category is SyncErrorCategory.UNEXPECTED


def test_a_source_with_an_unrepresentable_lifecycle_still_reports_a_failure(
    tmp_path, make_git_repo, make_source, context
):
    """The failure path must not be able to fail.

    Building a plan reads the declared lifecycle, and a value outside the four
    declared ones has no plan — through the registry that cannot happen, since
    the loader refuses the value when it loads the file, but a failure path
    that raised here would report one broken source by aborting the run over
    all of them.
    """
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha", lifecycle="FINISHED")

    result = sync_source(source, context)  # must return, not raise

    assert result.status is SyncStatus.FAILED
    assert result.source_name == "alpha"
    assert result.plan.disposition is SyncDisposition.REVIEW_REQUIRED


# ------------------------------------------------------------------- recovery ---

def test_a_failed_run_is_retried_over_the_same_range(tmp_path, make_git_repo,
                                                     make_source, state_store,
                                                     recording_ingest):
    """Interrupted, then rerun: correct on the second attempt, not duplicated."""
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha")
    good = SyncContext(store=state_store, ingest=recording_ingest)
    sync_source(source, good)

    repo.write("a.md", "# Alpha\n\nRewritten.\n")
    repo.write("b.md", "# Beta\n\nBrand new.\n")
    second = repo.commit("two changes")

    failing = SyncContext(
        store=state_store, ingest=RecordingIngest(raises=IngestionError("interrupted"))
    )
    assert sync_source(source, failing).status is SyncStatus.FAILED
    recording_ingest.calls.clear()

    retried = sync_source(source, good)

    assert retried.status is SyncStatus.SYNCED
    # The whole range, because the checkpoint never moved past the first commit.
    assert retried.candidates == ("a.md", "b.md")
    assert state_store.get_checkpoint("alpha").last_revision == second


def test_a_checkpoint_whose_commit_vanished_triggers_a_full_resync(
    tmp_path, make_git_repo, make_source, context, recording_ingest, state_store
):
    """History rewritten: there is no valid diff, so re-submit the inventory.

    A checkpoint can outlive the commit it names — a rebase, a force-push, a
    garbage collection. The store is written directly here because producing a
    genuinely unreachable commit means expiring the reflog and pruning, which
    tests git's garbage collector rather than this code.
    """
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    repo.write("b.md", "# Beta\n\nWords.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha")
    sync_source(source, context)
    state_store.record_sync_success("alpha", "0" * 40)  # a commit git does not have
    recording_ingest.calls.clear()

    result = sync_source(source, context)

    assert result.full_resync
    assert result.previous_revision == "0" * 40
    assert result.candidates == ("a.md", "b.md")
    assert recording_ingest.last["scope"] == "@source/alpha/"


def test_a_content_checkpoint_meeting_a_commit_is_a_full_resync(
    tmp_path, make_git_repo, make_source, context, recording_ingest
):
    """A repository that had no commits and then got one, which really happens.

    The stored revision is a content digest, and a digest cannot be handed to
    git — so the change is real but undiffable, and the content hashes decide
    what actually differs.
    """
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    source = make_source(repo.path, name="alpha")

    first = sync_source(source, context)
    assert first.revision_kind is RevisionKind.CONTENT

    repo.commit("first commit")
    recording_ingest.calls.clear()

    result = sync_source(source, context)

    assert result.full_resync
    assert result.revision_kind is RevisionKind.GIT
    assert result.previous_revision == first.current_revision
    assert result.candidates == ("a.md",)
    assert recording_ingest.last["scope"] == "@source/alpha/"


# ------------------------------------------------------------- per-source runs ---

def test_a_repository_that_is_not_in_the_registry_is_never_synchronized(
    tmp_path, make_git_repo, make_source, state_store, recording_ingest
):
    """The registry is the complete statement of what counts as evidence.

    A repository sitting beside a registered source is invisible to
    synchronization — not because a filter rejected it, but because nothing
    enumerated it. There is no walk here for a filter to apply to, which is
    what makes the guarantee structural rather than a matter of pattern
    quality.
    """
    registered = make_git_repo()
    registered.write("a.md", "# Alpha\n\nWords.\n")
    registered.commit()
    unregistered = make_git_repo()
    unregistered.write("b.md", "# Beta\n\nNever registered.\n")
    unregistered.commit()

    registry = Registry(
        sources=(make_source(registered.path, name="registered"),),
        path=tmp_path / "sources.yaml",
    )
    run = sync_all(registry, SyncContext(store=state_store, ingest=recording_ingest))

    assert [result.source_name for result in run] == ["registered"]
    assert recording_ingest.last["candidates"] == ("@source/registered/a.md",)
    assert [c.source_name for c in state_store.list_checkpoints()] == ["registered"]
    assert not any(
        "Never registered" in str(call) for call in recording_ingest.calls
    )


def test_one_source_failing_leaves_the_others_alone(tmp_path, make_git_repo,
                                                    make_source, state_store,
                                                    recording_ingest):
    """A success / B broken / C success — with no cross-source transaction."""
    first = make_git_repo()
    first.write("a.md", "# Alpha\n\nWords.\n")
    first.commit()
    third = make_git_repo()
    third.write("c.md", "# Gamma\n\nWords.\n")
    third.commit()

    registry = Registry(
        sources=(
            make_source(first.path, name="first"),
            make_source(tmp_path / "missing", name="broken"),
            make_source(third.path, name="third"),
        ),
        path=tmp_path / "sources.yaml",
    )
    context = SyncContext(store=state_store, ingest=recording_ingest)

    run = sync_all(registry, context)

    assert [r.source_name for r in run.synced] == ["first", "third"]
    assert [r.source_name for r in run.failed] == ["broken"]
    assert not run.ok
    assert run.get("broken").error_category is SyncErrorCategory.SOURCE_UNAVAILABLE
    assert run.get("first").status is SyncStatus.SYNCED
    assert run.get("third").status is SyncStatus.SYNCED
    # The run continued past the failure: both healthy sources were attempted.
    assert len(recording_ingest.calls) == 2


def test_a_run_where_every_source_fails_still_reports_all_of_them(
    tmp_path, make_source, state_store, recording_ingest
):
    registry = Registry(
        sources=tuple(
            make_source(tmp_path / f"gone{i}", name=f"gone{i}") for i in range(3)
        ),
        path=tmp_path / "sources.yaml",
    )
    run = sync_all(registry, SyncContext(store=state_store, ingest=recording_ingest))

    assert len(run.failed) == 3
    assert not run.ok
    assert recording_ingest.called is False
