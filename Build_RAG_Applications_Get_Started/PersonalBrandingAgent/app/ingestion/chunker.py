"""Text cleaning and chunking.

Chunking uses RecursiveCharacterTextSplitter (modern langchain_text_splitters
API — not the old IBM-lab CharacterTextSplitter import path). IDs are
deterministic: <content_hash>:<chunk_index>, so re-ingesting unchanged
content produces identical IDs and Chroma upserts in place.
"""
import hashlib
import re

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import CHUNK_SIZE, CHUNK_OVERLAP


def content_hash(text: str) -> str:
    """Stable SHA-256 of the *cleaned* text — change detection key."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_text(text: str) -> str:
    """Normalize whitespace while preserving structure (headings, bullets)."""
    # Strip trailing whitespace per line, collapse 3+ blank lines to 2.
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def chunk_id(doc_hash: str, index: int) -> str:
    """Deterministic Chroma document id: <source hash>:<chunk index>."""
    return f"{doc_hash}:{index}"


def chunk_document(text: str, chunk_size: int = CHUNK_SIZE,
                   chunk_overlap: int = CHUNK_OVERLAP) -> list[Document]:
    """Split one document into chunks. Page content only; metadata is
    attached by the pipeline (it needs the content hash of the full file)."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.create_documents([text])
