"""Test the search functionality of the application."""

from app.display import display_similarity_results
from app.repository import BookRepository
from app.search import BookSearchService


def test_search_similar_books():
    """Test searching for similar books."""
    book_search_service = BookSearchService(repository=BookRepository())

    query = "magical fantasy adventure with friendship and courage."
    results = book_search_service.search_similar_books(query, n_results=3)

    print("Test Results:")
    display_similarity_results(results)
