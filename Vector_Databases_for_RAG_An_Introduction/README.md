# Course 3 — Vector Databases for RAG: An Introduction

**Course status: Completed as of November 9, 2026 · Estimated duration: 9 hours**

[← Certificate overview](../README.md)

Three source-bearing projects explore **ChromaDB** and **SentenceTransformers** (`all-MiniLM-L6-v2`) for semantic search over books, food, and employee records. A fourth entry, Job Description Matcher, is plan-only. Food search contains implementation limitations described in its README; course completion does not imply that every extension is finished.

The course progresses from pure semantic search through metadata filtering to combined semantic + metadata queries, showing how vector databases power modern RAG systems.

---

## Projects

| Directory | State | Documentation |
|---|---|---|
| `Books_Advanced_Search` | Implemented modular search; print-based exercises | [README](Books_Advanced_Search/README.md) |
| `Food_Recommendation_System` | Experimental multi-script search/RAG lab; code blockers remain | [README](Food_Recommendation_System/README.md) |
| `Similarity_Search_on_Employee_Records` | Implemented in-memory search lab | [README](Similarity_Search_on_Employee_Records/README.md) |
| `job_description_matcher` | Plan only; no dataset or Python implementation | [README](job_description_matcher/README.md) |

## Main Learning Objectives

- Create collections, ingest documents, and compare persistent and in-memory clients.
- Separate searchable text from structured metadata.
- Combine semantic queries with metadata constraints.
- Understand that distance depends on collection configuration, not just the embedding model.
- Evaluate retrieval behavior without confusing demonstration scripts with assertion-based tests.

### Books Advanced Search (`Books_Advanced_Search/`)

A modular Python application that stores 8 book records in ChromaDB, generates embeddings, and enables semantic similarity search combined with structured metadata filtering. Demonstrates clean layered architecture: data → documents → vector_store → repository → search service.

- **8 books** across Classic, Dystopian, Fantasy, and Science Fiction genres
- **Layered architecture** with clear separation of concerns — `data/books.py`, `app/config.py`, `app/documents.py`, `app/vector_store.py`, `app/repository.py`, `app/search.py`
- **Persistent ChromaDB storage** via `chromadb.PersistentClient` (`storage/chroma/`)
- **Idempotent ingestion** using `upsert` — safe to run repeatedly
- **Four search patterns** across five exercise functions: similarity search, genre filtering (`$in`), rating filtering (`$gte`), combined semantic + metadata search
- Collection name and persist directory come from `app/config.py`; the embedding model is hardcoded in `app/vector_store.py` despite an unused model-name constant in config
- 384-dimensional embeddings via `all-MiniLM-L6-v2`; the book collection does not explicitly set cosine distance

### Food Recommendation System (`Food_Recommendation_System/`)

A progression from interactive semantic search to cuisine/calorie filtering and a watsonx-backed RAG chatbot over **185 committed food records**. Extra scripts explore calorie budgets, result limits, and response-style comparison.

- In-memory Chroma collections and local `all-MiniLM-L6-v2` embeddings.
- `enhanced_rag_chatbot.py` targets `ibm/granite-4-h-small` with Skills Network configuration, not OpenRouter.
- No environment variables are read by the source. Setting `LLM_*` variables does not configure the chatbot.
- Working-directory assumptions, inconsistent metadata keys, an undefined filtered-search helper, and an unresolved `List` annotation limit execution. See the [project limitations](Food_Recommendation_System/README.md#known-implementation-limitations).

### Job Description Matcher (`job_description_matcher/`)

A **planned** semantic job-search extension. Only `README.md`, `plan.md`, and `requirements.txt` are tracked. The proposed dataset, ingestion, CLI, evaluation, and optional LLM summary are not implemented.

- Proposed ~30 records across 8 technical categories.
- Planned evaluation with Hit@K and Precision@K, query experiments, and metadata filters.
- Planned search → vector-store layering and an optional LCEL summary step (RAG-lite).

### Similarity Search on Employee Records (`Similarity_Search_on_Employee_Records/`)

A ChromaDB-based demonstration of semantic similarity search and metadata filtering on employee records. A single-file application (`similarity_employeedata.py`) with a companion data module.

- **Employee records** with role, department, experience, skills, location, and employment type
- **6 demonstration searches**: 2 pure similarity searches, 3 metadata filters, 1 combined search
- **Metadata filtering** — department (exact match), experience (`$gte`), location (`$in`), combined with `$and`
- **Combined search** — senior Python developers in major tech cities with 8+ years experience
- Pure `chromadb.Client()` (non-persistent) for simplicity
- Documents combine role, experience, department, skills, location, and employment type into a single searchable text string

---

## Tech Stack

Only libraries actually imported in source code:

- **Python** 3.10+
- **chromadb** — persistent client in Books; in-memory clients in Food and Employee Records
- **sentence-transformers** (`all-MiniLM-L6-v2`) — 384-dimensional embeddings
- **Pydantic**, **python-dotenv** — book result models and legacy data-module loading
- **ibm-watsonx-ai** — Food RAG script (Skills Network configuration)
- **pytest** — optional runner for the Books exercises
- **torch** — required by sentence-transformers

---

## What's Built

- Source implementations for three ChromaDB domains, with Food execution limitations documented
- Semantic similarity search using `collection.query(query_texts=[...], n_results=...)`
- Metadata filtering using `collection.get(where=...)` with operators: `$in`, `$gte`, `$lte`, `$and`, `$or`
- Combined semantic + metadata search using `collection.query(query_texts=[...], n_results=..., where=...)`
- Document construction strategies — combining multiple fields into effective searchable text strings
- Hit@K and Precision@K are planned in Job Matcher, not implemented evaluation results
- Clean layered architecture in Books Advanced Search (data → documents → vector_store → repository → search service)
- Persistent and in-memory ChromaDB storage modes demonstrated

---

## ChromaDB where filter operators

| Operator | Example | Description |
|---|---|---|
| Exact match | `{"genre": "Fantasy"}` | Equal to value |
| Greater than or equal | `{"rating": {"$gte": 4.3}}` | Greater than or equal |
| Less than or equal | `{"year": {"$lte": 2000}}` | Less than or equal |
| In list | `{"genre": {"$in": ["Fantasy", "Sci-Fi"]}}` | Value in list |
| And | `{"$and": [cond1, cond2]}` | All conditions must match |
| Or | `{"$or": [cond1, cond2]}` | At least one condition matches |

---

## Setup / Run

Dependency packaging differs by project. Books has a two-package manifest; Food and Employee Records have no tracked dependency manifest. Job Matcher has a manifest but no application to run.

For Books, from the repository root:

```bash
cd Vector_Databases_for_RAG_An_Introduction/Books_Advanced_Search
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pip install python-dotenv pydantic pytest
```

The additional packages cover source imports and the optional pytest runner that are not explicitly declared in the Books manifest. See each project README for its own setup.

### Run commands

Run from the working directory named in each row:

| Working directory (relative to repository root) | Command | Notes |
|---|---|---|
| `Vector_Databases_for_RAG_An_Introduction/Books_Advanced_Search` | `python -m scripts.run_search` | Runs the five print-based search exercises; `app.run_search` is only an ingestion helper |
| `Vector_Databases_for_RAG_An_Introduction/Similarity_Search_on_Employee_Records` | `python similarity_employeedata.py` | Six in-memory demonstrations |
| `Vector_Databases_for_RAG_An_Introduction/Food_Recommendation_System` | `python app/interactive_search.py` | Actual entry point; subject to the project's documented metadata limitations |

Job Matcher has no execution command because `cli.py` is not tracked.

- The three source-bearing projects use `all-MiniLM-L6-v2` embeddings (downloaded automatically on first run); Job Matcher only proposes them
- Books Advanced Search persists data to `storage/chroma/` — survives restarts
- Employee Records uses an in-memory ChromaDB client (data is lost on exit)

### Environment variables

| Project | Variables |
|---|---|
| `Books_Advanced_Search` | No API key; leave the legacy, unparsed `BOOKS_DATA` override unset |
| `Food_Recommendation_System` | None read; the hosted RAG script has fixed Skills Network configuration |
| `job_description_matcher` | No implementation/configuration reader yet |
| `Similarity_Search_on_Employee_Records` | None required |

### Known issues

- **First-run download** — the embedding model (~80MB) downloads automatically on first run. Requires internet access. Subsequent runs use the cached version.
- **torch dependency** — `sentence-transformers` requires `torch`, which is a large package. Ensure sufficient disk space and a compatible Python version.
- **In-memory vs persistent** — Employee Records uses `chromadb.Client()` (in-memory). Restarting the script recreates the collection from scratch. Books Advanced Search uses `chromadb.PersistentClient()` for persistence.
- **Distance metric** — Employee Records explicitly requests cosine; Books and Food do not. The embedding model does not select the collection's metric. Cosine distance is `1 − cosine similarity` (0 identical, 1 orthogonal, 2 opposite).
- **Semantic results are non-deterministic** — do not assert exact ranking in tests unless the embedding model and configuration are explicitly fixed. Prefer behavioral assertions (results returned, count within limits, metadata present).

## Engineering Lessons

- Normalize metadata consistently before ingestion and use those exact keys in filters and result formatting.
- Books has five print-based exercise functions across three test files, with no assertion-based retrieval checks; they are not evidence of verified ranking or coverage.
- Keep proposed datasets and evaluation targets in the plan-only category until the implementation exists.
