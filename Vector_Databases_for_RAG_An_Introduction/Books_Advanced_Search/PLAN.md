# Advanced Book Search — Implementation Plan

## 1. Project Goal

Build an advanced semantic book-search system using **ChromaDB** that demonstrates:

1. Semantic similarity search.
2. Metadata-based filtering.
3. Semantic search combined with metadata filters.
4. Reusable search functions.
5. Clean separation between data, indexing, search logic, and presentation.
6. Basic validation and testing.
7. Optional extensions for more advanced filtering.

The exercise should be implemented as a small, maintainable Python project rather than placing all logic inside one `books_advanced_search.py` file.

---

## 2. Learning Objectives

By completing this project, the implementation should demonstrate understanding of:

* ChromaDB collections.
* Documents vs. metadata.
* Embeddings and semantic similarity.
* Similarity search with `query()`.
* Metadata filtering with `get()`.
* Combining semantic search with metadata constraints.
* ChromaDB operators such as:

  * `$in`
  * `$gte`
  * `$lte`
  * `$and`
  * `$or`
* Persistent vs. in-memory ChromaDB collections.
* Reusable Python modules.
* Configuration management.
* Separation of concerns.
* Basic automated testing.
* Designing an application layer around a vector database instead of coupling the entire application directly to ChromaDB.

---

# 3. Target Project Structure

The project should eventually follow this structure:

```text
advanced-book-search/
│
├── README.md
├── PLAN.md
├── requirements.txt
├── .gitignore
│
├── data/
│   ├── __init__.py
│   └── books.py
│
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── documents.py
│   ├── vector_store.py
│   ├── repository.py
│   ├── search.py
│   ├── models.py
│   └── display.py
│
├── scripts/
│   └── run_search.py
│
├── tests/
│   ├── __init__.py
│   ├── test_documents.py
│   ├── test_repository.py
│   └── test_search.py
│
└── storage/
    └── chroma/
```

### Architecture Principle

Do not create modules simply for the sake of having many files.

Each module should have a clear responsibility.

The desired dependency direction is:

```text
CLI
 ↓
Search Service
 ↓
Repository
 ↓
Vector Store
 ↓
ChromaDB
```

The data and document-building layers should remain independent from the presentation layer.

---

# 4. Phase 1 — Project Setup

## Objective

Create the basic project structure and Python environment.

### Tasks

* [x] Create the project directory.
* [x] Create a Python virtual environment.
* [x] Activate the virtual environment.
* [x] Install ChromaDB and required dependencies.
* [x] Create `requirements.txt`.
* [x] Create `.gitignore`.
* [x] Create the directory structure.
* [x] Create empty `__init__.py` files where appropriate.
* [x] Initialize Git if this project will be version-controlled.

### Expected Result

The project should have a clean structure before implementing any search logic.

---

# 5. Phase 2 — Book Data Layer

## File

```text
data/books.py
```

## Objective

Keep the original book dataset isolated from the application logic.

Add the provided `books` list to this module.

The module should contain only book data and, optionally, simple constants related to the dataset.

Example:

```python
books = [
    {
        "id": "book_1",
        ...
    },
]
```

### Requirements

* [x] Include all 8 books.
* [x] Preserve the original fields.
* [x] Ensure every book has a unique ID.
* [x] Do not import ChromaDB here.
* [x] Do not perform searches here.
* [x] Do not print results here.

### Design Principle

The application should be able to replace this Python list with another data source later without rewriting the search layer.

---

# 6. Phase 3 — Book Document Construction

## File

```text
app/documents.py
```

## Objective

Convert each book into a meaningful semantic-search document.

Create:

```python
def build_book_document(book: dict) -> str:
    ...
```

The generated document should combine:

* Title
* Author
* Description
* Themes
* Setting
* Genre
* Publication year

Example conceptual document:

```text
The Lord of the Rings by J.R.R. Tolkien.
An epic fantasy quest to destroy a powerful ring and save Middle-earth.
Themes: heroism, friendship, good vs evil, power corruption.
Setting: Middle-earth, fantasy realm.
Genre: Fantasy.
Published in 1954.
```

Also create:

```python
def build_book_documents(books: list[dict]) -> list[str]:
    ...
```

### Requirements

* [x] One document per book.
* [x] Preserve the order of the input books.
* [x] Include the fields relevant to semantic search.
* [x] Do not access ChromaDB.
* [x] Do not print anything.

---

# 7. Phase 4 — Metadata Construction

Metadata should contain structured information that is useful for filtering.

Recommended metadata:

```python
{
    "title": book["title"],
    "author": book["author"],
    "genre": book["genre"],
    "year": book["year"],
    "rating": book["rating"],
    "pages": book["pages"],
}
```

### Important Design Rule

Separate semantic information from structured filtering information.

### Documents

Documents are optimized for semantic meaning.

Example:

```text
magical friendship courageous fantasy adventure
```

### Metadata

Metadata is optimized for structured constraints.

Example:

```text
genre = Fantasy
rating >= 4.3
year >= 1990
pages <= 500
```

Do not rely on text parsing to perform numeric filtering.

---

# 8. Phase 5 — Configuration

## File

```text
app/config.py
```

## Objective

Centralize configuration values.

At minimum define:

```python
COLLECTION_NAME = "books"
PERSIST_DIRECTORY = "storage/chroma"
```

Optionally define embedding configuration if the implementation explicitly selects an embedding model.

### Requirements

* [x] Avoid hard-coding collection names in multiple modules.
* [x] Avoid hard-coding storage paths throughout the application.
* [x] Keep configuration independent from search logic.

---

# 9. Phase 6 — ChromaDB Vector Store

## File

```text
app/vector_store.py
```

## Objective

Encapsulate ChromaDB client and collection initialization.

Create functions such as:

```python
def create_client():
    ...
```

and:

```python
def get_collection(client):
    ...
```

### Responsibilities

This module should handle:

1. Creating the ChromaDB client.
2. Configuring persistence.
3. Creating or retrieving the book collection.
4. Returning the collection to the application.

### Requirements

* [x] ChromaDB-specific initialization lives here.
* [x] Other modules should not create ChromaDB clients directly.
* [x] Collection name comes from configuration.
* [x] Persistence path comes from configuration.

---

# 10. Phase 7 — Repository Layer

## File

```text
app/repository.py
```

## Objective

Create an abstraction around ChromaDB operations.

The repository is the only layer that should need detailed knowledge of ChromaDB's storage/query API.

Suggested interface:

```python
class BookRepository:
    ...
```

Possible operations:

```python
def add_books(...):
    ...

def get_books(...):
    ...

def search_books(...):
    ...
```

### Responsibilities

The repository should provide:

* Book insertion/upsert.
* Metadata filtering.
* Semantic querying.
* Retrieval of book records.
* Conversion of low-level ChromaDB operations into application-friendly operations.

### Design Principle

The search service should not contain raw ChromaDB operations everywhere.

Prefer:

```text
Search Service
      ↓
BookRepository
      ↓
ChromaDB
```

instead of:

```text
Search Service
      ↓
ChromaDB directly
```

---

# 11. Phase 8 — Book Ingestion

## Objective

Create the indexing pipeline.

The ingestion flow should be:

```text
Books
  ↓
Document Builder
  ↓
Metadata Builder
  ↓
Repository
  ↓
ChromaDB
```

For each book:

1. Read the book dictionary.
2. Extract its ID.
3. Build the semantic document.
4. Build metadata.
5. Insert/upsert the book into ChromaDB.

---

# 12. Idempotent Ingestion

The script may be executed multiple times.

Therefore, avoid accidentally creating duplicate logical records.

Prefer an idempotent strategy.

For example:

```text
books
  ↓
upsert
  ↓
ChromaDB
```

If the chosen ChromaDB version supports `upsert`, prefer it for this exercise.

The following should be safe to run repeatedly:

```bash
python3.11 scripts/run_search.py
```

The number of logical books should remain 8.

---

# 13. Phase 9 — Search Service

## File

```text
app/search.py
```

## Objective

Implement the actual application-level search behavior.

A service class is recommended:

```python
class BookSearchService:
    ...
```

The service should receive the repository through dependency injection.

Conceptually:

```text
BookSearchService
        ↓
BookRepository
        ↓
ChromaDB
```

This makes the service easier to test and reduces coupling to ChromaDB.

---

# 14. Exercise 1 — Similarity Search

## Objective

Implement semantic similarity search for:

```text
magical fantasy adventure with friendship and courage
```

Create a reusable method such as:

```python
def search_similar_books(
    query: str,
    n_results: int = 3,
):
    ...
```

The repository should eventually execute a ChromaDB query equivalent to:

```python
collection.query(
    query_texts=[query],
    n_results=n_results,
)
```

### Results Should Include

* Rank
* Book ID
* Title
* Author
* Genre
* Distance

### Requirements

* [ ] Query is configurable.
* [ ] Number of results is configurable.
* [ ] Similarity distance is returned.
* [ ] Metadata is available with each result.
* [ ] Search logic is not hard-coded to one specific book.

---

# 15. Similarity Search Output

The presentation layer should format the results.

Example:

```text
=== Book Similarity Search ===

Query: magical fantasy adventure with friendship and courage

1. Harry Potter and the Philosopher's Stone
   Author: J.K. Rowling
   Genre: Fantasy
   Distance: 0.xxxx

2. The Lord of the Rings
   Author: J.R.R. Tolkien
   Genre: Fantasy
   Distance: 0.xxxx
```

Do not hard-code the expected ranking.

The exact ranking can depend on:

* Embedding model.
* ChromaDB configuration.
* Distance metric.

---

# 16. Exercise 2 — Metadata Filtering

## Objective

Implement structured metadata filtering independently from semantic search.

Create a reusable operation such as:

```python
def filter_books(where: dict):
    ...
```

The underlying repository should use ChromaDB's metadata filtering capabilities.

---

# 17. Genre Filtering

## Requirement

Find books belonging to either:

```text
Fantasy
Science Fiction
```

Use an `$in` condition:

```python
{
    "genre": {
        "$in": ["Fantasy", "Science Fiction"]
    }
}
```

### Expected Behavior

Every returned book must have:

```text
genre ∈ {Fantasy, Science Fiction}
```

### Important

Do not retrieve every book and filter it manually in Python.

The objective is to demonstrate ChromaDB metadata filtering.

---

# 18. Rating Filtering

## Requirement

Find books with a rating of at least `4.3`.

Use:

```python
{
    "rating": {
        "$gte": 4.3
    }
}
```

### Expected Behavior

Every returned book must satisfy:

```text
rating >= 4.3
```

Return useful metadata such as:

* Title
* Rating
* Genre
* Year

---

# 19. Exercise 3 — Combined Semantic + Metadata Search

## Objective

Combine semantic similarity search with a metadata constraint.

Query:

```text
dystopian society control oppression future
```

Metadata constraint:

```text
rating >= 4.0
```

Conceptually:

```python
collection.query(
    query_texts=["dystopian society control oppression future"],
    n_results=3,
    where={
        "rating": {
            "$gte": 4.0
        }
    },
)
```

This demonstrates:

```text
Semantic Relevance
       +
Structured Constraint
       ↓
Filtered Semantic Search
```

---

# 20. Search Result Model

## File

```text
app/models.py
```

## Objective

Avoid passing raw ChromaDB response dictionaries throughout the application.

Create a small application-level result representation.

For example:

```python
@dataclass
class BookSearchResult:
    id: str
    title: str
    author: str
    genre: str
    year: int
    rating: float
    distance: float | None = None
```

The exact model can be adjusted based on the implementation.

### Benefits

This prevents the rest of the application from becoming tightly coupled to ChromaDB's response format.

---

# 21. Presentation Layer

## File

```text
app/display.py
```

## Objective

Keep console output separate from business logic.

Create functions such as:

```python
def display_similarity_results(results):
    ...
```

```python
def display_filtered_books(results):
    ...
```

```python
def display_combined_results(results):
    ...
```

### Design Rule

Search services should return data.

They should not contain large amounts of:

```python
print(...)
```

This separation makes it easier to replace the CLI later with:

* FastAPI
* React
* Streamlit
* another frontend

without rewriting search logic.

---

# 22. Phase 10 — CLI Runner

## File

```text
scripts/run_search.py
```

## Objective

Create the executable entry point for the exercise.

The runner should orchestrate the application but should contain minimal business logic.

Expected flow:

```text
Initialize
    ↓
Load books
    ↓
Build documents
    ↓
Build metadata
    ↓
Initialize ChromaDB
    ↓
Index books
    ↓
Create repository
    ↓
Create search service
    ↓
Run searches
    ↓
Display results
```

---

# 23. Final CLI Flow

The runner should execute the four required exercises.

```text
=== Book Similarity Search ===

1. Finding magical fantasy adventures
...

=== Metadata Filtering ===

2. Finding Fantasy and Science Fiction books
...

3. Finding highly-rated books
...

=== Combined Search ===

4. Finding highly-rated dystopian books
...
```

---

# 24. Phase 11 — Testing

Create tests under:

```text
tests/
```

Use `pytest` unless the learning environment specifies another testing framework.

The tests should focus on **behavior**, not implementation details.

---

## Test 1 — Document Generation

Test:

```python
build_book_document(book)
```

Verify that the result contains:

* Title
* Author
* Description
* Themes
* Setting
* Genre
* Year

---

## Test 2 — Document Count

Verify:

```python
len(build_book_documents(books)) == len(books)
```

Expected:

```text
8 documents
```

---

## Test 3 — Metadata Generation

Verify every metadata object contains:

```text
title
author
genre
year
rating
pages
```

Also verify that:

```text
year
rating
pages
```

remain numeric.

This is important because ChromaDB metadata filtering depends on correct data types.

---

## Test 4 — Genre Filter

Run the Fantasy/Science Fiction filter.

Verify:

```python
result["genre"] in {"Fantasy", "Science Fiction"}
```

for every result.

---

## Test 5 — Rating Filter

Run:

```text
rating >= 4.3
```

Verify:

```python
result["rating"] >= 4.3
```

for every result.

---

## Test 6 — Combined Search

Run the dystopian semantic query with:

```text
rating >= 4.0
```

Verify that every returned result satisfies the rating constraint.

Do not require an exact semantic ranking unless the embedding configuration is intentionally fixed.

---

# 25. Semantic Search Testing Strategy

Semantic search is different from deterministic metadata filtering.

Avoid tests like:

```python
assert results[0].title == "Harry Potter..."
```

unless the embedding model and configuration are explicitly fixed.

Prefer behavioral assertions such as:

```text
- Results are returned.
- Results do not exceed n_results.
- Results contain valid book IDs.
- Results contain distances.
- Results contain expected metadata.
```

This makes the tests more robust.

---

# 26. Phase 12 — Bonus: Decade Filtering

Implement filtering by publication decade.

Example:

```text
Books published during the 1990s
```

Possible condition:

```python
{
    "$and": [
        {"year": {"$gte": 1990}},
        {"year": {"$lte": 1999}}
    ]
}
```

Verify the exact filter syntax supported by the installed ChromaDB version.

### Goal

Practice combining multiple numeric metadata constraints.

---

# 27. Bonus: Page Count Filtering

Implement a search for books with a page count within a range.

Example:

```text
Books between 250 and 400 pages
```

Conceptually:

```text
250 <= pages <= 400
```

This reinforces numeric metadata filtering.

---

# 28. Bonus: Multiple Theme Search

The current dataset stores themes as a comma-separated string:

```text
friendship, courage, good vs evil, coming of age
```

Investigate whether themes should instead be modeled as structured metadata.

Potential representation:

```python
"themes": [
    "friendship",
    "courage",
    "coming of age",
]
```

Before changing the representation, investigate the metadata capabilities and limitations of the installed ChromaDB version.

### Learning Goal

Understand when information should be:

* Semantic document content.
* Structured metadata.
* Separate database entities.

---

# 29. Phase 13 — Configuration Improvements

After the required exercise works, consider moving configuration to environment variables.

Potential variables:

```text
CHROMA_PERSIST_DIRECTORY
CHROMA_COLLECTION_NAME
```

The application should be able to change its environment-specific configuration without modifying source code.

---

# 30. Phase 14 — Logging

Replace large amounts of debugging `print()` statements with Python's standard:

```python
logging
```

module.

Use appropriate levels:

```text
DEBUG
INFO
WARNING
ERROR
```

Keep user-facing search results in the presentation layer.

Use logs for application diagnostics.

---

# 31. Phase 15 — Validation

Consider adding validation for the book data.

Validate:

* ID is present.
* ID is unique.
* Title is non-empty.
* Author is non-empty.
* Genre is non-empty.
* Year is an integer.
* Rating is numeric.
* Pages is a positive integer.
* Description is non-empty.

For a larger project, consider introducing a typed model such as a dataclass or Pydantic model.

---

# 32. Phase 16 — Error Handling

Handle common failure scenarios:

* Empty book dataset.
* Duplicate book IDs.
* Missing metadata.
* Invalid numeric values.
* ChromaDB initialization failure.
* Invalid search parameters.
* Empty search query.

Do not silently swallow errors.

Errors should either be:

* Properly handled.
* Logged and surfaced.
* Raised with useful context.

---

# 33. Phase 17 — Dependency Management

Create:

```text
requirements.txt
```

Document the required dependencies.

At minimum, the project will need the dependencies required by the chosen ChromaDB setup and test framework.

Example structure:

```text
chromadb
pytest
```

Add other packages only when they are actually used.

Avoid unnecessary dependencies.

---

# 34. Phase 18 — Documentation

Update `README.md` with:

## Project Overview

Explain what the project demonstrates.

## Architecture

Document the module responsibilities.

## Installation

Explain how to create the environment and install dependencies.

## Usage

Show:

```bash
python3.11 scripts/run_search.py
```

## Testing

Show:

```bash
pytest
```

## Search Examples

Document:

* Similarity search.
* Genre filtering.
* Rating filtering.
* Combined search.

## Future Improvements

Document possible extensions such as:

* API.
* Web UI.
* More advanced ranking.
* Hybrid search.
* Larger datasets.

---

# 35. Definition of Done

The required implementation is complete when all of the following are true.

## Data

* [ ] All 8 books are loaded.
* [ ] Every book has a unique ID.
* [ ] All required fields are present.
* [ ] Numeric fields have correct types.

## Documents

* [ ] Every book has a semantic document.
* [ ] Documents contain title.
* [ ] Documents contain author.
* [ ] Documents contain description.
* [ ] Documents contain themes.
* [ ] Documents contain setting.
* [ ] Documents contain genre.
* [ ] Documents contain year.

## Metadata

* [ ] Title is stored as metadata.
* [ ] Author is stored as metadata.
* [ ] Genre is stored as metadata.
* [ ] Year is stored as metadata.
* [ ] Rating is stored as metadata.
* [ ] Pages is stored as metadata.

## ChromaDB

* [ ] Collection is created/retrieved correctly.
* [ ] Books are indexed.
* [ ] Re-running the application does not create logical duplicates.
* [ ] Persistent storage works if enabled.

## Similarity Search

* [ ] Semantic search works.
* [ ] Query is configurable.
* [ ] `n_results` is configurable.
* [ ] Distances are available.
* [ ] Metadata is returned.

## Metadata Filtering

* [ ] `$in` genre filtering works.
* [ ] `$gte` rating filtering works.
* [ ] Numeric metadata types are preserved.

## Combined Search

* [ ] Semantic search works with metadata constraints.
* [ ] Rating constraint is applied by ChromaDB.
* [ ] Results respect the rating requirement.

## Architecture

* [ ] Data is separate from application logic.
* [ ] Document generation is separate.
* [ ] ChromaDB initialization is isolated.
* [ ] Repository handles database operations.
* [ ] Search service handles search behavior.
* [ ] Result models represent application-level results.
* [ ] Presentation handles output.
* [ ] Runner handles orchestration.

## Testing

* [ ] Document tests pass.
* [ ] Metadata tests pass.
* [ ] Filtering tests pass.
* [ ] Combined-search tests pass.

---

# 36. Recommended Implementation Order

Do not implement everything at once.

Follow this sequence:

### Step 1 — Setup

* [ ] Create project.
* [ ] Create virtual environment.
* [ ] Install dependencies.
* [ ] Create project structure.

### Step 2 — Data

* [ ] Add `books.py`.
* [ ] Verify the dataset.

### Step 3 — Documents

* [ ] Implement document construction.
* [ ] Test document generation.

### Step 4 — Configuration

* [ ] Create `config.py`.
* [ ] Define collection/storage configuration.

### Step 5 — Vector Store

* [ ] Initialize ChromaDB.
* [ ] Create/retrieve collection.

### Step 6 — Repository

* [ ] Implement indexing.
* [ ] Implement retrieval.
* [ ] Implement semantic querying.
* [ ] Implement metadata filtering.

### Step 7 — Search Service

* [ ] Implement similarity search.
* [ ] Implement genre filter.
* [ ] Implement rating filter.
* [ ] Implement combined search.

### Step 8 — Models

* [ ] Create result models.
* [ ] Convert raw ChromaDB results into application-level objects.

### Step 9 — Presentation

* [ ] Implement console output.

### Step 10 — Runner

* [ ] Connect all components.
* [ ] Run the four required exercises.

### Step 11 — Tests

* [ ] Add unit tests.
* [ ] Add integration-style search tests.
* [ ] Run the complete test suite.

### Step 12 — Bonus

Only after the required functionality is stable:

* [ ] Decade filtering.
* [ ] Page-count filtering.
* [ ] Theme search.
* [ ] CLI arguments.
* [ ] Environment configuration.
* [ ] Logging improvements.
* [ ] API layer.

---

# 37. Final Architecture

The final application should follow this architecture:

```text
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
                │     CLI      │      │ Future API   │
                │  display.py  │      │   FastAPI    │
                └──────────────┘      └──────────────┘
```

---

# 38. Core Design Principles

Throughout the implementation, follow these principles:

### 1. Separation of Concerns

Each module should have one clear responsibility.

### 2. Reusability

Search functionality should not depend on console output.

### 3. Testability

Business logic should be testable without depending on the CLI.

### 4. Low Coupling

Only the repository layer should be heavily coupled to ChromaDB.

### 5. Correct Data Modeling

Use documents for semantic meaning and metadata for structured filtering.

### 6. Idempotent Operations

Running the indexing process repeatedly should not create logical duplicates.

### 7. Progressive Complexity

Start with the required exercise.

Then add:

```text
Filtering
    ↓
Combined Search
    ↓
Tests
    ↓
Bonus Filters
    ↓
Configuration
    ↓
API
```

Do not introduce unnecessary complexity before the core functionality works.

---

# 39. Final Success Criteria

The project should ultimately allow the following workflow:

```text
Raw Books
    │
    ▼
Build Semantic Documents
    │
    ▼
Build Structured Metadata
    │
    ▼
Index into ChromaDB
    │
    ▼
┌───────────────────────────────────┐
│                                   │
│  Semantic Similarity Search       │
│                                   │
│  Metadata Filtering               │
│                                   │
│  Semantic + Metadata Search       │
│                                   │
└───────────────────────────────────┘
    │
    ▼
Application-Level Results
    │
    ▼
CLI / Future API
```

The final goal is not simply to make the four example queries work.

The goal is to understand how to take a simple ChromaDB exercise and turn it into a **small, clean, testable search application** that could later be extended into a larger recommendation or RAG system.
