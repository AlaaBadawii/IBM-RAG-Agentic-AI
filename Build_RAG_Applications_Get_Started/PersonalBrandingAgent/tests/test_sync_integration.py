"""Step 3 end to end: temporary git repositories, the real pipeline, real Chroma.

Nothing here is mocked. Each test builds a throwaway repository under
``tmp_path`` — never the user's workspace — commits to it, synchronizes it with
the actual ingestion pipeline against a temporary Chroma collection, and then
looks at what is in the collection.

The milestone test at the bottom is the one that matters most: two consecutive
synchronizations of an unchanged source must leave Chroma *byte-identical*,
compared by reading it back rather than by trusting a log line or a stat.
"""
import json

import pytest
from langchain_chroma import Chroma

from app.ingestion.pipeline import run_ingestion
from app.sources.enums import SourceType
from app.sources.models import Registry
from app.state.enums import LifecycleState
from app.state.store import StateStore
from app.sync.enums import RevisionKind, SyncStatus
from app.sync.synchronizer import SyncContext, sync_all, sync_source


@pytest.fixture
def context(state_store, chroma_store, fake_embeddings):
    """A context wired to the real pipeline and a temporary collection."""
    return SyncContext(store=state_store, chroma=chroma_store,
                       embeddings=fake_embeddings)


def _keys(store) -> set[str]:
    result = store.get(include=["metadatas"])
    return {meta["source"] for meta in result["metadatas"] if meta}


def _documents(store, key: str) -> list[str]:
    result = store.get(where={"source": key}, include=["documents"])
    return result["documents"]


def _fingerprint(store, *, only=None) -> list:
    """Everything Chroma holds, in a comparable, order-independent form.

    Ids, documents, metadata, and the stored vectors — nothing about *when* a
    row was written, because an idempotent pipeline must produce the same rows
    regardless. ``only`` filters on stored metadata, which is how the corpus
    subset of a shared collection gets compared on its own.
    """
    result = store.get(include=["metadatas", "documents", "embeddings"])
    embeddings = result["embeddings"]
    if embeddings is None:  # a collection with nothing in it
        embeddings = [[]] * len(result["ids"])
    rows = []
    for chunk_id, document, meta, embedding in zip(
        result["ids"], result["documents"], result["metadatas"], embeddings,
    ):
        meta = meta or {}
        if only is not None and not only(meta):
            continue
        rows.append((
            chunk_id,
            document,
            json.dumps(meta, sort_keys=True),
            [round(float(value), 9) for value in embedding],
        ))
    return sorted(rows, key=lambda row: row[0])


def _corpus_only(meta: dict) -> bool:
    """Rows that came from the hand-written corpus rather than a source."""
    return not str(meta.get("source", "")).startswith("@source/")


# --------------------------------------------------------------- the lifecycle ---

def test_commit_then_edit_then_nothing(tmp_path, make_git_repo, make_source, context,
                                       chroma_store, state_store):
    """The sequence PLAN.md Step 3 §16 describes, in one test."""
    repo = make_git_repo()
    repo.write("docs/architecture.md", "# Architecture\n\nA design note.\n")
    repo.write("src/service.py", "# Service\n\nA module.\n")
    repo.write("notes.txt", "not admitted by the include profile")
    commit_a = repo.commit("A")
    source = make_source(repo.path, name="alpha")

    # --- commit A: no checkpoint, so the whole admitted inventory goes in.
    first = sync_source(source, context)
    assert first.status is SyncStatus.SYNCED
    assert first.full_resync and first.previous_revision is None
    assert first.current_revision == commit_a
    assert first.candidates == ("docs/architecture.md", "src/service.py")
    assert _keys(chroma_store) == {
        "@source/alpha/docs/architecture.md", "@source/alpha/src/service.py",
    }
    assert state_store.get_checkpoint("alpha").last_revision == commit_a

    # --- commit B: one file edited, one added. Only those two are submitted.
    repo.write("src/service.py", "# Service\n\nA module, now with retries.\n")
    repo.write("docs/runbook.md", "# Runbook\n\nHow to operate it.\n")
    commit_b = repo.commit("B")

    second = sync_source(source, context)
    assert second.status is SyncStatus.SYNCED
    assert second.previous_revision == commit_a
    assert second.current_revision == commit_b
    assert second.full_resync is False
    assert second.candidates == ("docs/runbook.md", "src/service.py")
    assert second.ingestion["files_updated"] == 1
    assert second.ingestion["files_added"] == 1
    # Two files were read, not three: architecture.md never reached the
    # pipeline, because git said it did not change and nothing here re-checks
    # the whole tree to find that out.
    assert second.ingestion["files_discovered"] == 2
    assert second.ingestion["files_unchanged"] == 0
    assert "now with retries." in " ".join(
        _documents(chroma_store, "@source/alpha/src/service.py")
    )
    assert "@source/alpha/docs/runbook.md" in _keys(chroma_store)
    assert state_store.get_checkpoint("alpha").last_revision == commit_b

    # --- sync again: same revision, so nothing at all happens.
    before = _fingerprint(chroma_store)
    third = sync_source(source, context)
    assert third.status is SyncStatus.NO_CHANGE
    assert third.did_work is False
    assert _fingerprint(chroma_store) == before


def test_a_deleted_file_leaves_chroma(tmp_path, make_git_repo, make_source, context,
                                      chroma_store, state_store):
    repo = make_git_repo()
    repo.write("keep.md", "# Keep\n\nStays.\n")
    repo.write("drop.md", "# Drop\n\nGoes.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha")
    sync_source(source, context)
    assert "@source/alpha/drop.md" in _keys(chroma_store)

    repo.remove("drop.md")
    repo.commit("delete drop.md")

    result = sync_source(source, context)

    assert result.purged == ("drop.md",)
    assert result.ingestion["files_removed"] == 1
    assert result.ingestion["chunks_removed"] > 0
    assert _keys(chroma_store) == {"@source/alpha/keep.md"}


def test_an_exact_rename_keeps_the_content_under_the_new_name(
    tmp_path, make_git_repo, make_source, context, chroma_store
):
    """The rename policy, verified against the collection rather than the plan."""
    body = "# Handover\n\n" + "A paragraph of the document.\n" * 30
    repo = make_git_repo()
    repo.write("draft.md", body)
    repo.commit()
    source = make_source(repo.path, name="alpha")
    sync_source(source, context)
    before = chroma_store._collection.count()
    assert _keys(chroma_store) == {"@source/alpha/draft.md"}

    repo.move("draft.md", "final.md")
    repo.commit("rename")

    result = sync_source(source, context)

    assert result.changed_paths[0].is_exact_rename
    assert result.candidates == ("final.md",)
    assert result.purged == ("draft.md",)
    # Present under the new key, absent under the old one, and *not duplicated*:
    # an exact rename keeps the content address, so a purge that ran after the
    # add would have deleted the chunks the new key had just claimed.
    assert _keys(chroma_store) == {"@source/alpha/final.md"}
    assert chroma_store._collection.count() == before
    assert body.splitlines()[0] in " ".join(_documents(chroma_store, "@source/alpha/final.md"))


def test_a_rename_that_also_edits_the_file_reindexes_it(tmp_path, make_git_repo,
                                                        make_source, context,
                                                        chroma_store):
    repo = make_git_repo()
    repo.write("original.md", "line of text\n" * 60)
    repo.commit()
    source = make_source(repo.path, name="alpha")
    sync_source(source, context)

    repo.move("original.md", "renamed.md")
    repo.write("renamed.md", "line of text\n" * 55 + "brand new ending\n" * 5)
    repo.commit("rename and edit")

    result = sync_source(source, context)

    assert result.candidates == ("renamed.md",)
    assert result.purged == ("original.md",)
    assert _keys(chroma_store) == {"@source/alpha/renamed.md"}
    documents = " ".join(_documents(chroma_store, "@source/alpha/renamed.md"))
    assert "brand new ending" in documents


def test_an_irrelevant_commit_does_not_touch_chroma(tmp_path, make_git_repo, make_source,
                                                    context, chroma_store, state_store):
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha", include=("**/*.md",))
    sync_source(source, context)
    before = _fingerprint(chroma_store)

    repo.write("Makefile", "all:\n\techo hi\n")
    commit = repo.commit("a build file, not admitted")

    result = sync_source(source, context)

    assert result.status is SyncStatus.SYNCED
    assert result.did_work is False
    assert _fingerprint(chroma_store) == before
    assert state_store.get_checkpoint("alpha").last_revision == commit


def test_a_filesystem_source_synchronizes_and_settles(tmp_path, make_source, context,
                                                      chroma_store, state_store):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "one.md").write_text("# One\n\nFirst note.\n", encoding="utf-8")
    source = make_source(tmp_path, name="notes", type=SourceType.FILESYSTEM, ref=None)

    first = sync_source(source, context)
    assert first.revision_kind is RevisionKind.CONTENT
    assert _keys(chroma_store) == {"@source/notes/notes/one.md"}

    second = sync_source(source, context)
    assert second.status is SyncStatus.NO_CHANGE
    assert state_store.get_checkpoint("notes").last_revision == first.current_revision

    (tmp_path / "notes" / "two.md").write_text("# Two\n\nSecond note.\n", encoding="utf-8")
    third = sync_source(source, context)
    assert third.status is SyncStatus.SYNCED
    assert third.revision_kind is RevisionKind.CONTENT
    assert _keys(chroma_store) == {
        "@source/notes/notes/one.md", "@source/notes/notes/two.md",
    }


def test_a_rename_with_unchanged_content_is_still_a_change_for_a_filesystem_source(
    tmp_path, make_source, context, chroma_store
):
    """No history to diff, so the path is part of the digest — and must be."""
    (tmp_path / "old.md").write_text("# Same\n\nIdentical words.\n", encoding="utf-8")
    source = make_source(tmp_path, name="notes", type=SourceType.FILESYSTEM, ref=None)
    sync_source(source, context)
    assert _keys(chroma_store) == {"@source/notes/old.md"}

    (tmp_path / "old.md").rename(tmp_path / "new.md")
    result = sync_source(source, context)

    assert result.status is SyncStatus.SYNCED
    # The old key is gone because the full resync sweeps the source's scope,
    # not because anything could name it as removed: with a content digest
    # there is no per-path history, which is exactly why the sweep is scoped.
    assert _keys(chroma_store) == {"@source/notes/new.md"}


# ------------------------------------------------------------------- recovery ---

def test_an_interrupted_run_is_safe_to_rerun(tmp_path, make_git_repo, make_source,
                                             state_store, chroma_store,
                                             fake_embeddings):
    """A failure leaves the checkpoint behind; the retry converges, unduplicated."""
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha")
    good = SyncContext(store=state_store, chroma=chroma_store,
                       embeddings=fake_embeddings)
    sync_source(source, good)
    checkpoint = state_store.get_checkpoint("alpha")

    repo.write("a.md", "# Alpha\n\nRewritten.\n")
    repo.write("b.md", "# Beta\n\nNew.\n")
    commit = repo.commit("two changes")

    def explode(**kwargs):
        raise RuntimeError("the process was killed mid-run")

    interrupted = SyncContext(store=state_store, chroma=chroma_store,
                              embeddings=fake_embeddings, ingest=explode)
    failed = sync_source(source, interrupted)

    assert failed.status is SyncStatus.FAILED
    assert state_store.get_checkpoint("alpha").last_revision == checkpoint.last_revision

    retried = sync_source(source, good)

    assert retried.status is SyncStatus.SYNCED
    # The whole range since the last *successful* revision, because the
    # checkpoint never moved. Ingesting the same content twice reaches the
    # same state rather than duplicating it.
    assert retried.candidates == ("a.md", "b.md")
    assert state_store.get_checkpoint("alpha").last_revision == commit
    assert _keys(chroma_store) == {"@source/alpha/a.md", "@source/alpha/b.md"}

    # ...and "the same state" is meant literally: the recovered collection is
    # byte-for-byte what a source synchronized once, cleanly, would hold.
    reference_state = StateStore(tmp_path / "reference_state.db")
    try:
        reference_chroma = Chroma(
            collection_name="sync_reference",
            embedding_function=fake_embeddings,
            persist_directory=str(tmp_path / "reference_chroma"),
        )
        reference = SyncContext(store=reference_state, chroma=reference_chroma,
                                embeddings=fake_embeddings)
        assert sync_source(source, reference).status is SyncStatus.SYNCED
        assert _fingerprint(chroma_store) == _fingerprint(reference_chroma)
    finally:
        reference_state.close()


def test_two_sources_share_one_collection_without_interfering(
    tmp_path, make_git_repo, make_source, state_store, chroma_store, fake_embeddings
):
    first = make_git_repo("firstrepo")
    first.write("shared.md", "# First source's document\n\nAlpha content.\n")
    first.commit()
    second = make_git_repo("secondrepo")
    second.write("shared.md", "# Second source's document\n\nBeta content.\n")
    second.commit()

    registry = Registry(
        sources=(
            make_source(first.path, name="first"),
            make_source(second.path, name="second"),
        ),
        path=tmp_path / "sources.yaml",
    )
    context = SyncContext(store=state_store, chroma=chroma_store,
                          embeddings=fake_embeddings)

    run = sync_all(registry, context)

    assert run.ok
    assert _keys(chroma_store) == {"@source/first/shared.md", "@source/second/shared.md"}
    # The same relative path in two sources is two distinct documents.
    assert "Alpha content." in " ".join(_documents(chroma_store, "@source/first/shared.md"))
    assert "Beta content." in " ".join(_documents(chroma_store, "@source/second/shared.md"))


def test_the_corpus_is_not_disturbed_by_source_synchronization(
    tmp_path, make_git_repo, make_source, state_store, chroma_store, fake_embeddings
):
    """One collection, two populations, neither able to sweep the other."""
    corpus = tmp_path / "data"
    (corpus / "evidence" / "backend").mkdir(parents=True)
    (corpus / "evidence" / "backend" / "fastapi.md").write_text(
        "# FastAPI evidence\n\n## Evidence state\nVERIFIED\n\nA shipment API.\n",
        encoding="utf-8",
    )
    run_ingestion(data_dir=corpus, embeddings=fake_embeddings, store=chroma_store)
    corpus_state = _fingerprint(chroma_store, only=_corpus_only)
    assert corpus_state, "the isolation claim is vacuous without corpus rows"

    repo = make_git_repo()
    repo.write("app.py", "# App\n\nSource content.\n")
    repo.write("gone.md", "# Gone\n\nWill be swept.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha")
    context = SyncContext(store=state_store, chroma=chroma_store,
                          embeddings=fake_embeddings)
    sync_source(source, context)

    repo.remove("gone.md")
    repo.commit("delete")
    result = sync_source(source, context)
    assert result.full_resync is False and result.purged == ("gone.md",)

    keys = _keys(chroma_store)
    assert "evidence/backend/fastapi.md" in keys
    assert "@source/alpha/app.py" in keys
    assert "@source/alpha/gone.md" not in keys
    # Every corpus row is byte-identical to before the source existed here.
    assert _fingerprint(chroma_store, only=_corpus_only) == corpus_state


# ------------------------------------------------------------------- milestone ---

def test_milestone_two_syncs_of_an_unchanged_source_leave_chroma_identical(
    tmp_path, make_git_repo, make_source, context, chroma_store, state_store
):
    """PLAN.md Step 3 §18: not log output — a deterministic comparison.

    The collection is read back, in full, including the stored embeddings, and
    the two snapshots must be equal. An idempotent pipeline is what makes that
    true; a no-op no-change path is what makes it *cheap*.
    """
    repo = make_git_repo()
    repo.write("docs/a.md", "# A\n\nFirst document.\n")
    repo.write("docs/b.md", "# B\n\nSecond document.\n")
    repo.write("src/c.py", "# C\n\nA module with a function.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha")

    sync_source(source, context)
    checkpoint = state_store.get_checkpoint("alpha")
    first = _fingerprint(chroma_store)
    assert first, "the milestone is vacuous if nothing was indexed"

    second_result = sync_source(source, context)
    second = _fingerprint(chroma_store)

    assert second_result.status is SyncStatus.NO_CHANGE
    assert second == first
    # ...and the checkpoint is byte-identical too: a no-change sync writes
    # nothing at all, not even a fresh timestamp.
    assert state_store.get_checkpoint("alpha") == checkpoint

    # A third pass, for the same reason a second is not enough on its own:
    # a pipeline that mutated on every other run would still pass with two.
    sync_source(source, context)
    assert _fingerprint(chroma_store) == first


def test_milestone_holds_after_a_change_settles(tmp_path, make_git_repo, make_source,
                                                context, chroma_store):
    """Two syncs of a *changed-then-quiet* source converge, too."""
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nWords.\n")
    repo.commit()
    source = make_source(repo.path, name="alpha")
    sync_source(source, context)

    repo.write("a.md", "# Alpha\n\nDifferent words entirely.\n")
    repo.commit()
    sync_source(source, context)
    settled = _fingerprint(chroma_store)

    assert sync_source(source, context).status is SyncStatus.NO_CHANGE
    assert _fingerprint(chroma_store) == settled


def test_a_completed_project_still_receives_its_new_commits(tmp_path, make_git_repo,
                                                            make_source, context,
                                                            chroma_store, state_store):
    """Lifecycle governs priority, never visibility."""
    repo = make_git_repo()
    repo.write("legacy.md", "# Legacy\n\nFinished long ago.\n")
    repo.commit()
    source = make_source(repo.path, name="done", lifecycle=LifecycleState.COMPLETED)
    sync_source(source, context)

    repo.write("legacy.md", "# Legacy\n\nOne more commit after all.\n")
    repo.commit("revived")

    result = sync_source(source, context)

    assert result.needs_review
    assert result.ingestion["files_updated"] == 1
    assert "One more commit after all." in " ".join(
        _documents(chroma_store, "@source/done/legacy.md")
    )
    # The declaration is untouched; only the signal changed.
    assert state_store.get_source_lifecycle("done") is None
