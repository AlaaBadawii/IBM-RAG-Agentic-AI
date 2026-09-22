"""Loader for image files with security boundaries."""
import os
import re
from io import BytesIO
from urllib.parse import urlparse

from PIL import Image, UnidentifiedImageError

SUPPORTED_FORMATS = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_URL_SCHEMES = {"https"}
BLOCKED_LOCAL_PATHS = {"/etc", "/root", "/usr", "/var", "/proc", "/sys", "/dev"}


class InvalidImageError(Exception):
    """Raised when an image file fails validation."""


class SecurityError(Exception):
    """Raised when a security boundary is violated."""


def load_image(image_path: str) -> Image.Image:
    """Load an image from a local file or remote URL with security checks."""
    if image_path.startswith(("http://", "https://")):
        return _load_from_url(image_path)
    else:
        return _load_from_local(image_path)


def _load_from_local(image_path: str) -> Image.Image:
    """Load an image from the local filesystem with security checks."""
    _validate_local_path(image_path)
    if not os.path.exists(image_path):
        raise InvalidImageError(f"File not found: {image_path}")
    file_size = os.path.getsize(image_path)
    if file_size > MAX_FILE_SIZE:
        raise InvalidImageError(f"File too large: {file_size} bytes (max {MAX_FILE_SIZE})")
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    ext = image_path.rsplit(".", 1)[-1].lower()
    if ext not in SUPPORTED_FORMATS:
        raise InvalidImageError(f"Unsupported image format: {ext}")
    try:
        img = Image.open(BytesIO(image_bytes))
        img.verify()
    except UnidentifiedImageError:
        raise InvalidImageError(f"File is not a valid image: {image_path}")
    return Image.open(BytesIO(image_bytes))


def _load_from_url(url: str) -> Image.Image:
    """Load an image from a URL with SSRF protection."""
    _validate_url(url)
    import requests
    parsed = urlparse(url)
    hostname = parsed.hostname
    if hostname in ["localhost", "127.0.0.1", "0.0.0.0"]:
        raise SecurityError(f"Access to local addresses is blocked: {url}")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    image_bytes = response.content
    img = Image.open(BytesIO(image_bytes))
    img.verify()
    return Image.open(BytesIO(image_bytes))


def _validate_local_path(image_path: str) -> None:
    """Check that the local path is not in a restricted directory."""
    abs_path = os.path.abspath(image_path)
    for blocked in BLOCKED_LOCAL_PATHS:
        if abs_path.startswith(blocked):
            raise SecurityError(f"Access to {blocked} is not allowed")


def _validate_url(url: str) -> None:
    """Check that the URL uses an allowed scheme and is not SSRF."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        raise SecurityError(f"URL scheme '{parsed.scheme}' is not allowed. Only https is permitted.")
    if not re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', parsed.hostname or ""):
        raise SecurityError(f"Invalid hostname: {parsed.hostname}")


def validate_image(image_path: str) -> dict:
    """Validate an image and return metadata."""
    if image_path.startswith(("http://", "https://")):
        _validate_url(image_path)
        return {"source": "url", "valid": True, "path": image_path}
    else:
        _validate_local_path(image_path)
        if not os.path.exists(image_path):
            raise InvalidImageError(f"File not found: {image_path}")
        ext = image_path.rsplit(".", 1)[-1].lower()
        return {"source": "local", "valid": True, "path": image_path, "format": ext}