"""Book search functionality."""
from app.models import BookSearchResult


class BookSearchService:
    """Service for searching books in the repository."""

    def __init__(self, repository):
        self.repository = repository

    def search_similar_books(self, query, n_results=3, where: dict | None = None):
        """Search for books based on a query."""
        books = self.repository.search_books(query, n_results=n_results, where=where)

        return [
            BookSearchResult(
                id=book["id"],
                title=book["metadata"].get("title"),
                author=book["metadata"].get("author"),
                genre=book["metadata"].get("genre"),
                year=book["metadata"].get("year"),
                rating=book["metadata"].get("rating"),
                distance=book.get("distance"),
            )
            for book in books
        ]

    def filter_books(self, where: dict):
        """Filter books based on specified criteria."""
        return self.repository.filter_books(where)

    def get_book(self, book_id):
        """Retrieve a book by its ID."""
        return self.repository.get_book(book_id)

    def get_books(self):
        """Retrieve all books."""
        return self.repository.get_books()
