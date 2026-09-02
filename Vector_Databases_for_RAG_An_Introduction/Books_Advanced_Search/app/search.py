"""Book search functionality."""

class BookSearchService:
    """Service for searching books in the repository."""

    def __init__(self, repository):
        self.repository = repository

    def search_similar_books(self, query, n_results=3):
        """Search for books based on a query."""
        return self.repository.search_books(query, n_results=n_results)

    def get_book(self, book_id):
        """Retrieve a book by its ID."""
        return self.repository.get_book(book_id)

    def get_books(self, book_id):
        """Retrieve a book by its ID."""
        return self.repository.get_books(book_id)
