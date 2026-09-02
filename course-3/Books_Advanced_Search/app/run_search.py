"""Run the search functionality."""

def ingest_books(repository, books):
    """Ingest a list of books into the repository."""
    for book in books:
        repository.upsert_book(book)
