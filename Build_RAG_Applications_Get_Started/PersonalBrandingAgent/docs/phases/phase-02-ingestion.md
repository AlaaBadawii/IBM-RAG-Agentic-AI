# Phase 2 — Knowledge Ingestion

## Goal

Turn the existing `data/` knowledge base into a structured, queryable vector
corpus in ChromaDB, preserving the directory hierarchy as semantic metadata.

## Why This Phase Exists

The `data/` directory is the real, structured source of truth and must not be
flattened. This phase makes it queryable: discover Markdown, extract reliable
metadata from the hierarchy and content, clean/normalize, chunk, embed, and
persist to Chroma. A repeatable, idempotent, change-aware pipeline is required
so the corpus stays in sync with the source files.

## Inputs

- `data/` (the full structured knowledge base, with per-category `README.md`
  index files)
- `app/config.py` (embedding model, chunk params, Chroma dir, data dir) from
  Phase 1
- `app/paths.py`, `app/logging_config.py`, `app/errors.py` from Phase 1

## Outputs

- A populated, persistent Chroma collection at `chroma_db/`
- An ingestion CLI (`python -m app.ingestion.pipeline` or similar) that prints
  stats (files, chunks, vectors, added/updated/removed)
- Document metadata derived from the hierarchy and content
- Idempotent + change-aware + stale-aware behavior

## Architecture

```text
data/
   ↓
Markdown discovery
   ↓
Document loading
   ↓
Metadata extraction
   ↓
Cleaning / normalization
   ↓
Chunking
   ↓
Embeddings
   ↓
ChromaDB
```

Metadata example (deliberately derived):

```python
{
    "source": "stories_lessons/quizey_exam_versioning.md",
    "category": "stories_lessons",
    "domain": "architecture",
    "document_type": "lesson",
    "status": "in_progress",
    "language": "en",
    "content_hash": "<sha256>",
}
```

```python
{
    "source": "evidence/backend/fastapi.md",
    "category": "evidence",
    "domain": "backend",
    "document_type": "evidence",
    "evidence_state": "IN_PROGRESS",
}
```

Only include metadata that can be **reliably derived**; leave a field unset
rather than guessing.

## Files Introduced

- `app/ingestion/__init__.py`
- `app/ingestion/loader.py` — Markdown discovery + loading
- `app/ingestion/metadata.py` — metadata extraction rules
- `app/ingestion/chunker.py` — chunking
- `app/ingestion/pipeline.py` — orchestration, idempotency, stale removal
- `tests/test_ingestion.py`, `tests/test_metadata.py`, `tests/test_chunker.py`

## Implementation Tasks

1. Implement Markdown discovery over `data/`, using `app/paths.py`.
2. Implement loading with `langchain_community.document_loaders` /
   `TextLoader` as appropriate.
3. Implement metadata extraction from the path (category, domain for
   `evidence/`, document_type) plus reliable content signals (status headings,
   evidence state, language). Keep the derivation rules explicit and testable.
4. Implement cleaning/normalization (whitespace, consistent separators).
5. Implement chunking with `RecursiveCharacterTextSplitter` using
   `CHUNK_SIZE` / `CHUNK_OVERLAP` from config.
6. Implement embedding with the local
   `sentence-transformers/all-MiniLM-L6-v2` model via `langchain-huggingface`.
7. Implement persistence to persistent Chroma at `chroma_db/`.
8. Implement change detection using a content hash stored in metadata; only
   re-embed changed documents.
9. Implement stale-vector removal: if a source file no longer exists, delete its
   vectors.
10. Provide a CLI that reports files/chunks/vectors added, updated, unchanged,
    and removed.

## Tests

- **Loader**: discovers all expected Markdown files across categories; respects
  the include/exclude policy for `README.md` files.
- **Metadata**: given sample files (e.g., an `evidence/backend/*.md` and a
  `stories_lessons/*.md`), metadata is derived as documented.
- **Chunker**: chunk sizes/overlap respect config; chunks of a file are
  contiguous and non-overlapping in content beyond the configured overlap.
- **Pipeline (idempotency)**: running twice produces the same vector set; no
  duplicate vectors for unchanged files.
- **Pipeline (change)**: editing a file re-embeds it; deleting a file removes
  its vectors.
- Use a fake/cheap embedding for pipeline tests to avoid heavy model downloads.

## Acceptance Criteria

- `python -m app.ingestion.pipeline` indexes `data/` and reports stats.
- Chroma persists to `chroma_db/` (gitignored).
- Re-running the pipeline is idempotent (no duplicates, no churn).
- Editing a file updates only that file's vectors.
- Deleting a file removes its vectors.
- Metadata is correct per the derivation rules; no invented metadata.
- Tests pass without live network/LLM.

## Failure Modes

- **No Markdown found** → clear warning; report zero files.
- **Embedding model unavailable** → explicit error; do not silently skip.
- **Chroma write failure** → error surfaced with partial-state report.
- **Deterministic ids** → use stable ids so re-runs don't duplicate.

## Security Considerations

- `chroma_db/` is gitignored.
- No secrets enter metadata or logs.
- If `data/` ever contains sensitive personal info, note that the corpus is
  local-only for now.

## Dependencies on Previous Phases

- Phase 1 (config, paths, logging, errors).

## Future Extensions

- Incremental ingestion via a file-watch/scheduler (ties to Phase 9).
- Richer metadata extraction from front matter / headings as conventions evolve.
- Corpus-level statistics and drift detection.

## Course Alignment

- Document loading, chunking, embeddings, and Chroma map directly to the IBM
  RAG labs (Phase 2 of the course: build RAG applications).

## Checklist

- [ ] Markdown discovery and loading over `data/` works
- [ ] Metadata extraction rules defined and tested
- [ ] Cleaning/normalization applied
- [ ] Chunking respects config
- [ ] Embeddings via local MiniLM model
- [ ] Persistent Chroma at `chroma_db/`
- [ ] Pipeline is idempotent and change-aware
- [ ] Stale vectors removed on file deletion
- [ ] CLI reports add/update/unchanged/remove stats
- [ ] Tests pass without network/LLM