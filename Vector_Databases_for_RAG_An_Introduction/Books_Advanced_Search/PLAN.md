# Books Advanced Search — Learning Lab

Welcome! In this lab, you will build a semantic book-search system using **ChromaDB**, a vector database. By the end, you will understand how computers can find books by *meaning*, not just by exact keywords.

---

## 1. What You'll Build

You will build a small Python application that:

- Stores 8 classic books in a **vector database**
- Converts book text into numerical representations called **embeddings**
- Searches for books by *concept* (e.g., "magic and friendship") instead of exact keywords
- Filters books by structured fields like genre, rating, and year
- Combines semantic search with metadata filtering

The final project has a clean, layered architecture:

```text
CLI / Runner
  ↓
Search Service (app/search.py)
  ↓
Repository (app/repository.py)
  ↓
Vector Store (app/vector_store.py)
  ↓
ChromaDB
```

---

## 2. What You'll Learn

By following this lab, you will understand:

- What **embeddings** are and why they matter
- How a **vector database** differs from a traditional database
- How to use **ChromaDB** to store and search vectors
- The difference between **documents** (text for similarity) and **metadata** (structured fields for filtering)
- How **semantic similarity search** works
- How to filter results using ChromaDB's `where` expressions
- How to combine semantic search with metadata filters
- Why real applications use **layers** (service, repository, vector store) instead of calling ChromaDB directly
- How to structure results with **Pydantic models**
- What makes good tests vs. print-only verification

---

## 3. Prerequisites

- **Python 3.10+** (the project uses `list[dict]` syntax)
- Basic familiarity with **Python functions, classes, and modules**
- Basic understanding of what a **database** is
- No prior knowledge of vector databases required — everything is taught here

### Setup

```bash
# Create a virtual environment (if you haven't already)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

The `requirements.txt` contains:

```
chromadb
sentence-transformers
```

`chromadb` is the vector database. `sentence-transformers` provides the embedding model.

> **Note:** If `from dotenv import load_dotenv` in `data/books.py` fails, you may need `pip install python-dotenv`. This import is a leftover from earlier development and is not essential to the core project.

---

## 4. Project Overview

### The Dataset

The project uses **8 books** defined in `data/books.py`. Each book has:

| Field | Example | Type |
|---|---|---|
| `id` | `"book_1"` | string |
| `title` | `"The Great Gatsby"` | string |
| `author` | `"F. Scott Fitzgerald"` | string |
| `genre` | `"Fantasy"` | string |
| `year` | `1997` | integer |
| `rating` | `4.5` | float |
| `pages` | `223` | integer |
| `description` | `"A young wizard discovers..."` | string |
| `themes` | `"friendship, courage, good vs evil"` | string |
| `setting` | `"England, magical world"` | string |

All 8 books are listed in `data/books.py`.

### Key Files

| File | Purpose |
|---|---|
| `data/books.py` | The book dataset |
| `app/config.py` | Configuration constants |
| `app/documents.py` | Converts books to text documents and structured metadata |
| `app/vector_store.py` | Creates the ChromaDB client and collection |
| `app/repository.py` | `BookRepository` — abstracts all ChromaDB operations |
| `app/models.py` | `BookSearchResult` — the application's result model |
| `app/search.py` | `BookSearchService` — application-level search logic |
| `app/display.py` | `display_similarity_results()` — shows results to the user |
| `app/run_search.py` | `ingest_books()` helper function |
| `tests/` | Tests demonstrating the search capabilities |

---

## 5. Lab 1 — Prepare the Dataset

### 1. What are we learning?

**Data separation** — the book dataset lives in its own module (`data/books.py`) so it is completely independent from all application logic. This means you can swap the dataset without touching the search code.

### 2. What are we building?

The `books` list in `data/books.py` contains 8 dictionaries. Each dictionary represents one book with all its fields.

### 3. What should you implement?

The file `data/books.py` already exists with the 8 books. Each book dictionary includes `id`, `title`, `author`, `genre`, `year`, `rating`, `pages`, `description`, `themes`, and `setting`.

The dataset is self-contained — no database or external service is needed.

### 4. How do you verify it?

```bash
python -c "from data.books import books; print(len(books), 'books loaded')"
```

You should see: `8 books loaded`.

---

## 6. Lab 2 — Understand Documents and Metadata

### 1. What are we learning?

**Documents vs. metadata** — this is one of the most important concepts in vector databases.

A **document** is free-form text that gets converted into an embedding (a vector of numbers). The embedding captures the *meaning* of the text. When you search by meaning, you search over documents.

**Metadata** is structured, key-value information (like a spreadsheet row). Metadata is used for *filtering* — you can say "show me results where genre is Fantasy" or "where rating is at least 4.0".

**They serve different purposes:**

- **Documents** answer: *"What is conceptually similar?"*
- **Metadata** answers: *"What satisfies this structured constraint?"*

### 2. What are we building?

In `app/documents.py`, there are three functions:

**`build_book_document(book)`** — Takes a book dictionary and creates a single text string that combines the book's title, author, description, themes, setting, genre, year, and rating. This is the text that will be embedded.

```python
def build_book_document(book: dict) -> str:
    return f"""
    The {book["title"]} by {book["author"]}.
    {book["description"]}.
    Themes: {book["themes"]}.
    Setting: {book["setting"]}.
    Genre: {book["genre"]}.
    Published in {book["year"]}
    With a {book["rating"]} rating.
    """
```

**`build_book_documents(books)`** — Calls `build_book_document()` for each book in a list and returns a list of document strings.

**`build_metadatas(books)`** — Creates a list of metadata dictionaries. Each metadata dictionary contains the structured fields: `title`, `author`, `genre`, `year`, `rating`, and `pages`.

### 3. What should you implement?

Look at `app/documents.py`. Notice:

- The **document** includes descriptive text (the description, themes, setting) — this is what gets semantically searched.
- The **metadata** includes only structured fields (`year`, `rating`, `pages`) — these are what get filtered.
- Numeric metadata fields (`year`, `rating`, `pages`) are explicitly cast to `int` or `float`. This is **critical** because ChromaDB needs correct types for filtering to work.

### 4. How do you verify it?

```bash
python -c "
from data.books import books
from app.documents import build_book_document, build_metadatas

doc = build_book_document(books[0])
print('Document for first book:')
print(doc[:100], '...')

meta = build_metadatas(books)
print('\nMetadata for first book:', meta[0])
print('Type of year:', type(meta[0]['year']))
print('Type of rating:', type(meta[0]['rating']))
"
```

You should see the document text and metadata dictionary with correct numeric types.

---

## 7. Lab 3 — Set Up ChromaDB

### 1. What are we learning?

**ChromaDB** is a vector database. A vector database stores vectors (lists of numbers) and can find the most similar vectors quickly.

Key ChromaDB concepts:

- **Client** — the connection to the database. `PersistentClient` saves data to disk.
- **Collection** — a named container for vectors, similar to a table in a relational database.
- **ID** — a unique string identifier for each stored item.
- **Persistence** — when using `PersistentClient`, data is saved to a directory (`storage/chroma/`) so it survives restarts. Without persistence, data vanishes when the program ends.

### How does a vector database differ from a traditional database?

| Traditional database | Vector database |
|---|---|
| Finds rows by exact match | Finds rows by *similarity* |
| Example: `WHERE genre = 'Fantasy'` | Example: "find text similar to this description" |
| Structured queries | Semantic queries |
| Uses filters (`=`, `>`, `<`) | Uses distance/similarity |

They work **together**, not as replacements. This project uses both: ChromaDB for semantic search and metadata filtering together.

### 2. What are we building?

In `app/vector_store.py`, two functions create the ChromaDB infrastructure:

**`create_client()`** — Creates a `chromadb.PersistentClient` pointing at `storage/chroma/`. This means all data is saved to disk.

**`get_collection(client)`** — Calls `client.get_or_create_collection()` to retrieve an existing collection named `"books"` or create it if it doesn't exist. The collection is configured with an **embedding function**.

### 3. What should you implement?

Look at `app/vector_store.py`. The key code:

```python
from chromadb.utils import embedding_functions
from app.config import COLLECTION_NAME, PERSIST_DIRECTORY

embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)
```

The **embedding function** is what converts text into vectors. The model used is `all-MiniLM-L6-v2`, which produces **384-dimensional vectors** (each vector is a list of 384 floating-point numbers).

The collection is retrieved with:

```python
client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=embedding_function
)
```

The `embedding_function` is passed to the collection so ChromaDB automatically converts text to vectors whenever documents are added or queried. You do not need to compute embeddings yourself.

### 4. How do you verify it?

```bash
python -c "
from app.vector_store import create_client, get_collection

client = create_client()
collection = get_collection(client)
print('Collection name:', collection.name)
print('Dimensions:', collection.metadata['embedding_function']['model_name'])
"
```

You should see the collection name `"books"`. The `storage/chroma/` directory should now exist with a SQLite database file.

---

## 8. Lab 4 — Generate Embeddings

### 1. What are we learning?

**Embeddings** are numerical representations of text. The model `all-MiniLM-L6-v2` converts text into a **384-dimensional vector** — a list of 384 numbers.

Here is the intuition:

- Similar texts produce vectors that are **close together** in this 384-dimensional space.
- Dissimilar texts produce vectors that are **far apart**.
- The distance between vectors measures semantic similarity.

When ChromaDB stores a document, it automatically calls the embedding function and stores the vector alongside the document text and metadata.

### 2. What are we building?

The embedding function is configured at module level in `app/vector_store.py`. ChromaDB calls it automatically — you never call it directly. When you add a document to the collection, ChromaDB embeds it. When you query with text, ChromaDB embeds the query text and finds the closest vectors.

### 3. What should you implement?

No additional code is needed — the embedding function is already set up. Just understand that:

1. You pass text strings to ChromaDB.
2. ChromaDB embeds them using `all-MiniLM-L6-v2`.
3. ChromaDB stores the 384-dimensional vectors.
4. ChromaDB uses those vectors to find similar text when you search.

### 4. How do you verify it?

```bash
python -c "
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer('all-MiniLM-L6-v2')
v = model.encode(['hello world'])
print(f'Vector dimension: {v.shape[1]}')
print(f'First 5 values: {v[0][:5]}')
"
```

You should see `Vector dimension: 384`.

---

## 9. Lab 5 — Ingest the Books

### 1. What are we learning?

**Ingestion** — the process of adding data to the vector database. This project uses **upsert** (update or insert), which means:

- If an item with the given ID does not exist, it is **inserted** (added).
- If an item with the given ID already exists, it is **updated** (replaced).

This makes ingestion **idempotent** — you can run it multiple times without creating duplicates. This is very useful during development.

### 2. What are we building?

In `app/repository.py`, the `BookRepository` class has a method `upsert_book(book)` that:

1. Calls `build_book_document([book])` to create the document text.
2. Calls `build_metadatas([book])` to create the metadata dictionary.
3. Calls `self.collection.upsert(documents=..., metadatas=..., ids=[book_id])` to store everything in ChromaDB.

Each book needs three things stored in ChromaDB:
- **`documents`** — the text that gets embedded
- **`metadatas`** — the structured key-value data
- **`ids`** — a unique identifier (the book's `id` field)

### 3. What should you implement?

Look at `app/repository.py`. The `upsert_book()` method handles one book at a time. The `ingest_books()` function in `app/run_search.py` iterates over all books and calls `upsert_book()` for each.

The workflow is:

```text
Books (data/books.py)
  → build_book_document() → text string
  → build_metadatas() → metadata dict
  → collection.upsert() → stored in ChromaDB
```

### 4. How do you verify it?

```bash
python -c "
from data.books import books
from app.repository import BookRepository
from app.run_search import ingest_books

repo = BookRepository()
ingest_books(repo, books)
print('Books ingested successfully')
"
```

If you run this twice, it will not create duplicates because `upsert` replaces existing entries.

---

## 10. Lab 6 — Semantic Similarity Search

### 1. What are we learning?

**Semantic similarity search** — you provide a query (a sentence describing what you want), and ChromaDB finds the most similar documents.

How it works:

1. Your query text is converted to a vector (embedding) using the same embedding model.
2. ChromaDB compares this vector to all stored vectors.
3. It returns the `n_results` closest matches.
4. Each result includes the document text, metadata, and a **distance** value.

The **distance** tells you how similar the results are to your query. Smaller distance means more similar. ChromaDB's default distance metric for this setup is **cosine distance**.

The parameter `n_results` controls how many matches to return.

### 2. What are we building?

The search flow goes through two layers:

1. **`BookSearchService.search_similar_books()`** (`app/search.py`) — the application-level service that receives the query and parameters, delegates to the repository, and converts raw results into `BookSearchResult` objects.

2. **`BookRepository.search_books()`** (`app/repository.py`) — the repository layer that calls `collection.query()` with the query text and `n_results`.

When no metadata filter is applied (`where is None`), the repository calls:

```python
self.collection.query(
    query_texts=[query],
    n_results=n_results,
)
```

ChromaDB returns results ordered by similarity, each containing `ids`, `documents`, `metadatas`, and `distances`.

### 3. What should you implement?

Look at `app/search.py`. The `search_similar_books()` method takes a query string and optional `n_results`, calls the repository, and converts each raw result dict into a `BookSearchResult` object.

### 4. How do you verify it?

```bash
python -m pytest tests/test_search_similar_books.py -v
```

The test searches for `"magical fantasy adventure with friendship and courage."` and should return books like Harry Potter and The Lord of the Rings, because the embedding model considers those concepts semantically similar.

> **Note:** The tests use `print()` to display results rather than asserting expected values. They demonstrate behavior visually but are not automated assertions. See Lab 11 for test quality discussion.

---

## 11. Lab 7 — Metadata Filtering

### 1. What are we learning?

**Metadata filtering** lets you apply structured constraints on top of semantic results. ChromaDB supports a `where` clause with comparison operators:

| Operator | Meaning | Example |
|---|---|---|
| `$gte` | greater than or equal | `{"rating": {"$gte": 4.0}}` |
| `$lte` | less than or equal | `{"rating": {"$lte": 4.5}}` |
| `$in` | in a list | `{"genre": {"$in": ["Fantasy", "Sci-Fi"]}}` |
| `$and` | logical AND | `{"$and": [{"genre": {...}}, {"year": {...}}]}` |
| `$or` | logical OR | `{"$or": [{"genre": {...}}, {"rating": {...}}]}` |

**Important implementation detail:** The repository handles the case where no filter is provided separately from the case where a filter is provided. When `where is None`, the `where` parameter is not passed to ChromaDB at all. This is because the installed ChromaDB version rejects an empty `where={}` expression. This is an intentional design choice worth remembering.

### 2. What are we building?

There are **two different paths** for metadata filtering in this project:

**Path A — Metadata-only filtering** via `BookRepository.filter_books()`:

This calls `collection.get(where=filters)` — a metadata-only retrieval that does **not** perform semantic search. It returns all items whose metadata matches the filter.

**Path B — Semantic search with metadata filter** via `BookRepository.search_books(query, n_results, where)`:

This calls `collection.query(query_texts=[query], n_results=n_results, where=where)` — semantic search **combined** with metadata filtering. ChromaDB performs both operations in a single call.

The `BookSearchService.filter_books()` method delegates to `repository.filter_books()` (Path A), while `search_similar_books()` delegates to `repository.search_books()` (Path B).

### 3. What should you implement?

Look at `app/repository.py`. Notice the difference:

- `filter_books(filters)` → `collection.get(where=filters)` — metadata only
- `search_books(query, n_results, where)` → `collection.query(..., where=where)` — semantic + metadata

The test `tests/test_filter_books.py` demonstrates Path A with two filters:

```python
where = {"genre": {"$in": ["Fantasy", "Science Fiction"]}}
where = {"rating": {"$gte": 4.3}}
```

### 4. How do you verify it?

```bash
python -m pytest tests/test_filter_books.py -v
```

You should see 2 tests pass that filter by genre and by rating.

---

## 12. Lab 8 — Combine Semantic Search with Metadata Filtering

### 1. What are we learning?

**Combined search** lets you ask both types of questions at once:

- Semantic search: *"What is conceptually relevant?"*
- Metadata filtering: *"What satisfies this structured constraint?"*

For example: "Find books similar to 'dystopian society control oppression future' but only show me those with a rating of 4.0 or higher."

The semantic part finds conceptually matching books. The metadata filter narrows the results to those that satisfy the rating requirement. ChromaDB handles both in a single `query()` call.

### 2. What are we building?

The tests in `tests/test_combined_semantic_metadata_search.py` demonstrate combined search:

**Test 1** — Semantic search filtered by genre AND author:

```python
query = "magical fantasy adventure with friendship and courage."
where = {
    "$and": [
        {"genre": {"$in": ["Fantasy", "Science Fiction"]}},
        {"author": {"$in": ["J.R.R. Tolkien", "Isaac Asimov", "F. Scott Fitzgerald"]}},
    ]
}
results = book_search_service.search_similar_books(query, n_results=3, where=where)
```

This finds books conceptually similar to the query, but only from Fantasy/Science Fiction genres by those specific authors.

**Test 2** — Semantic search filtered by rating:

```python
query = "dystopian society control oppression future"
where = {"rating": {"$gte": 4.0}}
results = book_search_service.search_similar_books(query, n_results=3, where=where)
```

This finds books about dystopian themes with a rating of at least 4.0.

### 3. What should you implement?

The combined search is implemented in `BookRepository.search_books()` — it passes the `where` clause directly to `collection.query()`. The `BookSearchService.search_similar_books()` forwards both the query and `where` to the repository.

No additional code is needed — the architecture already supports this through the `where` parameter.

### 4. How do you verify it?

```bash
python -m pytest tests/test_combined_semantic_metadata_search.py -v
```

Both combined search tests should pass.

---

## 13. Lab 9 — Build the Application Layers

### 1. What are we learning?

**Layered architecture** — why do we split the code into multiple layers instead of calling ChromaDB directly?

```text
Search Service → Repository → Vector Store → ChromaDB
```

Each layer has a clear responsibility:

| Layer | File | Responsibility |
|---|---|---|
| **Search Service** | `app/search.py` | Application logic — decides what to search for and how to present results |
| **Repository** | `app/repository.py` | Database operations — abstracts ChromaDB calls |
| **Vector Store** | `app/vector_store.py` | Infrastructure — manages ChromaDB client and collection |

**Why this matters:**

- The **repository** is the *only* layer that knows about ChromaDB's API. If you ever switch from ChromaDB to another vector database, you only need to change the repository.
- The **service layer** works with application-level objects (`BookSearchResult`), not raw ChromaDB response structures. This keeps the rest of the application clean.
- The **vector store** handles all ChromaDB setup. Changing the embedding model or persistence path only requires changes here.

### 2. What are we building?

All layers already exist in the project. Let's review each:

**`app/config.py`** — Centralized configuration:

```python
COLLECTION_NAME = "books"
PERSIST_DIRECTORY = "storage/chroma"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
```

The vector store imports these constants, so configuration is managed in one place.

**`app/vector_store.py`** — Creates the ChromaDB client and collection:
- `create_client()` — returns a `PersistentClient`
- `get_collection(client)` — returns or creates the `"books"` collection

**`app/repository.py`** — `BookRepository` class:
- Manages all CRUD operations (add, get, upsert, update, delete)
- Handles search with optional metadata filtering
- Handles metadata-only filtering via `filter_books()`
- The only layer with direct ChromaDB knowledge

**`app/search.py`** — `BookSearchService` class:
- Receives a `BookRepository` through `__init__` (dependency injection)
- `search_similar_books(query, n_results, where)` — delegates to repository
- `filter_books(where)` — delegates to repository's metadata filter
- `get_book(book_id)` / `get_books()` — delegates to repository

### 3. What should you implement?

No additional code is needed. Just understand how the layers connect:

```text
Your code
  → BookSearchService (service layer)
    → BookRepository (repository layer)
      → ChromaDB collection (vector store layer)
```

### 4. How do you verify it?

```bash
python -c "
from app.config import COLLECTION_NAME, PERSIST_DIRECTORY, EMBEDDING_MODEL_NAME
print('Collection:', COLLECTION_NAME)
print('Persist:', PERSIST_DIRECTORY)
print('Model:', EMBEDDING_MODEL_NAME)
"
```

---

## 14. Lab 10 — Return Structured Results

### 1. What are we learning?

**Application-level result models** — why do we create a `BookSearchResult` model instead of returning raw ChromaDB response dictionaries?

Raw ChromaDB responses contain many fields and have a complex structure. Exposing them throughout the application creates tight coupling to ChromaDB's API and makes the code harder to maintain.

A **Pydantic model** (`BookSearchResult`) solves this by:

- Defining exactly which fields the application cares about
- Providing type validation and coercion
- Creating a clean contract between layers
- Making it easy to add or change fields without affecting other code

### 2. What are we building?

Look at `app/models.py`:

```python
from pydantic import BaseModel

class BookSearchResult(BaseModel):
    id: str
    title: str
    author: str
    genre: str
    year: int
    rating: float
    distance: float | None = None
```

The `distance` field defaults to `None` because not all retrieval methods return distance values. Metadata-only filtering (via `filter_books()`) does not compute similarity distance, so the field is optional.

The `BookSearchService.search_similar_books()` method converts raw repository results into `BookSearchResult` objects. However, `BookSearchService.filter_books()` currently returns **raw dictionaries** instead of `BookSearchResult` objects — this is an inconsistency in the current implementation.

### 3. What should you implement?

Understand how `BookSearchResult` is constructed in `app/search.py`:

```python
BookSearchResult(
    id=book["id"],
    title=book["metadata"].get("title"),
    author=book["metadata"].get("author"),
    genre=book["metadata"].get("genre"),
    year=book["metadata"].get("year"),
    rating=book["metadata"].get("rating"),
    distance=book.get("distance"),
)
```

Each raw result dictionary from the repository is mapped to a `BookSearchResult` object with clean, typed fields.

### 4. How do you verify it?

```bash
python -c "
from app.models import BookSearchResult

result = BookSearchResult(
    id='book_1', title='The Great Gatsby', author='F. Scott Fitzgerald',
    genre='Classic', year=1925, rating=4.1, distance=0.35
)
print(result.title)
print(result)
"
```

---

## 15. Lab 11 — Test the Search System

### 1. What are we learning?

**Testing vector database applications** — what does it mean to test a system that uses embeddings?

The current tests verify that:

1. Semantic search returns results for a query
2. Metadata filtering returns books matching the criteria
3. Combined search returns results matching both semantic and metadata constraints

### 2. What are we building?

The project has **5 tests** across 3 test files:

| Test File | Test Function | What It Tests |
|---|---|---|
| `test_search_similar_books.py` | `test_search_similar_books` | Semantic search with n_results=3 |
| `test_filter_books.py` | `test_filter_books_by_genre` | Filter by genre using `$in` |
| `test_filter_books.py` | `test_filter_books_by_rating` | Filter by rating using `$gte` |
| `test_combined_semantic_metadata_search.py` | `test_combined_semantic_metadata_search_1` | Combined search with `$and` filter |
| `test_combined_semantic_metadata_search.py` | `test_combined_semantic_metadata_search_2` | Combined search with rating filter |

### 3. What should you implement?

The tests already exist. Run them with:

```bash
python -m pytest tests/ -v
```

### 4. How do you verify it?

All 5 tests should pass. However, be aware of the current limitations:

> **Important note about the current tests:** The existing tests use `print()` statements and display functions to *show* results visually. They do **not** use `assert` statements to verify expected behavior automatically. For example, `test_search_similar_books` calls `display_similarity_results(results)` but never asserts that the results contain expected books or have the correct number of items.

This means the tests demonstrate the functionality works, but they are not true automated tests. Improving them — adding assertions to verify result counts, metadata constraints, and valid IDs — is a great exercise for after you complete this lab.

---

## 16. Run the Full Demo

### 1. What are we learning?

**How to run the complete workflow** — from data to results.

### 2. What are we building?

`scripts/run_search.py` runs all 5 tests in sequence, printing headers and displaying results. It demonstrates the full range of search capabilities:

1. Similarity search for fantasy books
2. Genre filtering
3. Combined search by genre and author
4. Rating filtering
5. Combined search for dystopian books with high ratings

### 3. How do you verify it?

```bash
python scripts/run_search.py
```

You should see output for all 5 search exercises with results displayed.

---

## 17. Final Architecture

### How the pieces connect

```text
                          ┌─────────────────┐
                          │  Book Dataset   │
                          │  data/books.py  │
                          └────────┬────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │   Documents     │
                          │ documents.py    │
                          └────────┬────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │  ChromaDB       │
                          │  (Persistent)   │
                          │  storage/chroma/│
                          └────────┬────────┘
                                   │
                                   ▲
                                   │
                          ┌────────┴────────┐
                          │   Repository    │
                          │ repository.py   │
                          └────────┬────────┘
                                   │
                                   ▲
                                   │
                          ┌────────┴────────┐
                          │ Search Service  │
                          │   search.py     │
                          └────────┬────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │   Results Model │
                          │  models.py      │
                          └────────┬────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │   Display       │
                          │  display.py     │
                          └────────┬────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │   Tests / CLI   │
                          │  tests/ scripts/│
                          └─────────────────┘
```

### Module responsibilities

| Module | Responsibility | Status |
|---|---|---|
| `data/books.py` | Book dataset — isolated from all application logic | Implemented |
| `app/config.py` | Centralized configuration (collection name, persist directory, embedding model) | Implemented |
| `app/documents.py` | Converts books to semantic documents and structured metadata | Implemented |
| `app/vector_store.py` | ChromaDB client creation and collection retrieval | Implemented |
| `app/repository.py` | Abstraction over ChromaDB operations (add, get, search, filter, upsert, update, delete) | Implemented |
| `app/search.py` | Application-level search service — delegates to repository, returns `BookSearchResult` | Implemented |
| `app/models.py` | `BookSearchResult` Pydantic model for application-level results | Implemented |
| `app/display.py` | Presentation layer (`display_similarity_results` implemented) | Implemented |
| `app/run_search.py` | `ingest_books()` helper function | Implemented |
| `utils.py` | `print_books()` utility (not part of original plan) | Present |
| `scripts/run_search.py` | Test runner aggregating all tests | Implemented |
| `tests/` | 5 tests, all passing, print-based | Implemented |

### Key design decisions

1. **`filter_books()` uses `collection.get()` not `collection.query()`** — metadata-only retrieval does not perform semantic search. Combined semantic + metadata search goes through `collection.query()` with the `where` parameter.

2. **Empty `where` is avoided** — when no filter is provided, the `where` parameter is not passed to ChromaDB at all (using `if where is None`). This prevents errors from the installed ChromaDB version rejecting empty `where={}` expressions.

3. **Pydantic `BaseModel` instead of `@dataclass`** — the `BookSearchResult` model uses Pydantic for validation and type coercion.

4. **Persistent storage** — all data is saved to `storage/chroma/` and survives application restarts.

5. **Idempotent ingestion** — `upsert_book()` allows the ingestion process to be safely repeated without creating duplicates.

---

## 18. What You Learned

Here is a summary of the concepts and skills you practiced:

- **Embeddings**: Text is converted into 384-dimensional vectors using `all-MiniLM-L6-v2`. Similar texts have similar vectors.
- **Vector databases**: ChromaDB stores vectors and finds similar vectors efficiently, enabling semantic search.
- **ChromaDB concepts**: Client, collection, documents, embeddings, metadata, IDs, persistence, querying.
- **Documents vs. metadata**: Documents are text for semantic similarity. Metadata is structured data for filtering.
- **Semantic search**: Provide a query text, get the most similar documents ordered by distance.
- **Metadata filtering**: Use ChromaDB's `where` expressions (`$gte`, `$lte`, `$in`, `$and`, `$or`) to filter results.
- **Combined search**: Semantic search and metadata filtering work together in a single `collection.query()` call.
- **Layered architecture**: Service → Repository → Vector Store separates concerns and makes the code maintainable.
- **Result models**: Pydantic `BookSearchResult` provides a clean contract between layers.
- **Persistence**: Data saved to `storage/chroma/` survives restarts.
- **Idempotent ingestion**: `upsert` allows safe repeated ingestion.

---

## 19. Optional Extensions

These are ideas you can implement after completing the core lab. None of them are part of the current project.

### Testing improvements

- **Convert tests to assertion-based** — add `assert` statements to verify result counts, metadata constraints, and valid IDs.
- **Add `test_documents.py`** — verify that `build_book_document()` output contains all expected fields, and that `len(build_book_documents(books)) == len(books)`.
- **Add `test_repository.py`** — test CRUD operations (`add_book`, `get_book`, `upsert_book`, `delete_book`).
- **Add metadata validation tests** — verify that all metadata fields are present and numeric types are preserved.

### Repository improvements

- **Fix `get_books()` bug** — currently returns a single dictionary instead of a list of all books.
- **Add `distance` to `filter_books()` results** — `filter_books()` currently returns raw dictionaries without the `distance` field.
- **Return `BookSearchResult` from `filter_books()`** — the service method currently returns raw dicts instead of structured objects.

### Additional filters

- **Year range filtering** — combine `$and` with year range to find books from a specific decade.
- **Page count filtering** — numeric range on pages to find short or long reads.

### Application polish

- **Environment variable configuration** — allow `CHROMA_PERSIST_DIRECTORY` and `CHROMA_COLLECTION_NAME` to be set via environment variables.
- **Logging** — replace `print()` statements with Python's `logging` module.
- **Input validation and error handling** — add validation for book data and handle edge cases gracefully.
- **CLI arguments** — use `argparse` to accept query text, `n_results`, and filter options from the command line.

### Presentation

- **Complete `display.py`** — implement `display_filtered_books()` and `display_combined_results()`.
- **Remove `utils.py`** — consolidate display utilities into `app/display.py`.
- **Build a proper CLI orchestrator** — rewrite `scripts/run_search.py` as a full application runner that loads books, ingests, creates the search service, runs all exercises, and displays results.

### Advanced topics

- **FastAPI layer** — add a REST API for search.
- **Remove `dotenv` dependency** — `data/books.py` imports `load_dotenv` and checks `os.getenv("BOOKS_DATA", books)`, but no `.env` file exists and this is not part of the core functionality.

---

## 20. Quick Reference — ChromaDB `where` Operators

### Operators demonstrated in this project

| Operator | Meaning | Example |
|---|---|---|
| `$gte` | Greater than or equal | `{"rating": {"$gte": 4.0}}` |
| `$lte` | Less than or equal | `{"rating": {"$lte": 4.5}}` |
| `$in` | Value is in a list | `{"genre": {"$in": ["Fantasy", "Sci-Fi"]}}` |
| `$and` | Logical AND of conditions | `{"$and": [{"genre": {...}}, {"year": {...}}]}` |

### Additional ChromaDB operators (not used in this project)

| Operator | Meaning | Example |
|---|---|---|
| `$eq` | Equal | `{"genre": {"$eq": "Fantasy"}}` |
| `$gt` | Greater than | `{"rating": {"$gt": 4.0}}` |
| `$lt` | Less than | `{"rating": {"$lt": 5.0}}` |
| `$or` | Logical OR | `{"$or": [{"genre": {...}}, {"rating": {...}}]}` |

---

## 21. Quick Reference — Key Files and Functions

| File | Function / Class | Purpose |
|---|---|---|
| `data/books.py` | `books` | List of 8 book dictionaries |
| `app/config.py` | `COLLECTION_NAME`, `PERSIST_DIRECTORY`, `EMBEDDING_MODEL_NAME` | Configuration constants |
| `app/documents.py` | `build_book_document(book)` | Create semantic document from one book |
| `app/documents.py` | `build_book_documents(books)` | Create documents for all books |
| `app/documents.py` | `build_metadatas(books)` | Create metadata dictionaries |
| `app/vector_store.py` | `create_client()` | Create ChromaDB persistent client |
| `app/vector_store.py` | `get_collection(client)` | Get or create the collection |
| `app/vector_store.py` | `embedding_function` | `SentenceTransformerEmbeddingFunction` |
| `app/repository.py` | `BookRepository` | ChromaDB abstraction class |
| `app/repository.py` | `BookRepository.upsert_book(book)` | Insert or update a book |
| `app/repository.py` | `BookRepository.search_books(query, n_results, where)` | Semantic search with optional filter |
| `app/repository.py` | `BookRepository.filter_books(filters)` | Metadata-only filtering |
| `app/models.py` | `BookSearchResult` | Pydantic result model |
| `app/search.py` | `BookSearchService` | Application search service |
| `app/search.py` | `BookSearchService.search_similar_books(query, n_results, where)` | Combined semantic + metadata search |
| `app/search.py` | `BookSearchService.filter_books(where)` | Metadata filtering |
| `app/display.py` | `display_similarity_results(results)` | Display search results |
| `app/run_search.py` | `ingest_books(repository, books)` | Ingest all books |

---

## 22. Summary: Implemented vs. Future Work

### Implemented in this lab

- 8-book dataset with all required fields
- Document construction and metadata building
- ChromaDB persistent collection with `all-MiniLM-L6-v2` embeddings (384 dimensions)
- `BookRepository` with full CRUD and search operations
- `BookSearchService` with semantic search, metadata filtering, and combined search
- `BookSearchResult` Pydantic model for structured results
- `display_similarity_results()` for output
- 5 passing tests covering similarity search, metadata filtering, and combined search
- `scripts/run_search.py` test runner
- Persistent storage at `storage/chroma/`
- Idempotent ingestion via `upsert_book()`

### Current limitations (known issues)

- Tests use `print()` for display rather than `assert` for automated verification
- `get_books()` returns a single dict instead of a list of all books
- `filter_books()` in `BookSearchService` returns raw dicts instead of `BookSearchResult` objects
- `get_books()` in `BookRepository` is missing the `distance` field in its returned dict
- `data/books.py` contains a `dotenv` import that is not essential to the core functionality
- `utils.py` at the project root is not part of the planned architecture
- `display.py` only implements `display_similarity_results()`
- `scripts/run_search.py` acts as a test runner rather than a full CLI orchestrator

### Optional extensions (implement after completing the core lab)

- Assertion-based tests and additional test files
- Repository CRUD tests
- Decade and page-count filtering
- Environment variable configuration
- Logging, validation, and error handling
- CLI arguments with `argparse`
- Complete `display.py` with all display methods
- Proper CLI orchestrator
- FastAPI REST API layer
- Removal of `dotenv` dependency
- Consolidation of `utils.py` into `app/display.py`
