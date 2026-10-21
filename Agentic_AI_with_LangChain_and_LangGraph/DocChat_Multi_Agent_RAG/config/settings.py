from pydantic_settings import BaseSettings
from .constants import (
    MAX_FILE_SIZE as DEFAULT_MAX_FILE_SIZE,
    MAX_TOTAL_SIZE as DEFAULT_MAX_TOTAL_SIZE,
    ALLOWED_TYPES as DEFAULT_ALLOWED_TYPES,
)


class Settings(BaseSettings):
    # Optional settings with defaults
    MAX_FILE_SIZE: int = DEFAULT_MAX_FILE_SIZE
    MAX_TOTAL_SIZE: int = DEFAULT_MAX_TOTAL_SIZE
    ALLOWED_TYPES: list = DEFAULT_ALLOWED_TYPES

    # Database settings
    CHROMA_DB_PATH: str = "./chroma_db"
    CHROMA_COLLECTION_NAME: str = "documents"

    # Retrieval settings
    VECTOR_SEARCH_K: int = 10
    HYBRID_RETRIEVER_WEIGHTS: list = [0.4, 0.6]

    # Logging settings
    LOG_LEVEL: str = "INFO"

    # New cache settings with type annotations
    CACHE_DIR: str = "document_cache"
    CACHE_EXPIRE_DAYS: int = 7

    # Docling PDF pipeline settings. OCR and table-structure models are
    # expensive; disable them by default for text-based PDFs. Enable them for
    # scanned documents or when structured table content is required.
    DOCLING_DO_OCR: bool = False
    DOCLING_DO_TABLE_STRUCTURE: bool = False
    DOCLING_DOCUMENT_TIMEOUT: float = 300.0

    # Watsonx settings (loaded from environment variables or .env).
    # Optional at import time; RelevanceChecker requires the API key.
    WATSONX_API_KEY: str | None = None
    WATSONX_PROJECT_ID: str | None = None
    WATSONX_PROJECT_NAME: str | None = None
    WATSONX_URL: str | None = None
    WATSONX_MODEL_ID: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
