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
"""
from pathlib import Path

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
                  store: Chroma = None) -> dict:
    """Execute the full ingestion cycle. Returns a stats dict."""
    data_dir = data_dir or config.DATA_DIR
    setup_logging()
    try:
        files = discover_markdown(data_dir)
        loaded = load_all(files)
        store = store or get_vector_store(embeddings or get_embeddings())
        stored = _stored_hashes(store)

        stats = {
            "files_discovered": len(files),
            "files_added": 0,
            "files_updated": 0,
            "files_unchanged": 0,
            "files_removed": 0,
            "chunks_added": 0,
            "chunks_updated": 0,
            "chunks_removed": 0,
        }

        current_sources = set()
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
            # Delete old chunks of this source first (ids change when
            # content changes) then add the new ones.
            if existing_ids:
                store.delete(ids=existing_ids)
                stats["files_updated"] += 1
                stats["chunks_removed"] += len(existing_ids)
                stats["chunks_updated"] += len(chunk_documents)
            else:
                stats["files_added"] += 1
                stats["chunks_added"] += len(chunk_documents)
            store.add_documents(chunk_documents, ids=ids)
            logger.info("Ingested %s (%d chunks)", source.relative_path, len(chunk_documents))

        # Stale removal: sources in Chroma that no longer exist on disk.
        for source_path, ids in stored.items():
            if source_path not in current_sources:
                store.delete(ids=ids)
                stats["files_removed"] += 1
                stats["chunks_removed"] += len(ids)
                logger.info("Removed stale vectors for %s (%d chunks)", source_path, len(ids))

        total = store._collection.count()
        stats["total_chunks_in_store"] = total
        logger.info("Ingestion complete: %s", stats)
        return stats
    except IngestionError:
        raise
    except Exception as exc:
        raise IngestionError(f"Ingestion failed: {exc}") from exc


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
