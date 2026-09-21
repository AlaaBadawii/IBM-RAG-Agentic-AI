"""Step 3: the ingestion seam that candidate mode added.

Two modes, one indexing loop. These tests pin down both: that corpus mode
still behaves exactly as it did, and that candidate mode indexes a set, removes
a set, and sweeps a scope — without ever reimplementing how a file becomes
vectors.
"""
import pytest
from langchain_chroma import Chroma

from app.errors import IngestionError
from app.ingestion.loader import SourceFile
from app.ingestion.pipeline import run_ingestion
from app.sync.candidates import SourceCandidate, candidate_files, purge_keys
from app.sync.namespace import source_key, source_namespace


def _candidate(key: str, path) -> SourceCandidate:
    """A candidate whose stored key is spelled out, as the sync layer does."""
    return SourceCandidate(
        path=path,
        relative_path=key,
        source_name=key.split("/")[1],
        source_relative_path=key.split("/", 2)[2],
    )


def _write(tmp_path, relative: str, text: str):
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def _stored_keys(store) -> set[str]:
    result = store.get(include=["metadatas"])
    return {meta["source"] for meta in result["metadatas"] if meta}


def _corpus_store(tmp_path, fake_embeddings, name="corpus"):
    return Chroma(
        collection_name=f"seam_{name}_{tmp_path.name.replace('.', '_').replace('-', '_')}",
        embedding_function=fake_embeddings,
        persist_directory=str(tmp_path / f"chroma_{name}"),
    )


# ------------------------------------------------------------- argument guard ---

def test_purge_without_candidates_is_refused(tmp_path, chroma_store, fake_embeddings):
    """Corpus mode sweeps the whole collection; a named purge means nothing."""
    with pytest.raises(ValueError):
        run_ingestion(embeddings=fake_embeddings, store=chroma_store, purge=["a"])


def test_scope_without_candidates_is_refused(tmp_path, chroma_store, fake_embeddings):
    with pytest.raises(ValueError):
        run_ingestion(embeddings=fake_embeddings, store=chroma_store, scope="@source/")


# -------------------------------------------------------------- candidate mode ---

def test_candidate_mode_indexes_only_what_it_is_given(tmp_path, chroma_store,
                                                      fake_embeddings):
    first = _write(tmp_path, "a.md", "# Alpha\n\nSome words.\n")
    second = _write(tmp_path, "b.md", "# Beta\n\nOther words.\n")

    stats = run_ingestion(
        embeddings=fake_embeddings, store=chroma_store,
        candidates=[_candidate("@source/s/a.md", first)],
    )
    assert stats["files_discovered"] == 1
    assert stats["files_added"] == 1
    assert _stored_keys(chroma_store) == {"@source/s/a.md"}
    assert second.exists()  # never read, never indexed


def test_candidate_mode_is_idempotent(tmp_path, chroma_store, fake_embeddings):
    path = _write(tmp_path, "a.md", "# Alpha\n\nSome words.\n")
    candidate = _candidate("@source/s/a.md", path)

    first = run_ingestion(embeddings=fake_embeddings, store=chroma_store,
                          candidates=[candidate])
    second = run_ingestion(embeddings=fake_embeddings, store=chroma_store,
                           candidates=[candidate])
    assert first["files_added"] == 1
    assert second["files_added"] == 0
    assert second["files_updated"] == 0
    assert second["files_unchanged"] == 1
    assert second["total_chunks_in_store"] == first["total_chunks_in_store"]


def test_candidate_mode_leaves_the_rest_of_the_collection_alone(tmp_path,
                                                                fake_embeddings):
    """The corpus and a source share a collection; neither may sweep the other."""
    store = _corpus_store(tmp_path, fake_embeddings)
    corpus = tmp_path / "corpus"
    _write(corpus, "evidence/backend/fastapi.md", "# FastAPI\n\nEvidence.\n")
    run_ingestion(data_dir=corpus, embeddings=fake_embeddings, store=store)
    corpus_keys = _stored_keys(store)
    assert corpus_keys == {"evidence/backend/fastapi.md"}

    path = _write(tmp_path, "a.md", "# Alpha\n\nSource content.\n")
    run_ingestion(embeddings=fake_embeddings, store=store,
                  candidates=[_candidate("@source/ai/a.md", path)],
                  scope=source_namespace("ai"))

    assert _stored_keys(store) == corpus_keys | {"@source/ai/a.md"}


def test_candidate_mode_does_not_sweep_without_a_scope(tmp_path, chroma_store,
                                                       fake_embeddings):
    """No scope means no sweep: a partial candidate set must not clear the rest.

    This is the trap the scope argument exists to avoid — a diff submits only
    what changed, and sweeping against it would delete every file the revision
    did not happen to touch.
    """
    first = _write(tmp_path, "a.md", "# Alpha\n\nSome words.\n")
    second = _write(tmp_path, "b.md", "# Beta\n\nOther words.\n")
    run_ingestion(embeddings=fake_embeddings, store=chroma_store,
                  candidates=[_candidate("@source/s/a.md", first),
                              _candidate("@source/s/b.md", second)])
    assert len(_stored_keys(chroma_store)) == 2

    run_ingestion(embeddings=fake_embeddings, store=chroma_store,
                  candidates=[_candidate("@source/s/a.md", first)])
    assert _stored_keys(chroma_store) == {"@source/s/a.md", "@source/s/b.md"}


def test_scope_sweep_removes_stale_keys_under_that_prefix_only(tmp_path,
                                                               fake_embeddings):
    store = _corpus_store(tmp_path, fake_embeddings)
    corpus = tmp_path / "corpus"
    _write(corpus, "evidence/x.md", "# X\n\nCorpus content.\n")
    run_ingestion(data_dir=corpus, embeddings=fake_embeddings, store=store)

    keep = _write(tmp_path, "keep.md", "# Keep\n\nKept.\n")
    stale = _write(tmp_path, "stale.md", "# Stale\n\nWill be swept.\n")
    other = _write(tmp_path, "other.md", "# Other\n\nAnother source.\n")
    run_ingestion(embeddings=fake_embeddings, store=store, candidates=[
        _candidate("@source/ai/keep.md", keep),
        _candidate("@source/ai/stale.md", stale),
        _candidate("@source/web/other.md", other),
    ])

    stale.unlink()
    stats = run_ingestion(
        embeddings=fake_embeddings, store=store,
        candidates=[_candidate("@source/ai/keep.md", keep)],
        scope=source_namespace("ai"),
    )
    assert stats["files_removed"] == 1
    # The other source's key and the corpus file survive: "@source/ai/" cannot
    # match "@source/web/..." precisely because the prefix ends at a separator.
    assert _stored_keys(store) == {
        "evidence/x.md", "@source/ai/keep.md", "@source/web/other.md",
    }


def test_a_scoped_sweep_relinquishes_a_content_address_before_a_rename_claims_it(
    tmp_path, chroma_store, fake_embeddings
):
    """The sweep is a removal, so it belongs before the adds, like the purge.

    A full resync of a source submits the inventory and lets the sweep remove
    what is no longer in it — so a file renamed without any change to its bytes
    arrives as a new key holding the old key's content address. Sweeping after
    indexing would delete the chunks the new key had just claimed, and since a
    scoped sweep only runs on a cycle that then advances a checkpoint, that
    content would be gone for good rather than merely delayed.
    """
    old = _write(tmp_path, "old.md", "# Same\n\nIdentical words.\n")
    run_ingestion(embeddings=fake_embeddings, store=chroma_store,
                  candidates=[_candidate("@source/s/old.md", old)],
                  scope=source_namespace("s"))
    assert _stored_keys(chroma_store) == {"@source/s/old.md"}

    new = tmp_path / "new.md"
    old.rename(new)
    stats = run_ingestion(
        embeddings=fake_embeddings, store=chroma_store,
        candidates=[_candidate("@source/s/new.md", new)],
        scope=source_namespace("s"),
    )

    assert stats["files_skipped_duplicate_content"] == 0
    assert stats["files_removed"] == 1
    assert _stored_keys(chroma_store) == {"@source/s/new.md"}
    got = chroma_store.get(where={"source": "@source/s/new.md"}, include=["documents"])
    assert got["ids"], "the content has to survive the sweep, under the new key"


# ------------------------------------------------------------------- purging ---

def test_purge_removes_a_key_before_indexing(tmp_path, chroma_store, fake_embeddings):
    gone = _write(tmp_path, "gone.md", "# Gone\n\nContent.\n")
    run_ingestion(embeddings=fake_embeddings, store=chroma_store,
                  candidates=[_candidate("@source/s/gone.md", gone)])
    assert _stored_keys(chroma_store) == {"@source/s/gone.md"}

    stats = run_ingestion(embeddings=fake_embeddings, store=chroma_store,
                          candidates=[], purge=["@source/s/gone.md"])
    assert stats["files_removed"] == 1
    assert stats["chunks_removed"] > 0
    assert _stored_keys(chroma_store) == set()


def test_purging_an_unknown_key_is_a_no_op(tmp_path, chroma_store, fake_embeddings):
    stats = run_ingestion(embeddings=fake_embeddings, store=chroma_store,
                          candidates=[], purge=["@source/s/never-seen.md"])
    assert stats["files_removed"] == 0


def test_exact_rename_is_purged_then_claimed_by_the_new_key(tmp_path, chroma_store,
                                                           fake_embeddings):
    """The purge-before-add ordering, which is the whole reason it is that way.

    An exact rename keeps the content address, so the old key's ids and the new
    key's ids are the same. Deleting *after* adding would remove the chunks the
    new path had just claimed; deleting first leaves them present under the new
    key, with the chunk count unchanged.
    """
    old = _write(tmp_path, "old.md", "# Document\n\nIdentical bytes.\n")
    before = run_ingestion(embeddings=fake_embeddings, store=chroma_store,
                           candidates=[_candidate("@source/s/old.md", old)])
    count_before = before["total_chunks_in_store"]

    new = tmp_path / "new.md"
    old.rename(new)
    stats = run_ingestion(
        embeddings=fake_embeddings, store=chroma_store,
        candidates=[_candidate("@source/s/new.md", new)],
        purge=["@source/s/old.md"],
    )

    assert _stored_keys(chroma_store) == {"@source/s/new.md"}
    assert stats["total_chunks_in_store"] == count_before
    # The content is retrievable under the new key, which is the point.
    got = chroma_store.get(where={"source": "@source/s/new.md"}, include=["documents"])
    assert got["ids"]
    assert "Identical bytes." in got["documents"][0]


# ------------------------------------------------- identical content, two files ---

def test_identical_content_in_two_files_is_indexed_once_and_reported(
    tmp_path, chroma_store, fake_embeddings
):
    """Chroma's key space cannot hold two files under one content address.

    The first path in order keeps it and the second is skipped — deterministically,
    and out loud. The alternative, letting the write overwrite, makes which file
    the index attributes the content to depend on which run happened last, so the
    two trade places on every full re-scan.
    """
    first = _write(tmp_path, "a.md", "# Same\n\nIdentical words.\n")
    second = _write(tmp_path, "b.md", "# Same\n\nIdentical words.\n")

    stats = run_ingestion(embeddings=fake_embeddings, store=chroma_store, candidates=[
        _candidate("@source/s/a.md", first),
        _candidate("@source/s/b.md", second),
    ])

    assert stats["files_added"] == 1
    assert stats["files_skipped_duplicate_content"] == 1
    assert _stored_keys(chroma_store) == {"@source/s/a.md"}


def test_identical_content_does_not_swap_on_a_second_run(tmp_path, chroma_store,
                                                         fake_embeddings):
    """Two consecutive scans reach the same state, not each other's."""
    first = _write(tmp_path, "a.md", "# Same\n\nIdentical words.\n")
    second = _write(tmp_path, "b.md", "# Same\n\nIdentical words.\n")
    candidates = [_candidate("@source/s/a.md", first), _candidate("@source/s/b.md", second)]

    run_ingestion(embeddings=fake_embeddings, store=chroma_store, candidates=candidates)
    after_first = _stored_keys(chroma_store)
    run_ingestion(embeddings=fake_embeddings, store=chroma_store, candidates=candidates)

    assert _stored_keys(chroma_store) == after_first == {"@source/s/a.md"}


def test_the_collision_guard_is_off_for_the_corpus(tmp_path, fake_embeddings):
    """Corpus mode keeps the behaviour it has always had."""
    store = _corpus_store(tmp_path, fake_embeddings)
    corpus = tmp_path / "corpus"
    _write(corpus, "one.md", "# Same\n\nIdentical words.\n")
    _write(corpus, "two.md", "# Same\n\nIdentical words.\n")

    stats = run_ingestion(data_dir=corpus, embeddings=fake_embeddings, store=store)
    assert stats["files_skipped_duplicate_content"] == 0


# ------------------------------------------------------------------- loading ---

def test_an_unreadable_candidate_fails_the_cycle(tmp_path, chroma_store,
                                                 fake_embeddings):
    """Indexing part of a candidate set would let a checkpoint advance past a
    file that never reached the index."""
    directory = tmp_path / "not-a-file"
    directory.mkdir()
    with pytest.raises(IngestionError):
        run_ingestion(
            embeddings=fake_embeddings, store=chroma_store,
            candidates=[SourceFile(path=directory, relative_path="@source/s/d.md")],
        )


def test_content_hash_makes_an_unchanged_candidate_a_no_op(tmp_path, chroma_store,
                                                           fake_embeddings):
    """Git is the pre-filter; the content hash is the final check."""
    path = _write(tmp_path, "a.md", "# Alpha\n\nSome words.\n")
    candidate = _candidate("@source/s/a.md", path)
    run_ingestion(embeddings=fake_embeddings, store=chroma_store, candidates=[candidate])
    before = chroma_store.get(include=["metadatas"])["ids"]

    # A "change" that leaves the cleaned text identical: trailing whitespace and
    # a blank-line run are both normalised away by clean_text.
    path.write_text("# Alpha\n\n\n\nSome words.   \n", encoding="utf-8")
    stats = run_ingestion(embeddings=fake_embeddings, store=chroma_store,
                          candidates=[candidate])

    assert stats["files_unchanged"] == 1
    assert stats["files_updated"] == 0
    assert stats["chunks_added"] == 0
    assert chroma_store.get(include=["metadatas"])["ids"] == before


# ---------------------------------------------------------- candidate_files ---

def test_candidate_files_namespaces_every_key(tmp_path, make_source):
    _write(tmp_path, "docs/guide.md", "guide")
    source = make_source(tmp_path, name="my-source")

    files = candidate_files(source, ["docs/guide.md"])
    assert files[0].relative_path == source_key("my-source", "docs/guide.md")
    assert files[0].category == "my-source"
    assert files[0].domain is None
    assert files[0].path == tmp_path / "docs" / "guide.md"


def test_candidate_files_refuses_a_path_that_escapes_the_source(tmp_path,
                                                                make_source):
    source = make_source(tmp_path)
    (tmp_path / ".." / "outside.md").write_text("nope")
    with pytest.raises(Exception):
        candidate_files(source, ["../outside.md"])


def test_candidate_files_refuses_a_path_that_is_not_a_file(tmp_path, make_source):
    source = make_source(tmp_path)
    (tmp_path / "adir").mkdir()
    with pytest.raises(Exception):
        candidate_files(source, ["adir"])


def test_purge_keys_names_paths_the_way_they_are_stored(tmp_path, make_source):
    """A source-relative path would match nothing and remove nothing, silently.

    The pipeline removes a key by looking it up in the collection, where every
    source key is namespaced, and deleting a key that is not there is not an
    error — so getting this wrong loses no exception, only content.
    """
    source = make_source(tmp_path, name="my-source")
    assert purge_keys(source, ["old.md", "nested/gone.py"]) == (
        "@source/my-source/old.md",
        "@source/my-source/nested/gone.py",
    )


def test_a_raw_path_would_not_have_matched(tmp_path, chroma_store, fake_embeddings):
    """The regression this translation exists to prevent."""
    path = _write(tmp_path, "gone.md", "# Gone\n\nContent.\n")
    run_ingestion(embeddings=fake_embeddings, store=chroma_store,
                  candidates=[_candidate("@source/s/gone.md", path)])

    stats = run_ingestion(embeddings=fake_embeddings, store=chroma_store,
                          candidates=[], purge=["gone.md"])
    assert stats["files_removed"] == 0, "a raw path matches no stored key"
    assert _stored_keys(chroma_store) == {"@source/s/gone.md"}
