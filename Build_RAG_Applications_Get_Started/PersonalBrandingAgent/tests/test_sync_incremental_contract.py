"""The periodic incremental-sync contract.

Two halves:

* **Revision-first gate** (git sources): the current revision is resolved and
  compared against the last successful checkpoint *before* anything else. An
  unchanged repository returns ``NO_CHANGE`` without inventorying the tree,
  reading a single file, calling the pipeline, or writing state. A changed
  repository diffs old-vs-new through git and only the changed paths are
  discovered, read, and ingested. A full resync happens only with no
  trustworthy baseline (no checkpoint, non-git revision, or a checkpoint
  commit the repository no longer knows).
* **Scoped registry**: periodic sync considers exactly the five roots the
  user named — ``~/DevOps``, ``~/DSA-Python-LeetCode-130``, ``~/Quizey``,
  ``~/DataBases``, ``~/LLMs`` — because the registry is the complete
  statement of sync scope (``sync_all`` iterates it and nothing else).

Single-changed-file, added/deleted-file, and failure-keeps-checkpoint cases
are pinned in ``tests/test_sync_synchronizer.py`` and are not duplicated
here; this module pins what that file does not: zero discovery on no-change,
multi-file selection, the explicit second run, and the committed scope.
"""
from pathlib import Path

import pytest

import app.sync.revision as revision_module
import app.sync.synchronizer as synchronizer_module
from app.sources import load_registry
from app.sync.enums import SyncStatus
from app.sync.synchronizer import SyncContext, sync_source

PERIODIC_ROOTS = (
    Path("/home/alaabadawii/DevOps"),
    Path("/home/alaabadawii/DSA-Python-LeetCode-130"),
    Path("/home/alaabadawii/Quizey"),
    Path("/home/alaabadawii/DataBases"),
    Path("/home/alaabadawii/LLMs"),
)

EXPECTED_PERIODIC_SOURCES = {
    "ibm-genai-coursework",
    "ai-agents",
    "hackathon-lectures",
    "hackathon-practice-lab",
    "quizey-v2",
    "quizey-platform",
    "jenkins-practice",
    "kodekloud-devops-specialization",
    "devops-lab",
    "kubernetes-lab",
    "databases-mongodb-crud",
    "dsa-python-leetcode-130",
}


@pytest.fixture
def context(state_store, recording_ingest):
    """A context whose pipeline is a recorder: nothing is embedded or stored."""
    return SyncContext(store=state_store, ingest=recording_ingest)


def _counting_spy(monkeypatch, module, name):
    """Wrap ``module.name`` counting calls while preserving its behaviour."""
    original = getattr(module, name)
    calls: list = []

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(module, name, spy)
    return calls


def _watch_discovery(monkeypatch):
    """Count every file-discovery entry point without changing behaviour."""
    watched = {}
    for module, name in (
        (synchronizer_module, "changed_paths"),
        (synchronizer_module, "annotate"),
        (synchronizer_module, "plan_changes"),
        (synchronizer_module, "full_resync_plan"),
        (synchronizer_module, "candidate_files"),
        (synchronizer_module, "purge_keys"),
        (revision_module, "iter_admitted_files"),
        (revision_module, "read_admitted_paths"),
        (revision_module, "content_revision"),
    ):
        watched[f"{module.__name__}.{name}"] = _counting_spy(monkeypatch, module, name)
    return watched


# ------------------------------------------------------- the revision gate ---

def test_unchanged_git_repo_discovers_nothing_and_reports_no_change(
    tmp_path, make_git_repo, make_source, context, recording_ingest,
    state_store, monkeypatch,
):
    """Revision equality ends the run before any inventory, read, or write."""
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    repo.write("b.md", "# Beta\n\nMore words.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha")
    sync_source(source, context)
    before = state_store.get_checkpoint("alpha")
    recording_ingest.calls.clear()

    watched = _watch_discovery(monkeypatch)
    result = sync_source(source, context)

    assert result.status is SyncStatus.NO_CHANGE
    assert result.full_resync is False
    assert result.did_work is False
    assert recording_ingest.called is False
    assert all(calls == [] for calls in watched.values()), {
        name for name, calls in watched.items() if calls
    }
    after = state_store.get_checkpoint("alpha")
    assert after.last_revision == before.last_revision
    assert after.updated_at == before.updated_at


def test_several_changed_files_select_only_those(
    tmp_path, make_git_repo, make_source, context, recording_ingest
):
    """Three changed paths out of five files: only those three are selected."""
    repo = make_git_repo()
    repo.write("keep1.md", "# Keep\n\nWords.\n")
    repo.write("keep2.md", "# Keep\n\nWords.\n")
    repo.write("edit1.md", "# Edit me\n\nWords.\n")
    repo.write("edit2.md", "# Edit me\n\nWords.\n")
    repo.write("new.md", "# Placeholder\n\nWords.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha")
    sync_source(source, context)
    recording_ingest.calls.clear()

    repo.write("edit1.md", "# Edit me\n\nRewritten.\n")
    repo.write("edit2.md", "# Edit me\n\nRewritten.\n")
    repo.write("added.md", "# Brand new\n\nWords.\n")
    repo.remove("new.md")
    repo.commit("several changes")

    result = sync_source(source, context)

    assert result.status is SyncStatus.SYNCED
    assert result.full_resync is False
    assert set(result.candidates) == {"edit1.md", "edit2.md", "added.md"}
    assert set(result.purged) == {"new.md"}
    assert "keep1.md" not in result.candidates
    assert "keep2.md" not in result.candidates
    sent = recording_ingest.last["candidates"]
    assert {c.split("/", 2)[-1] for c in sent} == {"edit1.md", "edit2.md", "added.md"}


def test_second_run_after_success_does_not_reingest(
    tmp_path, make_git_repo, make_source, context, recording_ingest,
    state_store,
):
    """The checkpoint from a successful sync makes the next run a pure no-op."""
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    commit = repo.commit()
    source = make_source(repo.path, name="alpha")

    first = sync_source(source, context)
    assert first.status is SyncStatus.SYNCED
    assert state_store.get_checkpoint("alpha").last_revision == commit
    recording_ingest.calls.clear()

    second = sync_source(source, context)

    assert second.status is SyncStatus.NO_CHANGE
    assert second.current_revision == commit
    assert recording_ingest.called is False


# ------------------------------------------------------------- scoped registry ---

@pytest.fixture(scope="module")
def periodic_registry():
    """The committed registry — the artifact periodic sync actually reads."""
    return load_registry()


def test_periodic_registry_names_exactly_the_intended_scope(periodic_registry):
    assert set(periodic_registry.names) == EXPECTED_PERIODIC_SOURCES


def test_every_periodic_source_lives_under_an_intended_root(periodic_registry):
    roots = [root.resolve() for root in PERIODIC_ROOTS]
    outside = [
        f"{source.name}: {source.local_path}"
        for source in periodic_registry
        if not any(
            source.local_path.resolve() == root
            or root in source.local_path.resolve().parents
            for root in roots
        )
    ]
    assert outside == []


def test_dsa_practice_is_a_tracked_git_source(periodic_registry):
    """The fifth root is registered (it used to sit in not_registered)."""
    source = periodic_registry.get("dsa-python-leetcode-130")
    assert source is not None
    assert source.is_git
    assert source.ref == "main"
    assert not any(
        "DSA-Python-LeetCode-130" in str(entry.path)
        for entry in periodic_registry.not_registered
    )
