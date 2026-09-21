"""Ingestion pipeline: data/ -> persistent Chroma.

Run from the repository root (works from any CWD):

    python -m app.ingestion.pipeline

Guarantees:
    - Deterministic IDs: <sha256 of cleaned text>:<chunk index>.
    - Idempotent: re-running with unchanged data/ touches nothing
      (verified by comparing content_hash in stored metadata).
    - Change-aware: only files whose hash changed are re-embedded.
    - Stale-aware: vectors whose source file no longer exists are deleted.

Stats are printed and returned as a dict.

This module is the **only** place content reaches Chroma. The synchronization
layer decides *what* changed (`PLAN.md` Step 3); it hands the raw material to
:func:`run_ingestion` and everything below that — cleaning, hashing, chunking,
embedding, ids, metadata, and stale removal — happens here, once, unchanged.
There is deliberately no second indexing path: a second implementation of
"how a file becomes vectors" is a second set of idempotency and staleness
rules, and two of those will eventually disagree.
"""
from pathlib import Path
from typing import Sequence

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from app import config
from app.errors import IngestionError
from app.ingestion.chunker import chunk_document, chunk_id, clean_text, content_hash
from app.ingestion.loader import SourceFile, discover_markdown, load_all
from app.ingestion.metadata import extract_metadata
from app.logging_config import get_logger, setup_logging
from app.paths import CHROMA_DIR, ensure_runtime_dirs

logger = get_logger(__name__)


def get_embeddings():
    """Local HuggingFace embeddings (all-MiniLM-L6-v2 by default).

    Lazy + cached: loading the model takes seconds and only the pipeline
    and retrieval strategies need it.
    """
    global _EMBEDDINGS_CACHE
    if _EMBEDDINGS_CACHE is None:
        logger.info("Loading embedding model %s", config.EMBEDDING_MODEL)
        _EMBEDDINGS_CACHE = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
    return _EMBEDDINGS_CACHE


_EMBEDDINGS_CACHE = None


def get_vector_store(embeddings=None) -> Chroma:
    """Open (creating if needed) the persistent Chroma collection."""
    ensure_runtime_dirs()
    return Chroma(
        collection_name=config.CHROMA_COLLECTION,
        embedding_function=embeddings or get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )


def _stored_hashes(store: Chroma) -> dict[str, list[str]]:
    """Map source path -> list of stored chunk ids, from Chroma metadata."""
    stored: dict[str, list[str]] = {}
    # Chroma.get paginates internally; the KB is small (~hundreds of chunks).
    result = store.get(include=["metadatas"])
    for chunk_id, meta in zip(result["ids"], result["metadatas"]):
        if meta and "source" in meta:
            stored.setdefault(meta["source"], []).append(chunk_id)
    return stored


def run_ingestion(data_dir: Path = None, embeddings=None,
                  store: Chroma = None, *,
                  candidates: Sequence[SourceFile] | None = None,
                  purge: Sequence[str] = (),
                  scope: str | None = None) -> dict:
    """Execute an ingestion cycle. Returns a stats dict.

    Two modes, one implementation:

    **Corpus mode** — ``candidates is None``, the default: the behaviour of
    this pipeline since Step 0, unchanged. Discover ``*.md`` under
    ``data_dir``, index them, then remove every stored source that no longer
    exists on disk.

    **Candidate mode** — ``candidates`` given: index exactly these files,
    remove exactly the keys in ``purge``, and, when ``scope`` is given, remove
    stored keys under that prefix which were not candidates. This is what the
    synchronization layer calls with what it worked out changed.

    Args:
        candidates: the files to index. Their ``relative_path`` is the stored
            key, so a caller names them the way it wants them retrieved.
        purge: stored keys to remove **before** indexing. The ordering is not
            cosmetic: ids are content-addressed (``<hash>:<index>``), so a
            rename that changes no bytes produces the same ids at the new
            path, and deleting after adding would remove the chunks the new
            path had just claimed.
        scope: a key prefix whose stale entries should be swept. Pass this
            only when ``candidates`` is a source's *complete* admitted set —
            the sweep removes everything in scope that is not a candidate, so
            a partial candidate set would delete that source's untouched
            files. Swept keys are removed before indexing, exactly like
            ``purge`` and for the same reason.

    Raises:
        ValueError: ``purge`` or ``scope`` given without ``candidates``. In
            corpus mode the scope is the whole collection and there is nothing
            to purge by name; accepting either silently would make the two
            modes mean different things by the same argument.
        IngestionError: the cycle failed. Never a partial success reported as
            one.
    """
    setup_logging()
    if candidates is None and (purge or scope is not None):
        raise ValueError(
            "purge and scope describe a candidate set, and are only meaningful "
            "with candidates=...; corpus ingestion's scope is the whole "
            "collection and it has nothing to purge by name"
        )
    try:
        if candidates is None:
            return _ingest_corpus(data_dir, embeddings, store)
        return _ingest_candidates(list(candidates), purge, scope, embeddings, store)
    except IngestionError:
        raise
    except Exception as exc:
        raise IngestionError(f"Ingestion failed: {exc}") from exc


def _new_stats(files_discovered: int) -> dict:
    """The stats dict, with the same keys in both modes.

    ``files_skipped_duplicate_content`` is always present and is always 0 in
    corpus mode: the condition it counts needs two admitted files with
    byte-identical cleaned text, which a curated corpus does not produce but a
    set of real repositories can.
    """
    return {
        "files_discovered": files_discovered,
        "files_added": 0,
        "files_updated": 0,
        "files_unchanged": 0,
        "files_removed": 0,
        "files_skipped_duplicate_content": 0,
        "chunks_added": 0,
        "chunks_updated": 0,
        "chunks_removed": 0,
    }


def _resolve_store(embeddings, store) -> Chroma:
    return store or get_vector_store(embeddings or get_embeddings())


def _index_documents(store: Chroma, loaded, stored: dict, stats: dict, *,
                     owned: dict[str, str] | None = None) -> set[str]:
    """Index loaded documents. The single place content reaches Chroma.

    Args:
        stored: stored key -> chunk ids, read once before this runs.
        owned: chunk id -> stored key, or ``None`` to skip duplicate-content
            detection. Only the candidate path passes it; see below.

    Returns:
        The set of stored keys this cycle accounted for.
    """
    current_sources: set[str] = set()
    for source, raw_text in loaded:
        current_sources.add(source.relative_path)
        text = clean_text(raw_text)
        doc_hash = content_hash(text)
        meta = extract_metadata(source, text, doc_hash)
        existing_ids = stored.get(source.relative_path, [])
        existing_hash = _hash_of_existing(store, existing_ids)

        if existing_ids and existing_hash == doc_hash:
            stats["files_unchanged"] += 1
            continue

        chunks = chunk_document(text)
        chunk_documents = [
            Document(page_content=chunk.page_content, metadata=meta.to_chroma_metadata())
            for chunk in chunks
        ]
        ids = [chunk_id(doc_hash, i) for i in range(len(chunk_documents))]

        if owned is not None and ids and ids[0] in owned:
            # Two admitted files with identical cleaned text share one content
            # address, and Chroma's key space cannot hold both. The first in
            # path order keeps it; the second is skipped and *reported*, because
            # the alternative — letting the write overwrite — makes which file
            # the index attributes the content to depend on which run happened
            # last, so the two files trade places on every full re-scan.
            stats["files_skipped_duplicate_content"] += 1
            logger.warning(
                "Skipped %s: its content is identical to %s, which already holds "
                "the same content address %s",
                source.relative_path, owned[ids[0]], ids[0],
            )
            continue

        # Delete old chunks of this source first (ids change when content
        # changes) then add the new ones.
        if existing_ids:
            store.delete(ids=existing_ids)
            stats["files_updated"] += 1
            stats["chunks_removed"] += len(existing_ids)
            stats["chunks_updated"] += len(chunk_documents)
            if owned is not None:
                for old_id in existing_ids:
                    owned.pop(old_id, None)
        else:
            stats["files_added"] += 1
            stats["chunks_added"] += len(chunk_documents)
        store.add_documents(chunk_documents, ids=ids)
        if owned is not None:
            for new_id in ids:
                owned[new_id] = source.relative_path
        logger.info("Ingested %s (%d chunks)", source.relative_path, len(chunk_documents))
    return current_sources


def _remove(store: Chroma, key: str, ids: list[str], stats: dict,
            why: str) -> None:
    """Delete one stored key's chunks, and count it. Ids are never empty."""
    store.delete(ids=ids)
    stats["files_removed"] += 1
    stats["chunks_removed"] += len(ids)
    logger.info("Removed %s (%d chunks) — %s", key, len(ids), why)


def _finish(store: Chroma, stats: dict) -> dict:
    stats["total_chunks_in_store"] = store._collection.count()
    logger.info("Ingestion complete: %s", stats)
    return stats


def _ingest_corpus(data_dir, embeddings, store) -> dict:
    data_dir = data_dir or config.DATA_DIR
    files = discover_markdown(data_dir)
    loaded = load_all(files)
    store = _resolve_store(embeddings, store)
    stored = _stored_hashes(store)
    stats = _new_stats(len(files))

    current_sources = _index_documents(store, loaded, stored, stats)

    # Stale removal: sources in Chroma that no longer exist on disk.
    for source_path, ids in stored.items():
        if source_path not in current_sources:
            _remove(store, source_path, ids, stats, "no longer on disk")
    return _finish(store, stats)


def _ingest_candidates(candidates: list[SourceFile], purge, scope,
                       embeddings, store) -> dict:
    loaded = load_all(candidates, strict=True)
    store = _resolve_store(embeddings, store)
    stored = _stored_hashes(store)
    stats = _new_stats(len(candidates))

    # Every removal happens before any addition. The purge is literally ordered
    # that way (see `purge` above); the scope sweep is a removal too, so it
    # belongs here rather than after indexing.
    for key in purge:
        ids = stored.pop(key, None)
        if ids:
            _remove(store, key, ids, stats, "no longer admitted by the source")

    if scope is not None:
        # A swept key is one that is in scope and is not in the inventory this
        # cycle was handed. Removing it after indexing would be too late for a
        # renamed file whose bytes did not change: the new key holds the same
        # content address, so the sweep would delete the chunks the new key had
        # just claimed — and this cycle then advances a checkpoint, so that
        # loss would be recorded as a success.
        kept = {candidate.relative_path for candidate in candidates}
        for key in [k for k in stored if k.startswith(scope) and k not in kept]:
            _remove(store, key, stored.pop(key), stats,
                    "no longer in the source's inventory")

    # What is still stored, and therefore whose content addresses are taken.
    owned: dict[str, str] = {}
    for key, ids in stored.items():
        for existing_id in ids:
            owned.setdefault(existing_id, key)

    _index_documents(store, loaded, stored, stats, owned=owned)
    return _finish(store, stats)


def _hash_of_existing(store: Chroma, ids: list[str]) -> str | None:
    """Look up the stored content_hash of an existing source's first chunk."""
    if not ids:
        return None
    result = store.get(ids=ids[:1], include=["metadatas"])
    metas = result.get("metadatas") or []
    if metas and metas[0]:
        return metas[0].get("content_hash")
    return None


def main() -> None:
    stats = run_ingestion()
    print("\n=== Ingestion report ===")
    print(f"  files discovered : {stats['files_discovered']}")
    print(f"  files added      : {stats['files_added']}")
    print(f"  files updated    : {stats['files_updated']}")
    print(f"  files unchanged  : {stats['files_unchanged']}")
    print(f"  files removed    : {stats['files_removed']}")
    print(f"  chunks added     : {stats['chunks_added']}")
    print(f"  chunks updated   : {stats['chunks_updated']}")
    print(f"  chunks removed   : {stats['chunks_removed']}")
    print(f"  total in store   : {stats['total_chunks_in_store']}")
    print(f"  store location   : {CHROMA_DIR}")


if __name__ == "__main__":
    main()
