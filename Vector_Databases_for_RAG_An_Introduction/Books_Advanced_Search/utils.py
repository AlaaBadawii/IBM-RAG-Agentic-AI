"""Utility functions for the book search application."""

def print_books(books):
    """Print a list of books in a readable format."""
    print("\n\n=== Book Search Results ===\n\n")
    print(f"Number of results: {len(books)}")

    for i, book in enumerate(books, start=1):
        metadata = book.get("metadata", {})

        print(f"Book {i}:")
        print(f"  ID: {book.get('id')}")
        print(f"  Title: {metadata.get('title')}")
        print(f"  Author: {metadata.get('author')}")
        print(f"  Genre: {metadata.get('genre')}")

        if "rating" in metadata:
            print(f"  Rating: {metadata['rating']}")

        if "year" in metadata:
            print(f"  Year: {metadata['year']}")

        if book.get("rank") is not None:
            print(f"  Rank: {book['rank']}")

        if book.get("distance") is not None:
            print(f"  Distance: {book['distance']:.2f}")
