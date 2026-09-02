# Books Advanced Search — Semantic Search with ChromaDB

A Python application that stores book records in **ChromaDB**, generates embeddings using **SentenceTransformers** (`all-MiniLM-L6-v2`), and enables natural-language semantic search combined with structured metadata filtering.

This project is part of **Course 3 — Vector Databases for RAG: An Introduction** (IBM RAG and Agentic AI Professional Certificate). It follows the IBM lab progression from document storage through similarity search with metadata filtering.

---

## 1. What this project does

1. **Stores** 8 book records in ChromaDB with rich metadata (title, author, genre, year, rating, pages)
2. **Generates** embeddings using `all-MiniLM-L6-v2` (SentenceTransformers) — 384-dimensional vectors
3. **Enables** semantic similarity search — find books by meaning, not just keywords
4. **Provides** metadata filtering (genre, rating, year, pages) using ChromaDB `where` clauses
5. **Combines** semantic search with metadata constraints for refined results
6. **Demonstrates** clean architecture — data, documents, vector store, repository, and search service layers

### Core philosophy

> "You're not just learning: 'Chroma returns similar documents.' You're learning: 'What does my embedding model consider semantically similar?'"

---

## 2. Dataset

Books are defined in `data/books.py` (`books`). Each record contains:

| Field | Description |
|---|---|
| `id` | Unique identifier (e.g., `book_1`) |
| `title` | Book title |
| `author` | Author name |
| `genre` | Genre (Classic, Dystopian, Fantasy, Science Fiction) |
| `year` | Publication year (integer) |
| `rating` | Average rating (float) |
| `pages` | Page count (integer) |
| `description` | Short description |
| `themes` | Comma-separated themes |
| `setting` | Setting description |

### Searchable text vs. metadata

This is a critical distinction:

- **Searchable text** (`documents` in Chroma): the free-text string that gets embedded. Combines title, author, description, themes, setting, genre, and year.
- **Metadata** (`metadatas` in Chroma): structured fields used for filtering, not semantic matching.

```python
# What gets embedded (searchable text):
"The Lord of the Rings by J.R.R. Tolkien.
An epic fantasy quest to destroy a powerful ring and save Middle-earth.
Themes: heroism, friendship, good vs evil, power corruption.
Setting: Middle-earth, fantasy realm.
Genre: Fantasy.
Published in 1954."

# What gets stored as metadata (for filtering):
{"title": "The Lord of the Rings", "author": "J.R.R. Tolkien", "genre": "Fantasy", "year": 1954, "rating": 4.5, "pages": 1216}
```

---

## 3. Search capabilities demonstrated

### Pure similarity search

```python
collection.query(query_texts=["magical fantasy adventure with friendship and courage"], n_results=3)
```

Finds the 3 most similar books based on semantic embedding of the query.

### Metadata filtering

```python
# Genre filtering using $in
collection.get(where={"genre": {"$in": ["Fantasy", "Science Fiction"]}})

# Rating filtering using $gte
collection.get(where={"rating": {"$gte": 4.3}})

# Combined with $and
collection.get(where={"$and": [{"year": {"$gte": 1990}}, {"year": {"$lte": 1999}}]})
```

### Combined search: similarity + metadata filtering

```python
collection.query(
    query_texts=["dystopian society control oppression future"],
    n_results=3,
    where={"rating": {"$gte": 4.0}}
)
```

Finds the most similar dystopian books with a rating of at least 4.0.

---

## 4. Project structure

```
Books_Advanced_Search/
├── README.md              # This file
├── PLAN.md                # Detailed 39-phase implementation plan
├── requirements.txt
├── .gitignore
├── data/
│   ├── __init__.py
│   └── books.py           # Book dataset (8 records)
├── app/
│   ├── __init__.py
│   ├── config.py          # Configuration constants
│   ├── documents.py       # Document and metadata builders
│   ├── vector_store.py    # ChromaDB client and collection management
│   ├── repository.py      # BookRepository — CRUD + search + filter
│   ├── search.py          # BookSearchService — search orchestration
│   └── run_search.py      # Ingestion helper
├── scripts/               # Runner scripts (placeholder)
├── storage/
│   └── chroma/            # Persistent ChromaDB storage (chroma.sqlite3)
└── tests/
    └── __init__.py
```

---

## 5. Architecture

The application follows a layered architecture with clear separation of concerns:

```
                          ┌─────────────────┐
                          │   Book Dataset  │
                          │  data/books.py  │
                          └────────┬────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │    Documents    │
                          │ documents.py    │
                          └────────┬────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │   Repository    │
                          │ repository.py   │
                          └────────┬────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │    ChromaDB     │
                          │  Vector Store   │
                          └────────┬────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │ Search Service  │
                          │   search.py     │
                          └────────┬────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │    CLI / API    │
                          │  run_search.py  │
                          └─────────────────┘
```

### Module responsibilities

| Module | Responsibility |
|---|---|
| `data/books.py` | Book dataset — isolated from all application logic |
| `app/config.py` | Centralized configuration (collection name, persist directory, embedding model) |
| `app/documents.py` | Converts books to semantic documents and structured metadata |
| `app/vector_store.py` | ChromaDB client creation and collection retrieval |
| `app/repository.py` | Abstraction over ChromaDB operations (add, get, search, filter, upsert, update, delete) |
| `app/search.py` | Application-level search service — delegates to repository |
| `app/run_search.py` | Ingestion helper |

### Dependency direction

```
CLI / Runner
  ↓
Search Service
  ↓
Repository
  ↓
Vector Store
  ↓
ChromaDB
```

---

## 6. Key configuration

| Constant | Value | Purpose |
|---|---|---|
| `COLLECTION_NAME` | `"books"` | Chroma collection name |
| `PERSIST_DIRECTORY` | `"storage/chroma"` | Persistent storage directory (survives restarts) |
| `EMBEDDING_MODEL_NAME` | `"all-MiniLM-L6-v2"` | 384-dim embeddings, trained on 1B sentence pairs |

---

## 7. Setup

**Requirements:** Python 3.10+, internet access for downloading the embedding model on first run.

```bash
cd Books_Advanced_Search
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt`:
```
chromadb
sentence-transformers
```

---

## 8. Usage

### Ingest books into ChromaDB

```python
from app.repository import BookRepository
from data.books import books
from app.run_search import ingest_books

repository = BookRepository()
ingest_books(repository, books)
```

The `upsert_book` method ensures idempotent ingestion — running multiple times will not create duplicate records.

### Search similar books

```python
repository = BookRepository()
results = repository.search_books("magical fantasy adventure with friendship and courage", n_results=3)
```

Returns a list of dictionaries with `id`, `document`, and `metadata` fields.

### Filter by metadata

```python
# Genre filtering
results = repository.filter_books({"genre": {"$in": ["Fantasy", "Science Fiction"]}})

# Rating filtering
results = repository.filter_books({"rating": {"$gte": 4.3}})
```

### Combined search via repository

```python
results = repository.search_books(
    "dystopian society control oppression future",
    n_results=3
)
# Then filter results by rating in application code, or use ChromaDB's
# combined query capability via the repository's underlying collection
```

---

## 9. How it works

1. **Embedding function** — `SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")` converts text into 384-dimensional vectors using cosine distance.
2. **Collection creation** — `client.get_or_create_collection()` creates or retrieves the `books` collection with the embedding function.
3. **Ingestion** — Each book is converted into a semantic document (via `build_book_document()`) and structured metadata (via `build_metadatas()`), then upserted via `collection.upsert()`.
4. **Search** — `collection.query()` accepts `query_texts`, `n_results`, and optional `where` filters, returning IDs, documents, metadatas, and distances.
5. **Filtering** — `collection.get()` with a `where` parameter retrieves documents matching metadata criteria (exact match, `$gte`, `$lte`, `$in`, `$and`, `$or`, etc.).

---

## 10. ChromaDB where filter operators

| Operator | Example | Description |
|---|---|---|
| Exact match | `{"genre": "Fantasy"}` | Equal to value |
| Greater than or equal | `{"rating": {"$gte": 4.3}}` | Greater than or equal |
| Less than or equal | `{"year": {"$lte": 2000}}` | Less than or equal |
| In list | `{"genre": {"$in": ["Fantasy", "Sci-Fi"]}}` | Value in list |
| And | `{"$and": [cond1, cond2]}` | All conditions must match |
| Or | `{"$or": [cond1, cond2]}` | At least one condition matches |

---

## 11. Key concepts practiced

- **ChromaDB collections** — creating, ingesting, and querying a persistent vector store
- **SentenceTransformer embeddings** — converting text to vectors with `SentenceTransformerEmbeddingFunction`
- **Cosine distance** — the distance metric used; 0 = identical, 1 = opposite
- **Document construction** — combining multiple fields into an effective searchable text string
- **Metadata filtering** — using `where` clauses in `collection.get()` for structured filtering
- **Combined search** — using `where` in `collection.query()` to filter semantic results
- **Idempotent ingestion** — using `upsert` so repeated runs don't create duplicates
- **Persistent storage** — `chromadb.PersistentClient` survives application restarts
- **Separation of concerns** — data, documents, vector store, repository, and search layers are isolated

---

## 12. Ideas to extend

- Add a CLI runner script (`scripts/run_search.py`) that executes all four exercises: similarity search, genre filtering, rating filtering, and combined search
- Add a `display.py` module for formatted console output (rank, title, author, genre, distance)
- Add `models.py` with `BookSearchResult` dataclass for application-level result representation
- Add unit tests under `tests/` for document generation, metadata validation, and filtering behavior
- Add more books to test retrieval quality across a larger dataset
- Experiment with different embedding models (`all-MiniLM-L12-v2`, `mp-net`) and compare results
- Build a Gradio or Streamlit UI for interactive search
- Add decade filtering (e.g., books published during the 1990s)
- Add page count filtering (e.g., books between 250 and 400 pages)
- Add environment variable configuration (`CHROMA_PERSIST_DIRECTORY`, `CHROMA_COLLECTION_NAME`)
- Add Python `logging` instead of `print()` statements
- Add input validation and error handling for missing or invalid book data
- Implement a FastAPI layer to expose search as a REST API
