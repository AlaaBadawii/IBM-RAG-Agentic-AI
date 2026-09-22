"""Integration tests for the full vision pipeline."""
import pytest
from unittest.mock import Mock, patch

from src.services.vision import VisionService
from src.models.result import VisionResult


def test_full_pipeline_caption(monkeypatch):
    """Test the full pipeline: load → encode → build message → call API → result."""
    monkeypatch.setenv("OPENROUTER_MODEL", "test/model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    from src.images.loader import load_image
    from src.images.encoder import encode_image, get_mime_type
    from src.images.build_image_message import build_image_message

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="A test caption."))]
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    with patch("src.services.vision.OpenRouterClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.chat.return_value = "A test caption."
        mock_instance.model_name = "test/model"
        mock_instance.usage = {"duration": 1.5, "prompt_tokens": 100, "completion_tokens": 50}
        service = VisionService(model_name="test/model")
        service.client = mock_instance

        result = service.caption_image("assets/image-1.jpg")

        assert isinstance(result, VisionResult)
        assert result.text == "A test caption."
        assert result.task == "caption"
        assert result.model == "test/model"
        assert result.total_tokens == 150


def test_full_pipeline_question(monkeypatch):
    """Test full pipeline with a custom question."""
    monkeypatch.setenv("OPENROUTER_MODEL", "test/model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="There are 3 cars."))]
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    with patch("src.services.vision.OpenRouterClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.chat.return_value = "There are 3 cars."
        mock_instance.model_name = "test/model"
        mock_instance.usage = {"duration": 1.2}
        service = VisionService(model_name="test/model")
        service.client = mock_instance

        result = service.answer_image_question("assets/image-1.jpg", "How many cars?")

        assert isinstance(result, VisionResult)
        assert result.text == "There are 3 cars."
        assert result.task == "question"


def test_full_pipeline_with_fallback(monkeypatch):
    """Test pipeline with fallback model."""
    monkeypatch.setenv("OPENROUTER_MODEL", "primary/model")
    monkeypatch.setenv("OPENROUTER_FALLBACK_MODEL", "fallback/model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Fallback answer."))]
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    with patch("src.services.vision.OpenRouterClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.chat.return_value = "Fallback answer."
        mock_instance.model_name = "fallback/model"
        mock_instance.usage = {"duration": 1.0}
        service = VisionService(model_name="fallback/model", max_retries=1)
        service.client = mock_instance

        result = service.caption_image("assets/image-1.jpg")
        assert isinstance(result, VisionResult)
        assert result.model == "fallback/model"