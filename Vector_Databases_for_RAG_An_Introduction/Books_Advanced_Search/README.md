# Books Advanced Search — Semantic Search with ChromaDB

A Python application that stores book records in **ChromaDB**, generates embeddings using **SentenceTransformers** (`all-MiniLM-L6-v2`), and enables natural-language semantic search combined with structured metadata filtering.

This project is part of **Course 3 — Vector Databases for RAG: An Introduction** (IBM RAG and Agentic AI Professional Certificate). It follows the IBM lab progression from document storage through similarity search with metadata filtering.

**Status: Implemented search exercises with known limitations.** [Course 3](../README.md) · [Certificate](../../README.md)

---

## 1. What this project does

1. **Stores** 8 book records in ChromaDB with rich metadata (title, author, genre, year, rating, pages)
2. **Generates** embeddings using `all-MiniLM-L6-v2` (SentenceTransformers) — 384-dimensional vectors
3. **Enables** semantic similarity search — find books by meaning, not just keywords
4. **Provides** metadata filtering (genre, rating, year, author) using ChromaDB `where` clauses
5. **Combines** semantic search with metadata constraints for refined results
6. **Demonstrates** clean architecture — data, documents, vector store, repository, search service, models, and presentation layers

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

> **Note:** `data/books.py` calls `load_dotenv()` and reads `BOOKS_DATA` with the built-in list as its default. An environment value is a string and is not parsed into records. Leave `BOOKS_DATA` unset to use the eight committed books; no API key is needed.

### Searchable text vs. metadata

This is a critical distinction:

- **Searchable text** (`documents` in Chroma): the free-text string that gets embedded. Combines title, author, description, themes, setting, genre, year, and rating.
- **Metadata** (`metadatas` in Chroma): structured fields used for filtering, not semantic matching.

```python
# What gets embedded (searchable text):
"The Lord of the Rings by J.R.R. Tolkien.
An epic fantasy quest to destroy a powerful ring and save Middle-earth.
Themes: heroism, friendship, good vs evil, power corruption.
Setting: Middle-earth, fantasy realm.
Genre: Fantasy.
Published in 1954.
With a 4.5 rating."

# What gets stored as metadata (for filtering):
{"title": "The Lord of the Rings", "author": "J.R.R. Tolkien", "genre": "Fantasy", "year": 1954, "rating": 4.5, "pages": 1216}
```

---

## 3. Search capabilities demonstrated

### Pure similarity search

```python
from app.search import BookSearchService
from app.repository import BookRepository

service = BookSearchService(repository=BookRepository())
results = service.search_similar_books("magical fantasy adventure with friendship and courage", n_results=3)
```

Returns a list of `BookSearchResult` objects with `id`, `title`, `author`, `genre`, `year`, `rating`, and `distance` fields.

### Metadata filtering

```python
# Genre filtering using $in
service.filter_books({"genre": {"$in": ["Fantasy", "Science Fiction"]}})

# Rating filtering using $gte
service.filter_books({"rating": {"$gte": 4.3}})

# Semantic search with a rating filter
service.search_similar_books("dystopian society control oppression future", n_results=3, where={"rating": {"$gte": 4.0}})
```

### Combined search: similarity + metadata filtering

```python
results = service.search_similar_books(
    "dystopian society control oppression future",
    n_results=3,
    where={"rating": {"$gte": 4.0}}
)
```

Finds the most similar dystopian books with a rating of at least 4.0. Results are returned as `BookSearchResult` objects.

---

## 4. Project structure

```
Books_Advanced_Search/
├── README.md                  # This file
├── PLAN.md                    # Detailed implementation plan
├── requirements.txt
├── .gitignore
├── utils.py                   # Utility function: print_books()
├── data/
│   ├── __init__.py
│   └── books.py               # Book dataset (8 records)
├── app/
│   ├── __init__.py
│   ├── config.py              # Configuration constants
│   ├── documents.py           # Document and metadata builders
│   ├── vector_store.py        # ChromaDB client and collection management
│   ├── repository.py          # BookRepository — CRUD + search + filter
│   ├── search.py              # BookSearchService — search orchestration
│   ├── models.py              # BookSearchResult Pydantic model
│   ├── display.py             # Presentation functions
│   └── run_search.py          # Ingestion helper
├── scripts/
│   ├── __init__.py
│   └── run_search.py          # Test runner script
├── storage/
│   └── chroma/                # Persistent ChromaDB storage (chroma.sqlite3)
└── tests/
    ├── __init__.py
    ├── test_search_similar_books.py
    ├── test_filter_books.py
    └── test_combined_semantic_metadata_search.py
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
                         ┌──────────┴──────────┐
                         │                     │
                         ▼                     ▼
                  ┌──────────────┐      ┌──────────────┐
                  │   Models     │      │  Display      │
                  │  models.py   │      │  display.py   │
                  └──────────────┘      └──────────────┘
                                    │
                                    ▼
                           ┌─────────────────┐
                           │ Exercise Runner │
                           │ scripts/run_    │
                           │    search.py    │
                           └─────────────────┘
```

### Module responsibilities

| Module | Responsibility |
|---|---|
| `data/books.py` | Book dataset — isolated from all application logic |
| `app/config.py` | Collection name and persist directory; declares an unused embedding-model constant |
| `app/documents.py` | Converts books to semantic documents and structured metadata |
| `app/vector_store.py` | ChromaDB client creation and collection retrieval |
| `app/repository.py` | Abstraction over ChromaDB operations (add, get, search, filter, upsert, update, delete) |
| `app/search.py` | Application-level search service (`BookSearchService`) — delegates to repository, returns `BookSearchResult` |
| `app/models.py` | `BookSearchResult` Pydantic model for application-level result representation |
| `app/display.py` | Presentation functions (`display_similarity_results`) |
| `app/run_search.py` | `ingest_books()` helper |
| `utils.py` | `print_books()` utility used by tests |
| `scripts/run_search.py` | Test runner that executes all 5 test functions |

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
| `EMBEDDING_MODEL_NAME` | `"all-MiniLM-L6-v2"` | Declared but not read by `vector_store.py`, which hardcodes the same model ID |

---

## 7. Data model

### `BookSearchResult` (`app/models.py`)

The `BookSearchResult` Pydantic model represents a book result at the application level:

```python
class BookSearchResult(BaseModel):
    id: str
    title: str
    author: str
    genre: str
    year: int
    rating: float
    distance: float | None = None
```

- `distance` is `None` for metadata-only filter results (from `filter_books()`), and populated for similarity search results.
- The `BookSearchService.search_similar_books()` method converts raw ChromaDB result dictionaries into `BookSearchResult` objects.
- The `BookSearchService.filter_books()` method returns raw dictionaries (not `BookSearchResult` objects) — this is a known inconsistency.

---

## 8. Setup

**Requirements:** Python 3.10+, internet access for downloading the embedding model on first run. Start from the repository root:

```bash
cd Vector_Databases_for_RAG_An_Introduction/Books_Advanced_Search
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pip install python-dotenv pydantic pytest
```

`requirements.txt`:
```
chromadb
sentence-transformers
```

> The manifest declares only ChromaDB and sentence-transformers. `python-dotenv` and Pydantic are direct source imports; pytest is needed for the optional test runner. They are shown explicitly above rather than assuming transitive installation.

---

## 9. Usage

From the project root, the actual demonstration runner is:

```bash
python -m scripts.run_search
```

`app/run_search.py` only defines `ingest_books()`; `python -m app.run_search` does not ingest or display searches.

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
from app.search import BookSearchService
from app.repository import BookRepository

repository = BookRepository()
service = BookSearchService(repository=repository)
results = service.search_similar_books("magical fantasy adventure with friendship and courage", n_results=3)
```

Returns a list of `BookSearchResult` objects with `id`, `title`, `author`, `genre`, `year`, `rating`, and `distance` fields.

### Filter by metadata

```python
service = BookSearchService(repository=BookRepository())

# Genre filtering
results = service.filter_books({"genre": {"$in": ["Fantasy", "Science Fiction"]}})

# Rating filtering
results = service.filter_books({"rating": {"$gte": 4.3}})
```

Returns a list of raw dictionaries with `id`, `document`, and `metadata` fields.

### Display results

```python
from app.display import display_similarity_results

display_similarity_results(results)
```

---

## 10. How it works

1. **Embedding function** — `SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")` converts text into 384-dimensional vectors. The embedding function is instantiated at module level in `app/vector_store.py`; it does not set the distance metric.
2. **Collection creation** — `client.get_or_create_collection()` creates or retrieves the `books` collection with the embedding function. No metric is explicitly configured, so a newly created collection uses the installed Chroma version's default (normally squared L2); an existing stored collection retains its own configuration.
3. **Ingestion** — Each book is converted into a semantic document (via `build_book_document()`) and structured metadata (via `build_metadatas()`), then upserted via `collection.upsert()`.
4. **Search** — `collection.query()` accepts `query_texts`, `n_results`, and optional `where` filters, returning IDs, documents, metadatas, and distances. The `BookSearchService` converts these into `BookSearchResult` objects.
5. **Filtering** — `collection.get()` with a `where` parameter retrieves documents matching metadata criteria (exact match, `$gte`, `$lte`, `$in`, `$and`, `$or`, etc.).

---

## 11. ChromaDB where filter operators

| Operator | Example | Description |
|---|---|---|
| Exact match | `{"genre": "Fantasy"}` | Equal to value |
| Greater than or equal | `{"rating": {"$gte": 4.3}}` | Greater than or equal |
| Less than or equal | `{"year": {"$lte": 2000}}` | Less than or equal |
| In list | `{"genre": {"$in": ["Fantasy", "Sci-Fi"]}}` | Value in list |
| And | `{"$and": [cond1, cond2]}` | All conditions must match |
| Or | `{"$or": [cond1, cond2]}` | At least one condition matches |

---

## 12. Key concepts practiced

- **ChromaDB collections** — creating, ingesting, and querying a persistent vector store
- **SentenceTransformer embeddings** — converting text to vectors with `SentenceTransformerEmbeddingFunction`
- **Collection distance configuration** — the metric is independent of the embedding model and is not explicitly selected by this source
- **Document construction** — combining multiple fields into an effective searchable text string
- **Metadata filtering** — using `where` clauses in `collection.get()` for structured filtering
- **Combined search** — using `where` in `collection.query()` to filter semantic results
- **Idempotent ingestion** — using `upsert` so repeated runs don't create duplicates
- **Persistent storage** — `chromadb.PersistentClient` survives application restarts
- **Separation of concerns** — data, documents, vector store, repository, search, models, and presentation layers are isolated
- **Application-level models** — `BookSearchResult` Pydantic model for typed search results

---

## 13. Testing

The project includes **5 print-based exercise functions across 3 test files** under `tests/`. They display results rather than asserting behavior. No pass result or coverage percentage is claimed by this documentation update.

| Exercise | Description |
|---|---|
| `test_search_similar_books` | Similarity query with n_results=3 |
| `test_filter_books_by_genre` | Genre `$in` filtering |
| `test_filter_books_by_rating` | Rating `$gte` filtering |
| `test_combined_semantic_metadata_search_1` | Genre + author `$in` filter |
| `test_combined_semantic_metadata_search_2` | Similarity + rating filter |

Run tests with:

```bash
python -m pytest tests/ -v
```

> **Note:** Tests currently use `print()` and `display_similarity_results()` for output rather than asserting expected behavior. The test runner `scripts/run_search.py` aggregates and executes all 5 test functions.

---

## 14. Ideas to extend

- Convert existing tests from `print()`-based to assertion-based verification
- Add `test_documents.py` and `test_repository.py` with assertions for document generation and CRUD operations
- Implement `display_filtered_books()` and `display_combined_results()` in `app/display.py`
- Rewrite `scripts/run_search.py` as a proper CLI orchestrator
- Add a CLI runner with `argparse` for query, n_results, filter options
- Add decade filtering (e.g., books published during the 1990s)
- Add page count filtering (e.g., books between 250 and 400 pages)
- Add environment variable configuration (`CHROMA_PERSIST_DIRECTORY`, `CHROMA_COLLECTION_NAME`)
- Add Python `logging` instead of `print()` statements
- Add input validation and error handling for missing or invalid book data
- Implement a FastAPI layer to expose search as a REST API
- Fix `get_books()` bug — currently returns a single dict instead of a list of all books

---

## 15. Known issues

1. **Tests do not assert behavior.** All five exercise functions print results instead of verifying them with assertions; model downloads and the persistent database also affect execution.
2. **`get_books()` likely has a bug.** The repository method returns a single dict (`result["ids"][0]`) instead of a list of all books.
3. **`build_book_documents()` silently swallows `KeyError`.** It prints an error and continues, which could hide data issues.
4. **`filter_books()` in `BookSearchService` returns raw dicts, not `BookSearchResult` objects.** The `search_similar_books()` method properly converts to `BookSearchResult`, but `filter_books()` does not.
5. **Dependency and configuration gaps.** `python-dotenv` and Pydantic are not explicitly listed in `requirements.txt`; `BOOKS_DATA` is read but not parsed, so it is not a usable structured-data override.
6. **`utils.py` at project root is not part of the planned architecture.** It contains `print_books()` which is used by tests but is not in the planned module structure.
