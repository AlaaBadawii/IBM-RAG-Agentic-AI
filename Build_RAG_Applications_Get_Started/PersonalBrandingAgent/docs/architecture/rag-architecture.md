# RAG Architecture

## Role of RAG in the system

RAG is the **knowledge capability** of the Agent. It turns the version-controlled
Markdown knowledge base (`data/`) into a structured, queryable vector corpus and
returns grounded context for generation. RAG is *not* the Agent itself.

## Source of truth

`data/` is the version-controlled source of truth. The existing directory
hierarchy is **semantic** and must be preserved — it is not flattened or
replaced. It is a core input to metadata.

Top-level categories (each a semantic class):

```text
completed_projects     projects that are finished
in_progress_projects   active projects and their current state
in_progress_courses    learning programs being studied
certificates           completed-learning credentials
evidence               what can be publicly claimed, with evidence states
stories_lessons        reusable personal engineering stories and lessons
public_positioning     how the user presents himself publicly
vision_goals           the professional vision (source of truth for positioning)
writing_style          tone and rules for content (authoritative voice guide)
audit                  consistency audits of the KB (diagnostic, not facts)
```

`evidence/` further groups by domain: `ai/`, `backend/`, `devops/`, `learning/`,
`professional/`, `projects/`.

## Ingestion pipeline

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

Requirements on the pipeline:

- **Repeatable** — the same `data/` always produces the same corpus.
- **Deterministic where practical** — stable chunking, stable metadata, stable
  document ids.
- **Observable** — logs files discovered, chunks created, vectors upserted.
- **Idempotent** — re-running produces the same state; changed files update,
  unchanged files are untouched.
- **Change-aware** — detect changed files (content hash) and only re-embed what
  changed.
- **Stale-aware** — if a source file is deleted, its vectors are removed.

## Metadata model

Metadata is **deliberately designed** and only includes dimensions that can be
**reliably derived**. The directory hierarchy drives category and domain.

Core derived metadata:

```python
{
    "source": "stories_lessons/quizey_exam_versioning.md",
    "category": "stories_lessons",       # top-level directory
    "domain": "architecture",            # evidence subcategory / inferred theme
    "document_type": "lesson",           # project | course | certificate | story |
                                         # lesson | evidence | positioning | vision |
                                         # writing_style | audit
    "status": "in_progress",             # completed | in_progress | learning |
                                         # planned | aspirational | documented
    "language": "en",                    # derived from content, if reliable
    "content_hash": "<sha256>",          # for change detection
}
```

Optional metadata, only when it can be derived reliably:

```python
{
    "project": "Quizey V2",              # when a single project is identifiable
    "evidence_state": "VERIFIED",        # evidence/ files only
    "mtime": "2026-08-01T...",           # last-modified timestamp
}
```

Rules:

- Do not invent metadata that cannot be derived from the file path, front
  matter, headings, or reliable content patterns.
- `document_type` and `status` are derived from the category plus reliable
  content signals (e.g., `## Status: Completed`); where the signal is
  ambiguous, leave the field unset rather than guessing.
- The `README.md` files inside each category are reference/index documents and
  may be ingested (they carry category semantics) or excluded, as a deliberate
  policy decision — make the choice explicit and consistent.

## Evidence states and hierarchy

The KB already defines these (see `data/evidence/README.md` and
`data/audit/README.md`); the system adopts them as policy.

Evidence states:

```text
VERIFIED, DOCUMENTED, IN_PROGRESS, LEARNING, ASPIRATIONAL, UNVERIFIED, STALE
```

Default evidence hierarchy (highest first; a default policy, not an absolute
law):

```text
1. Evidence files (data/evidence/)
2. Project documentation
3. Course / certificate documentation
4. Stories / lessons
5. General positioning / portfolio
6. LLM inference (weakest; never used to manufacture evidence)
```

This default can be refined if the actual data suggests otherwise.

## Embeddings

- Model: `sentence-transformers/all-MiniLM-L6-v2` (local, free, no API cost).
- Embeddings run locally; the vector store is local Chroma (persistent).

## Vector store

- Chroma persistent at `chroma_db/` (gitignored).
- Collection(s) for personal knowledge. Operational memory (publication
  history) is intentionally **not** placed in the same collection.

## Retrieval engine

Not a thin `search(q, k=5)` wrapper. The retrieval subsystem supports:

- **semantic retrieval**
- **metadata-aware retrieval** (filters), from the start

```text
Query
 ↓
Query interpretation
 ↓
Filter construction
 ↓
Semantic retrieval
 ↓
Optional reranking
 ↓
Relevant documents
 ↓
Retrieval result object
```

Supported request shapes:

```text
Retrieve:
- FastAPI experience
- only evidence/project sources
- prioritize current information
```

```text
Retrieve:
- writing style rules
- public positioning
- relevant lessons
```

The retrieval result is a structured object (documents + metadata + scores +
the filters that were applied), so downstream components and the audit trail
know exactly what was used.

## Retrieval evaluation

Evaluation is a first-class concern. A small gold dataset of representative
queries is maintained, with the expected documents for each:

```text
"How much FastAPI experience do I have?"
"What happened when I implemented Quizey versioning?"
"What lessons can I discuss from Kubernetes?"
"What is my preferred LinkedIn writing style?"
"What projects demonstrate AI agent experience?"
```

See `../evaluation/retrieval-evaluation.md` for metrics and process.

## Files (target)

- `app/ingestion/loader.py` — Markdown discovery + loading
- `app/ingestion/chunker.py` — chunking
- `app/ingestion/metadata.py` — metadata extraction rules
- `app/ingestion/pipeline.py` — orchestration, idempotency, stale removal
- `app/retrieval/retriever.py` — vector search + result object
- `app/retrieval/filters.py` — metadata filter construction
- `app/retrieval/reranker.py` — optional reranking

## Related documents

- End-to-end flow: `data-flow.md`
- Branding context: `../phases/phase-04-branding-context.md` and `data-flow.md`
- Retrieval evaluation: `../evaluation/retrieval-evaluation.md`
- Ingestion phase: `../phases/phase-02-ingestion.md`
- Retrieval phase: `../phases/phase-03-retrieval.md`