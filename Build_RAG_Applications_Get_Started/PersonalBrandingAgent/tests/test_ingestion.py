"""Tests for ingestion: loader, metadata, chunker, pipeline behavior.

The pipeline tests use a tiny synthetic data/ tree (tmp_path) and the
FakeEmbeddings from conftest — no network, no model downloads.
"""
from pathlib import Path

import pytest
from langchain_chroma import Chroma

from app.ingestion.chunker import chunk_document, chunk_id, clean_text, content_hash
from app.ingestion.loader import SourceFile, discover_markdown
from app.ingestion.metadata import DocumentMetadata, extract_metadata
from app.ingestion.pipeline import run_ingestion


# ---------------------------------------------------------------- loader ---

def test_discover_markdown_finds_files_recursively(tmp_path):
    (tmp_path / "evidence" / "backend").mkdir(parents=True)
    (tmp_path / "evidence" / "backend" / "fastapi.md").write_text("# FastAPI")
    (tmp_path / "stories_lessons").mkdir(parents=True)
    (tmp_path / "stories_lessons" / "a_story.md").write_text("# Story")
    files = discover_markdown(tmp_path)
    relative = [f.relative_path for f in files]
    assert "evidence/backend/fastapi.md" in relative
    assert "stories_lessons/a_story.md" in relative


def test_discover_markdown_excludes_readmes_by_default(tmp_path):
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / "README.md").write_text("index")
    (tmp_path / "evidence" / "fastapi.md").write_text("content")
    files = discover_markdown(tmp_path)
    assert [f.relative_path for f in files] == ["evidence/fastapi.md"]


def test_discover_markdown_can_include_readmes(tmp_path):
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / "README.md").write_text("index")
    files = discover_markdown(tmp_path, exclude_readmes=False)
    assert len(files) == 1


def test_source_file_category_and_domain(tmp_path):
    (tmp_path / "evidence" / "backend").mkdir(parents=True)
    f = tmp_path / "evidence" / "backend" / "fastapi.md"
    f.write_text("x")
    src = SourceFile(path=f, relative_path="evidence/backend/fastapi.md")
    assert src.category == "evidence"
    assert src.domain == "backend"
    # domain only exists for evidence/ subdirectories
    src2 = SourceFile(path=f, relative_path="stories_lessons/a.md")
    assert src2.domain is None


def test_discover_markdown_missing_dir_returns_empty(tmp_path):
    assert discover_markdown(tmp_path / "nope") == []


# -------------------------------------------------------------- metadata ---

def _make_source(tmp_path, relative: str) -> SourceFile:
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    return SourceFile(path=path, relative_path=relative)


def test_metadata_extracts_evidence_state(tmp_path):
    src = _make_source(tmp_path, "evidence/backend/fastapi.md")
    text = "# FastAPI\n\n## Evidence state\nVERIFIED (repo exists).\n"
    meta = extract_metadata(src, text, "hash123")
    assert meta.evidence_state == "VERIFIED"
    assert meta.category == "evidence"
    assert meta.domain == "backend"
    assert meta.document_type == "evidence"


def test_metadata_extracts_status_completed(tmp_path):
    src = _make_source(tmp_path, "completed_projects/taskey.md")
    text = "## Status\nCOMPLETED (implemented, run locally)\n"
    meta = extract_metadata(src, text, "h")
    assert meta.status == "COMPLETED"
    assert meta.document_type == "project"


def test_metadata_extracts_status_in_progress(tmp_path):
    src = _make_source(tmp_path, "in_progress_projects/quizey_v2.md")
    text = "## Status\nIN PROGRESS. The re-architecture of the old project.\n"
    meta = extract_metadata(src, text, "h")
    assert meta.status == "IN PROGRESS"


def test_metadata_leaves_unset_fields_none(tmp_path):
    src = _make_source(tmp_path, "vision_goals/my_vision.md")
    meta = extract_metadata(src, "# Vision\n\nNarrative text.\n", "h")
    assert meta.status is None
    assert meta.evidence_state is None
    assert meta.document_type == "vision"


def test_metadata_ignores_unknown_status_vocabulary(tmp_path):
    src = _make_source(tmp_path, "audit/cross_source_audit.md")
    # "## Status (2026): ..." style headings must not invent a status.
    meta = extract_metadata(src, "## Status (2026)\nAll items covered.\n", "h")
    assert meta.status is None


def test_metadata_project_slug_for_quizey_stories(tmp_path):
    src = _make_source(tmp_path, "stories_lessons/quizey_idempotency.md")
    meta = extract_metadata(src, "## Status\nCOMPLETED\n", "h")
    assert meta.project == "quizey"


def test_chroma_metadata_drops_none(tmp_path):
    meta = DocumentMetadata(source="a.md", category="audit")
    chroma_meta = meta.to_chroma_metadata()
    assert "domain" not in chroma_meta
    assert "status" not in chroma_meta
    assert chroma_meta["document_type"] == "unknown"


def test_metadata_on_real_corpus_evidence_file(tmp_path):
    """Spot-check against the actual knowledge base file."""
    from app.paths import DATA_DIR
    real = DATA_DIR / "evidence" / "backend" / "fastapi.md"
    if not real.exists():
        pytest.skip("real corpus not present")
    src = SourceFile(path=real, relative_path="evidence/backend/fastapi.md")
    meta = extract_metadata(src, real.read_text(), "h")
    assert meta.category == "evidence"
    assert meta.domain == "backend"
    assert meta.evidence_state in {"VERIFIED", "DOCUMENTED", "IN_PROGRESS"}


# --------------------------------------------------------------- chunker ---

def test_clean_text_collapses_blank_lines():
    assert clean_text("a\n\n\n\nb\n\n") == "a\n\nb\n"


def test_content_hash_is_stable_and_sensitive():
    assert content_hash("a") == content_hash("a")
    assert content_hash("a") != content_hash("b")


def test_chunk_deterministic_ids():
    h = content_hash("some text")
    assert chunk_id(h, 0) == f"{h}:0"
    assert chunk_id(h, 3) == f"{h}:3"


def test_chunking_respects_size(tmp_path):
    text = ("word " * 400).strip()  # ~2000 chars
    chunks = chunk_document(text, chunk_size=500, chunk_overlap=50)
    assert len(chunks) > 1
    assert all(len(c.page_content) <= 600 for c in chunks)  # splitter soft limit


# -------------------------------------------------------------- pipeline ---

def _make_kb(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    (data / "evidence" / "backend").mkdir(parents=True)
    (data / "evidence" / "README.md").write_text("evidence index\n")
    (data / "evidence" / "backend" / "fastapi.md").write_text(
        "# FastAPI evidence\n\n## Evidence state\nVERIFIED\n\nBuilt a FastAPI shipment API.\n"
    )
    (data / "stories_lessons").mkdir()
    (data / "stories_lessons" / "quizey_idempotency.md").write_text(
        "# Quizey idempotency\n\n## Status\nCOMPLETED\n\nRetry-safe request handling lesson.\n"
    )
    return data


def _store_for(tmp_path, fake_embeddings):
    return Chroma(
        collection_name=f"test_{tmp_path.name}",
        embedding_function=fake_embeddings,
        persist_directory=str(tmp_path / "chroma"),
    )


def test_pipeline_ingests_and_is_idempotent(tmp_path, fake_embeddings):
    data = _make_kb(tmp_path)
    store = _store_for(tmp_path, fake_embeddings)
    stats1 = run_ingestion(data_dir=data, embeddings=fake_embeddings, store=store)
    assert stats1["files_discovered"] == 2  # README excluded
    assert stats1["files_added"] == 2
    assert stats1["total_chunks_in_store"] > 0

    stats2 = run_ingestion(data_dir=data, embeddings=fake_embeddings, store=store)
    assert stats2["files_added"] == 0
    assert stats2["files_updated"] == 0
    assert stats2["files_unchanged"] == 2
    assert stats2["total_chunks_in_store"] == stats1["total_chunks_in_store"]


def test_pipeline_reingests_changed_file_only(tmp_path, fake_embeddings):
    data = _make_kb(tmp_path)
    store = _store_for(tmp_path, fake_embeddings)
    run_ingestion(data_dir=data, embeddings=fake_embeddings, store=store)

    changed = data / "evidence" / "backend" / "fastapi.md"
    original = changed.read_text()
    changed.write_text(original + "\nExtra: SQLAlchemy and Alembic migrations work.\n")
    stats = run_ingestion(data_dir=data, embeddings=fake_embeddings, store=store)
    assert stats["files_updated"] == 1
    assert stats["files_unchanged"] == 1
    assert stats["total_chunks_in_store"] >= stats["total_chunks_in_store"]


def test_pipeline_removes_stale_vectors(tmp_path, fake_embeddings):
    data = _make_kb(tmp_path)
    store = _store_for(tmp_path, fake_embeddings)
    run_ingestion(data_dir=data, embeddings=fake_embeddings, store=store)
    before = store._collection.count()

    (data / "stories_lessons" / "quizey_idempotency.md").unlink()
    stats = run_ingestion(data_dir=data, embeddings=fake_embeddings, store=store)
    assert stats["files_removed"] == 1
    assert stats["chunks_removed"] > 0
    assert store._collection.count() < before


def test_pipeline_metadata_reaches_chroma(tmp_path, fake_embeddings):
    data = _make_kb(tmp_path)
    store = _store_for(tmp_path, fake_embeddings)
    run_ingestion(data_dir=data, embeddings=fake_embeddings, store=store)
    result = store.get(where={"source": "evidence/backend/fastapi.md"})
    assert result["ids"]
    metas = store.get(where={"source": "evidence/backend/fastapi.md"},
                      include=["metadatas"])["metadatas"]
    assert metas[0]["category"] == "evidence"
    assert metas[0]["domain"] == "backend"
    assert metas[0]["evidence_state"] == "VERIFIED"


# ------------------------------------------------------- zero-chunk files ---

def _watch_add_documents(monkeypatch, store):
    """Record every store write; the store must never see an empty batch."""
    original = store.add_documents
    calls = []

    def spy(documents, ids=None, **kwargs):
        calls.append((list(documents), list(ids or [])))
        return original(documents, ids=ids, **kwargs)

    monkeypatch.setattr(store, "add_documents", spy)
    return calls


def test_pipeline_skips_zero_byte_file_without_failing(tmp_path, fake_embeddings,
                                                       monkeypatch):
    """A 0-byte admitted file cleans to zero chunks: skipped, not fatal.

    Before the guard this reached ``add_documents([], ids=[])`` and Chroma
    rejected the empty embeddings list, failing the whole cycle with
    ``IngestionError`` while the checkpoint never advanced.
    """
    data = _make_kb(tmp_path)
    (data / "evidence" / "backend" / "empty.md").write_text("")
    store = _store_for(tmp_path, fake_embeddings)
    writes = _watch_add_documents(monkeypatch, store)

    stats = run_ingestion(data_dir=data, embeddings=fake_embeddings, store=store)

    assert stats["files_added"] == 2
    assert stats["files_skipped_empty"] == 1
    assert stats["total_chunks_in_store"] > 0
    assert writes, "the non-empty files must still reach the store"
    assert all(documents and ids for documents, ids in writes)
    assert store.get(where={"source": "evidence/backend/empty.md"})["ids"] == []

    # A second run over the same tree is equally safe: the empty file is
    # skipped again rather than crashing idempotency.
    rerun = run_ingestion(data_dir=data, embeddings=fake_embeddings, store=store)
    assert rerun["files_skipped_empty"] == 1
    assert rerun["total_chunks_in_store"] == stats["total_chunks_in_store"]


def test_pipeline_skips_whitespace_only_file_without_failing(tmp_path,
                                                             fake_embeddings,
                                                             monkeypatch):
    """Whitespace-only content cleans to ``"\\n"``, which also chunks to zero."""
    data = _make_kb(tmp_path)
    (data / "evidence" / "backend" / "blank.md").write_text("   \n  \n\t\n")
    store = _store_for(tmp_path, fake_embeddings)
    writes = _watch_add_documents(monkeypatch, store)

    stats = run_ingestion(data_dir=data, embeddings=fake_embeddings, store=store)

    assert stats["files_added"] == 2
    assert stats["files_skipped_empty"] == 1
    assert stats["total_chunks_in_store"] > 0
    assert all(documents and ids for documents, ids in writes)
    assert store.get(where={"source": "evidence/backend/blank.md"})["ids"] == []
