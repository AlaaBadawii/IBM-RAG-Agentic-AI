from app.display import display_similarity_results
from app.repository import BookRepository
from app.search import BookSearchService


def test_combined_semantic_metadata_search_1():
    """Test combined semantic and metadata search."""
    book_search_service = BookSearchService(repository=BookRepository())

    query = "magical fantasy adventure with friendship and courage."
    where = {
        "$and": [
            {"genre": {"$in": ["Fantasy", "Science Fiction"]}},
            {
                "author": {
                    "$in": ["J.R.R. Tolkien", "Isaac Asimov", "F. Scott Fitzgerald"]
                }
            },
        ]
    }

    results = book_search_service.search_similar_books(query, n_results=3, where=where)

    print("Combined semantic and metadata search results:")
    display_similarity_results(results)


def test_combined_semantic_metadata_search_2():
    """Test combined semantic and metadata search."""
    book_search_service = BookSearchService(repository=BookRepository())

    query = "dystopian society control oppression future"
    where = {"rating": {"$gte": 4.0}}

    results = book_search_service.search_similar_books(
        query,
        n_results=3,
        where=where,
    )

    print("Combined semantic and metadata search results:")
    display_similarity_results(results)
