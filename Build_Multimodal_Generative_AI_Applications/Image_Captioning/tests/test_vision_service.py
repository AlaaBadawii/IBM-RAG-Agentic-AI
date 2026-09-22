"""Tests for the OpenRouter client and VisionService."""
import pytest
from unittest.mock import Mock, patch

from src.clients.openrouter import OpenRouterClient, OpenRouterError
from src.services.vision import VisionService
from src.models.result import VisionResult
from src.exceptions import RetryExhaustedError


def test_chat_returns_content():
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Hello!"))]
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50
    config = {"api_key": "test-key", "base_url": "https://openrouter.ai/api/v1", "model_name": "test/model"}

    with patch("src.clients.openrouter.OpenAI") as MockOpenAI:
        mock_client = MockOpenAI.return_value
        mock_client.chat.completions.create.return_value = mock_response
        client = OpenRouterClient(config=config)
        result = client.chat([{"role": "user", "content": "Test"}])
        assert result == "Hello!"


def test_chat_raises_on_error():
    from openai import OpenAIError

    config = {"api_key": "test-key", "base_url": "https://openrouter.ai/api/v1", "model_name": "test/model"}

    with patch("src.clients.openrouter.OpenAI") as MockOpenAI:
        mock_client = MockOpenAI.return_value
        mock_client.chat.completions.create.side_effect = OpenAIError("API error")
        client = OpenRouterClient(config=config)
        with pytest.raises(OpenRouterError):
            client.chat([{"role": "user", "content": "Test"}])


def test_chat_has_timeout():
    config = {"api_key": "test-key", "base_url": "https://openrouter.ai/api/v1", "model_name": "test/model"}

    with patch("src.clients.openrouter.OpenAI") as MockOpenAI:
        mock_client = MockOpenAI.return_value
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="OK"))],
            usage=Mock(prompt_tokens=10, completion_tokens=5),
        )
        client = OpenRouterClient(config=config, timeout=15)
        client.chat([{"role": "user", "content": "Test"}])
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["timeout"] == 15


def test_usage_info():
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="OK"))]
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50
    config = {"api_key": "test-key", "base_url": "https://openrouter.ai/api/v1", "model_name": "test/model"}

    with patch("src.clients.openrouter.OpenAI") as MockOpenAI:
        mock_client = MockOpenAI.return_value
        mock_client.chat.completions.create.return_value = mock_response
        client = OpenRouterClient(config=config)
        client.chat([{"role": "user", "content": "Test"}])
        assert client.usage["model"] == "test/model"
        assert client.usage["prompt_tokens"] == 100


def test_caption_image_returns_vision_result(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "test/model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="A beautiful sunset."))]
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    with patch("src.services.vision.OpenRouterClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.chat.return_value = "A beautiful sunset."
        mock_instance.model_name = "test/model"
        mock_instance.usage = {"model": "test/model", "duration": 1.5, "prompt_tokens": 100, "completion_tokens": 50}
        service = VisionService(model_name="test/model")
        service.client = mock_instance
        result = service.caption_image("assets/image-1.jpg")
        assert isinstance(result, VisionResult)
        assert result.text == "A beautiful sunset."
        assert result.model == "test/model"
        assert result.task == "caption"
        assert result.total_tokens == 150


def test_answer_image_question(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "test/model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="The sky is orange."))]
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    with patch("src.services.vision.OpenRouterClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.chat.return_value = "The sky is orange."
        mock_instance.model_name = "test/model"
        mock_instance.usage = {"duration": 1.2}
        service = VisionService(model_name="test/model")
        service.client = mock_instance
        result = service.answer_image_question("assets/image-1.jpg", "What color is the sky?")
        assert isinstance(result, VisionResult)
        assert result.text == "The sky is orange."
        assert result.task == "question"


def test_count_objects(monkeypatch):
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
        mock_instance.usage = {"duration": 1.0}
        service = VisionService(model_name="test/model")
        service.client = mock_instance
        result = service.count_objects("assets/image-1.jpg", "cars")
        assert isinstance(result, VisionResult)
        assert result.text == "There are 3 cars."
        assert result.task == "counting"
        mock_instance.chat.assert_called_once()
        call_args = mock_instance.chat.call_args
        messages = call_args[0][0]
        assert "Count the cars visible in the image." in messages[0]["content"][0]["text"]


def test_service_client_error(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "test/model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    with patch("src.services.vision.OpenRouterClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.chat.side_effect = OpenRouterError("API failed")
        service = VisionService(model_name="test/model", max_retries=3)
        service.client = mock_instance
        with pytest.raises(RetryExhaustedError):
            service.caption_image("assets/image-1.jpg")


def test_service_assess_image(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "test/model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Minor damage."))]
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    with patch("src.services.vision.OpenRouterClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.chat.return_value = "Minor damage."
        mock_instance.model_name = "test/model"
        mock_instance.usage = {"duration": 1.1}
        service = VisionService(model_name="test/model")
        service.client = mock_instance
        result = service.assess_image("assets/image-1.jpg")
        assert isinstance(result, VisionResult)
        assert result.task == "assessment"


def test_service_compare_models(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "model-a")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    from src.config import get_available_models

    with patch("src.services.vision.OpenRouterClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.chat.return_value = "Response"
        mock_instance.model_name = "model-a"
        mock_instance.usage = {"duration": 1.0}
        service = VisionService(model_name="model-a")
        service.client = mock_instance
        results = service.compare_models("assets/image-1.jpg", "Describe the image.")
        assert len(results) == len(get_available_models())


def test_retry_succeeds_on_second_attempt():
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
    with patch("src.services.vision.OpenRouterClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.chat.side_effect = OpenRouterError("Always fails")
        service = VisionService(model_name="test/model", max_retries=3)
        service.client = mock_instance
        with pytest.raises(RetryExhaustedError):
            service.caption_image("assets/image-1.jpg")
        assert mock_instance.chat.call_count == 3


def test_retry_backoff_delay():
    with patch("src.services.vision.OpenRouterClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.chat.side_effect = OpenRouterError("Fail")
        service = VisionService(model_name="test/model", max_retries=2)
        service.client = mock_instance
        with patch("src.services.vision.time.sleep") as mock_sleep:
            with pytest.raises(RetryExhaustedError):
                service.caption_image("assets/image-1.jpg")
            mock_sleep.assert_called_with(1)