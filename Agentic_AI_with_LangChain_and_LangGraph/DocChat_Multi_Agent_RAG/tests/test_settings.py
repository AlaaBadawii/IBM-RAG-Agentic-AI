"""Tests for ``config.settings``, including the Watsonx configuration."""

import pytest

from config.constants import ALLOWED_TYPES, MAX_FILE_SIZE, MAX_TOTAL_SIZE
from config.settings import Settings

WATSONX_ENV_VARS = (
    "WATSONX_API_KEY",
    "WATSONX_PROJECT_ID",
    "WATSONX_PROJECT_NAME",
    "WATSONX_URL",
    "WATSONX_MODEL_ID",
)


@pytest.fixture
def without_watsonx_env(monkeypatch):
    for name in WATSONX_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_existing_settings_keep_their_defaults(without_watsonx_env):
    settings = Settings(_env_file=None)

    assert settings.MAX_FILE_SIZE == MAX_FILE_SIZE
    assert settings.MAX_TOTAL_SIZE == MAX_TOTAL_SIZE
    assert settings.ALLOWED_TYPES == ALLOWED_TYPES
    assert settings.CHROMA_DB_PATH == "./chroma_db"
    assert settings.CHROMA_COLLECTION_NAME == "documents"
    assert settings.VECTOR_SEARCH_K == 10
    assert settings.HYBRID_RETRIEVER_WEIGHTS == [0.4, 0.6]
    assert settings.LOG_LEVEL == "INFO"
    assert settings.CACHE_DIR == "document_cache"
    assert settings.CACHE_EXPIRE_DAYS == 7
    assert settings.DOCLING_DO_OCR is False
    assert settings.DOCLING_DO_TABLE_STRUCTURE is False
    assert settings.DOCLING_DOCUMENT_TIMEOUT == 300.0


def test_watsonx_settings_are_optional_by_default(without_watsonx_env):
    settings = Settings(_env_file=None)

    assert settings.WATSONX_API_KEY is None
    assert settings.WATSONX_PROJECT_ID is None
    assert settings.WATSONX_PROJECT_NAME is None
    assert settings.WATSONX_URL is None
    assert settings.WATSONX_MODEL_ID is None


def test_watsonx_settings_map_from_environment(monkeypatch):
    values = {
        "WATSONX_API_KEY": "env-api-key",
        "WATSONX_PROJECT_ID": "env-project-id",
        "WATSONX_PROJECT_NAME": "env-project-name",
        "WATSONX_URL": "https://env.example.invalid",
        "WATSONX_MODEL_ID": "ibm/env-model",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    settings = Settings(_env_file=None)

    assert settings.WATSONX_API_KEY == values["WATSONX_API_KEY"]
    assert settings.WATSONX_PROJECT_ID == values["WATSONX_PROJECT_ID"]
    assert settings.WATSONX_PROJECT_NAME == values["WATSONX_PROJECT_NAME"]
    assert settings.WATSONX_URL == values["WATSONX_URL"]
    assert settings.WATSONX_MODEL_ID == values["WATSONX_MODEL_ID"]


def test_watsonx_settings_load_from_dotenv_file(tmp_path, without_watsonx_env):
    values = {
        "WATSONX_API_KEY": "dotenv-api-key",
        "WATSONX_PROJECT_ID": "dotenv-project-id",
        "WATSONX_PROJECT_NAME": "dotenv-project-name",
        "WATSONX_URL": "https://dotenv.example.invalid",
        "WATSONX_MODEL_ID": "ibm/dotenv-model",
    }
    env_file = tmp_path / ".env"
    env_file.write_text("\n".join(f"{name}={value}" for name, value in values.items()))

    settings = Settings(_env_file=env_file)

    assert settings.WATSONX_API_KEY == values["WATSONX_API_KEY"]
    assert settings.WATSONX_PROJECT_ID == values["WATSONX_PROJECT_ID"]
    assert settings.WATSONX_PROJECT_NAME == values["WATSONX_PROJECT_NAME"]
    assert settings.WATSONX_URL == values["WATSONX_URL"]
    assert settings.WATSONX_MODEL_ID == values["WATSONX_MODEL_ID"]
