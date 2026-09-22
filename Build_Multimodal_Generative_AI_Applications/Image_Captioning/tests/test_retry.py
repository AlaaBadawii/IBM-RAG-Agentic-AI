"""Tests for retry and resilience."""
import time
from unittest.mock import Mock, patch

import pytest

from src.clients.openrouter import OpenRouterClient, OpenRouterError
from src.services.vision import VisionService
from src.exceptions import RetryExhaustedError


def test_retry_succeeds_on_second_attempt():
    """Test that retry succeeds after a transient failure."""
    config = {"api_key": "test-key", "base_url": "https://openrouter.ai/api/v1", "model_name": "test/model"}
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Success!"))]

    with patch("src.services.vision.OpenRouterClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.chat.side_effect = [OpenRouterError("Temporary failure"), "Success!"]
        mock_instance.model_name = "test/model"
        mock_instance.usage = {}
        service = VisionService(model_name="test/model", max_retries=3)
        service.client = mock_instance
        result = service.caption_image("assets/image-1.jpg")
        assert result.text == "Success!"
        assert mock_instance.chat.call_count == 2


def test_retry_exhausted_raises_error():
    """Test that all retries exhausted raises RetryExhaustedError."""
    config = {"api_key": "test-key", "base_url": "https://openrouter.ai/api/v1", "model_name": "test/model"}

    with patch("src.services.vision.OpenRouterClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.chat.side_effect = OpenRouterError("Always fails")
        service = VisionService(model_name="test/model", max_retries=3)
        service.client = mock_instance
        with pytest.raises(RetryExhaustedError):
            service.caption_image("assets/image-1.jpg")
        assert mock_instance.chat.call_count == 3


def test_retry_backoff_delay():
    """Test that retry waits between attempts."""
    config = {"api_key": "test-key", "base_url": "https://openrouter.ai/api/v1", "model_name": "test/model"}

    with patch("src.services.vision.OpenRouterClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.chat.side_effect = OpenRouterError("Fail")
        service = VisionService(model_name="test/model", max_retries=2)
        service.client = mock_instance
        with patch("src.services.vision.time.sleep") as mock_sleep:
            with pytest.raises(RetryExhaustedError):
                service.caption_image("assets/image-1.jpg")
            mock_sleep.assert_called_with(1)


def test_vision_service_uses_correct_max_retries():
    """Test that max_retries is properly set."""
    config = {"api_key": "test-key", "base_url": "https://openrouter.ai/api/v1", "model_name": "test/model"}
    service = VisionService(model_name="test/model", max_retries=5)
    assert service.max_retries == 5
