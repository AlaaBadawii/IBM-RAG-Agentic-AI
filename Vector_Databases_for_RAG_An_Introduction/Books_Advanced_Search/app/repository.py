"""Repository for managing book data."""

from app.documents import build_book_documents, build_metadatas
from app.vector_store import create_client, get_collection


class BookRepository:
    """Repository class for managing book data."""

    def __init__(self):
        """Initialize the BookRepository with a ChromaDB client and collection."""
        self.client = create_client()
        self.collection = get_collection(self.client)

    def add_book(self, book: dict):
        """Add a book to the repository."""
        book_id = book.get("id")

        if not book_id:
            raise ValueError("Book must have an 'id' field.")

        documents = build_book_documents([book])
        metadatas = build_metadatas([book])

        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=[book_id],
        )

    def get_book(self, book_id):
        """Retrieve a book from the repository by its ID."""
        result = self.collection.get(ids=[book_id])

        if result["ids"] and result["documents"] and result["metadatas"]:
            return {
                "id": result["ids"][0],
                "document": result["documents"][0],
                "metadata": result["metadatas"][0],
            }

        return None


    def upsert_book(self, book: dict):
        """Upsert a book in the repository."""
        book_id = book.get("id")

        if not book_id:
            raise ValueError("Book must have an 'id' field.")

        documents = build_book_documents([book])
        metadatas = build_metadatas([book])

        self.collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=[book_id],
        )

    def get_books(self, book_id):
        """Retrieve a book from the repository by its ID."""
        result = self.collection.get(ids=[book_id])

        if result["ids"] and result["documents"] and result["metadatas"]:
            return {
                "id": result["ids"][0],
                "document": result["documents"][0],
                "metadata": result["metadatas"][0],
            }

        return None

    def search_books(self, query, n_results=3):
        """Search for books based on semantic similarity."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
        )

        return [
            {
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
            }
            for i in range(len(results["ids"][0]))
        ]

    def update_book(self, book_id, updated_book):
        """Update an existing book in the repository."""
        updated_book = {**updated_book, "id": book_id}

        documents = build_book_documents([updated_book])
        metadatas = build_metadatas([updated_book])

        self.collection.update(
            ids=[book_id],
            documents=documents,
            metadatas=metadatas,
        )

    def delete_book(self, book_id):
        """Delete a book from the repository by its ID."""
        self.collection.delete(ids=[book_id])

    def filter_books(self, filters):
        """Filter books based on metadata attributes."""
        results = self.collection.get(
            where=filters
        )

        return [
            {
                "id": results["ids"][i],
                "document": results["documents"][i],
                "metadata": results["metadatas"][i],
            }
            for i in range(len(results["ids"]))
        ]
