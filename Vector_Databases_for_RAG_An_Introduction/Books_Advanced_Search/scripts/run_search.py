from tests.test_combined_semantic_metadata_search import (
    test_combined_semantic_metadata_search_1,
    test_combined_semantic_metadata_search_2,
)
from tests.test_filter_books import (
    test_filter_books_by_genre,
    test_filter_books_by_rating,
)
from tests.test_search_similar_books import test_search_similar_books

print("=== Book Similarity Search ===")

print("1. Finding magical fantasy adventures")
test_search_similar_books()

print("=== Metadata Filtering ===")
test_filter_books_by_genre()

print("2. Finding Fantasy and Science Fiction books")
test_combined_semantic_metadata_search_1()

print("3. Finding highly-rated books")
test_filter_books_by_rating()

print("=== Combined Search ===")

print("4. Finding highly-rated dystopian books")
test_combined_semantic_metadata_search_2()
