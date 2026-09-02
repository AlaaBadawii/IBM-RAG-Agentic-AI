# Course 3 — Vector Databases for RAG: An Introduction

**Status: Completed**

Three projects demonstrating core vector database concepts using **ChromaDB** and **SentenceTransformers** (`all-MiniLM-L6-v2`) for semantic search with metadata filtering. All projects share the same tech stack and learning objectives but apply them to different domains: books, job descriptions, and employee records.

The course progresses from pure semantic search through metadata filtering to combined semantic + metadata queries, showing how vector databases power modern RAG systems.

---

## Projects

### Books Advanced Search (`Books_Advanced_Search/`)

A modular Python application that stores 8 book records in ChromaDB, generates embeddings, and enables semantic similarity search combined with structured metadata filtering. Demonstrates clean layered architecture: data → documents → vector_store → repository → search service.

- **8 books** across Classic, Dystopian, Fantasy, and Science Fiction genres
- **Layered architecture** with clear separation of concerns — `data/books.py`, `app/config.py`, `app/documents.py`, `app/vector_store.py`, `app/repository.py`, `app/search.py`
- **Persistent ChromaDB storage** via `chromadb.PersistentClient` (`storage/chroma/`)
- **Idempotent ingestion** using `upsert` — safe to run repeatedly
- **Four search exercises**: similarity search, genre filtering (`$in`), rating filtering (`$gte`), combined semantic + metadata search
- **Configurable** collection name, persist directory, and embedding model via `app/config.py`
- 384-dimensional embeddings with cosine distance via `all-MiniLM-L6-v2`

### Job Description Matcher (`job_description_matcher/`)

A semantic job search application storing ~30 job descriptions in ChromaDB with rich metadata (title, company, location, category, description). Enables natural-language semantic search with metadata filtering and evaluation metrics.

- **~30 job records** across 8 technical categories (Backend, Frontend, Data, DevOps, Mobile, AI/ML, Security, Full Stack)
- **Evaluation framework** — Hit@K, Precision@K metrics to measure retrieval quality
- **Search experimentation** — run queries, record results, analyze surprising or bad matches
- **Combined search** — semantic similarity with metadata filters (category, location)
- **Architecture refactor path** — separates concerns into search → vector_store → ChromaDB layers
- Optional LLM phase — uses LangChain LCEL to generate natural-language summaries of top-matching jobs (RAG-lite)

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
- **chromadb** — vector database for all three projects (persistent client in Books Advanced Search, in-memory client in Employee Records)
- **sentence-transformers** (`all-MiniLM-L6-v2`) — 384-dimensional embeddings with cosine distance
- **pytest** — testing (Books Advanced Search)
- **torch** — required by sentence-transformers

---

## What's Built

- Three runnable ChromaDB applications across different domains
- Semantic similarity search using `collection.query(query_texts=[...], n_results=...)`
- Metadata filtering using `collection.get(where=...)` with operators: `$in`, `$gte`, `$lte`, `$and`, `$or`
- Combined semantic + metadata search using `collection.query(query_texts=[...], n_results=..., where=...)`
- Document construction strategies — combining multiple fields into effective searchable text strings
- Evaluation metrics (Hit@K, Precision@K) in job_description_matcher
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

Each project is self-contained with its own `requirements.txt` and uses environment variables for secrets where applicable. **Never commit `.env` files.**

```bash
cd Vector_Databases_for_RAG_An_Introduction/<project>
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` for all three projects:
```
chromadb
sentence-transformers
torch
```

### Run commands

```bash
# Books Advanced Search — ingest and search
cd Vector_Databases_for_RAG_An_Introduction/Books_Advanced_Search
python3 -m app.run_search

# Job Description Matcher — see cli.py for ingest and search commands
cd Vector_Databases_for_RAG_An_Introduction/job_description_matcher
python cli.py ingest
python cli.py search "Python backend engineer with FastAPI"

# Similarity Search on Employee Records
cd Vector_Databases_for_RAG_An_Introduction/Similarity_Search_on_Employee_Records
python similarity_employeedata.py
```

- All projects use `all-MiniLM-L6-v2` embeddings (downloaded automatically on first run)
- Books Advanced Search persists data to `storage/chroma/` — survives restarts
- Employee Records uses an in-memory ChromaDB client (data is lost on exit)

### Environment variables

| Project | Variables |
|---|---|
| `Books_Advanced_Search` | None required (uses `all-MiniLM-L6-v2` directly) |
| `job_description_matcher` | None required for basic search; evaluation may need config |
| `Similarity_Search_on_Employee_Records` | None required |

### Known issues

- **First-run download** — the embedding model (~80MB) downloads automatically on first run. Requires internet access. Subsequent runs use the cached version.
- **torch dependency** — `sentence-transformers` requires `torch`, which is a large package. Ensure sufficient disk space and a compatible Python version.
- **In-memory vs persistent** — Employee Records uses `chromadb.Client()` (in-memory). Restarting the script recreates the collection from scratch. Books Advanced Search uses `chromadb.PersistentClient()` for persistence.
- **Distance metric** — `all-MiniLM-L6-v2` uses cosine distance (0 = identical, 1 = opposite). Results may vary slightly depending on ChromaDB version and default distance metric.
- **Semantic results are non-deterministic** — do not assert exact ranking in tests unless the embedding model and configuration are explicitly fixed. Prefer behavioral assertions (results returned, count within limits, metadata present).
