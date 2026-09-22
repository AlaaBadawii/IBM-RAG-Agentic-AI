""" OpenRouter client for the Image Captioning application. """
import logging
import time

from openai import OpenAI, OpenAIError

from ..config import get_model_config

logger = logging.getLogger(__name__)


class OpenRouterError(Exception):
    """Raised when communication with OpenRouter fails."""


class OpenRouterClient:
    """Client for interacting with the OpenRouter API."""

    def __init__(self, config: dict | None = None, timeout: int = 30):
        cfg = config or get_model_config()
        self.client = OpenAI(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
        )
        self.model_name = cfg["model_name"]
        self.timeout = timeout
        self._usage_info = None

    def chat(self, messages):
        """Send a chat request to the OpenRouter API."""
        start = time.time()
        try:
            logger.info("Sending request to model: %s", self.model_name)
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                timeout=self.timeout,
            )
            elapsed = time.time() - start
            self._usage_info = {
                "model": self.model_name,
                "duration": round(elapsed, 2),
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            }
            logger.info("Request completed in %.2fs", elapsed)
            return response.choices[0].message.content

        except OpenAIError as e:
            elapsed = time.time() - start
            logger.error("API error after %.2fs: %s", elapsed, e)
            raise OpenRouterError(f"Failed to communicate with OpenRouter: {e}")

    @property
    def usage(self):
        return self._usage_info


if __name__ == "__main__":
    client = OpenRouterClient()
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello. Respond with exactly: connection successful."}
    ]
    try:
        caption = client.chat(messages)
        print(caption)
    except OpenRouterError as e:
        print(e)
