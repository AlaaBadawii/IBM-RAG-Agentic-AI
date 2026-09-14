"""Tests for the book filtering functionality."""
from app.repository import BookRepository
from app.search import BookSearchService
from utils import print_books


def test_filter_books_by_genre():
    """Test filtering books based on genre."""
    book_search_service = BookSearchService(repository=BookRepository())

    where = {
        "genre": {"$in": ["Fantasy", "Science Fiction"]}
    }

    results = book_search_service.filter_books(where)

    print("Filtered books by genre")

    print_books(results)

def test_filter_books_by_rating():
    """Test filtering books by minimum rating."""
    book_search_service = BookSearchService(repository=BookRepository())

    where = {"rating": {"$gte": 4.3}}

    results = book_search_service.filter_books(where)
    print("Filtered books by rating")

    print_books(results)
