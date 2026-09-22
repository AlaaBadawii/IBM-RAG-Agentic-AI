"""Vision service with fallback model support."""
import logging
import time

from src.clients.openrouter import OpenRouterClient, OpenRouterError
from src.images.build_image_message import build_image_message
from src.images.encoder import encode_image, get_mime_type
from src.images.loader import InvalidImageError, load_image
from src.models.result import VisionResult
from src.prompts.vision import CAPTION_PROMPT, QUESTION_ANSWERING_PROMPT, ASSESSMENT_PROMPT
from src.exceptions import RetryExhaustedError
from src.config import MODEL_REGISTRY, get_available_models

logger = logging.getLogger(__name__)


class VisionService:
    """High-level service for vision tasks with fallback support."""

    def __init__(self, model_name: str = None, max_retries: int = 3):
        config = None
        if model_name:
            from src.config import get_model_config
            config = get_model_config(model_name)
        self.client = OpenRouterClient(config=config)
        self.max_retries = max_retries

    def _prepare_image(self, image_path: str) -> str:
        """Load and encode an image into a data URL."""
        load_image(image_path)
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        mime_type = get_mime_type(image_path)
        return encode_image(image_bytes, mime_type)

    def _call_with_retry(self, messages) -> str:
        """Call the API with retry logic for transient failures."""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return self.client.chat(messages)
            except OpenRouterError as e:
                last_error = e
                logger.warning("Attempt %d/%d failed: %s", attempt + 1, self.max_retries, e)
                if attempt < self.max_retries - 1:
                    wait = 2 ** attempt
                    logger.info("Retrying in %d seconds...", wait)
                    time.sleep(wait)
        raise RetryExhaustedError(f"All {self.max_retries} retry attempts failed") from last_error

    def _call_with_fallback(self, messages) -> str:
        """Call the primary model, fallback on failure."""
        try:
            return self._call_with_retry(messages)
        except RetryExhaustedError:
            fallback = MODEL_REGISTRY.get("fallback")
            if not fallback:
                raise
            logger.info("Falling back to model: %s", fallback)
            from src.config import get_model_config
            fallback_client = OpenRouterClient(config=get_model_config(fallback))
            try:
                return fallback_client.chat(messages)
            except OpenRouterError as e:
                raise RetryExhaustedError(f"Fallback also failed: {e}") from e

    def _wrap(self, text: str, task: str) -> VisionResult:
        """Wrap a raw text response into a VisionResult."""
        usage = self.client.usage or {}
        metadata = {
            "model": self.client.model_name,
            "duration": usage.get("duration", 0),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }
        logger.info("Task: %s, Model: %s, Tokens: %d", task, self.client.model_name, metadata.get("total_tokens", 0))
        return VisionResult(text=text, model=self.client.model_name, task=task, metadata=metadata)

    def caption_image(self, image_path: str) -> VisionResult:
        """Generate a caption for the given image."""
        data_url = self._prepare_image(image_path)
        messages = build_image_message(data_url, CAPTION_PROMPT)
        text = self._call_with_fallback(messages)
        return self._wrap(text, "caption")

    def answer_image_question(self, image_path: str, question: str) -> VisionResult:
        """Answer a question about the given image."""
        data_url = self._prepare_image(image_path)
        messages = build_image_message(data_url, question)
        text = self._call_with_fallback(messages)
        return self._wrap(text, "question")

    def assess_image(self, image_path: str) -> VisionResult:
        """Assess the given image."""
        data_url = self._prepare_image(image_path)
        messages = build_image_message(data_url, ASSESSMENT_PROMPT)
        text = self._call_with_fallback(messages)
        return self._wrap(text, "assessment")

    def count_objects(self, image_path: str, object_name: str) -> VisionResult:
        """Count objects visible in the image."""
        question = f"Count the {object_name} visible in the image."
        data_url = self._prepare_image(image_path)
        messages = build_image_message(data_url, question)
        text = self._call_with_fallback(messages)
        return self._wrap(text, "counting")

    def extract_information(self, image_path: str, info: str) -> VisionResult:
        """Extract information from the image."""
        question = f"Extract the {info} from the image."
        data_url = self._prepare_image(image_path)
        messages = build_image_message(data_url, question)
        text = self._call_with_fallback(messages)
        return self._wrap(text, "extraction")

    def compare_models(self, image_path: str, question: str) -> dict:
        """Compare responses from primary and fallback models."""
        results = {}
        for model_name in get_available_models():
            service = VisionService(model_name=model_name, max_retries=self.max_retries)
            results[model_name] = service.answer_image_question(image_path, question)
        return results