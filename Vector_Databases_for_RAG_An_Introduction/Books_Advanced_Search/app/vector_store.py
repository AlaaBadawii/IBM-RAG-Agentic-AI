"""Vector store module for managing vector embeddings and retrieval."""

import chromadb
from chromadb.utils import embedding_functions

from app.config import COLLECTION_NAME, PERSIST_DIRECTORY

embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)


def create_client():
    """Create and return a ChromaDB client instance with persistence."""
    return chromadb.PersistentClient(path=PERSIST_DIRECTORY)


def get_collection(client):
    """Retrieve or create the book collection from the ChromaDB client."""
    return client.get_or_create_collection(
        name=COLLECTION_NAME, embedding_function=embedding_function
    )
