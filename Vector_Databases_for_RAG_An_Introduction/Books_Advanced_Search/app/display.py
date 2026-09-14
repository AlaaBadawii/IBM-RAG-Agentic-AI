"""Display functions for the book search application."""
from app.models import BookSearchResult


def display_similarity_results(results: list[BookSearchResult]):
    """Display the results of a similarity search."""
    if not results:
        print("No similar books found.")
        return

    print("\nSimilar Books:")
    for i, book in enumerate(results, start=1):
        print(f"{i}. {book.title} by {book.author} (Genre: {book.genre}, Rating: {book.rating})")
        if book.distance is not None:
            print(f"   Similarity Score: {book.distance:.4f}")
