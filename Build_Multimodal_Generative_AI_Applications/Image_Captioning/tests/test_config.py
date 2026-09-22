"""Tests for the configuration."""
import os

import pytest

from src.config import get_model_config, get_available_models


def test_get_model_config_returns_dict(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "test/model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    config = get_model_config()
    assert config["model_name"] == "test/model"
    assert config["api_key"] == "test-key"
    assert config["base_url"] == "https://openrouter.ai/api/v1"


def test_get_model_config_with_custom_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "test/model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    config = get_model_config(model_name="custom/model")
    assert config["model_name"] == "custom/model"


def test_get_model_config_missing_model(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    with pytest.raises(ValueError, match="OPENROUTER_MODEL"):
        get_model_config()


def test_get_model_config_missing_api_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "test/model")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        get_model_config()


def test_get_available_models(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "model-a")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    models = get_available_models()
    assert "model-a" in models
