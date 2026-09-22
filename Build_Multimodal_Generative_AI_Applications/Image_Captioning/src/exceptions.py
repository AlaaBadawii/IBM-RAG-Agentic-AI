"""Application-level exceptions."""
import logging

logger = logging.getLogger(__name__)


class VisionError(Exception):
    """Base exception for vision application errors."""


class InvalidImageError(Exception):
    """Raised when an image fails validation."""


class APIError(Exception):
    """Raised when the OpenRouter API call fails."""


class ConfigurationError(Exception):
    """Raised when required configuration is missing."""


class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted."""