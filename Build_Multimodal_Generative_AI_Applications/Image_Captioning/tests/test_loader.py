"""Tests for the image loader."""
import os
import tempfile
from PIL import Image

import pytest

from src.images.loader import load_image, InvalidImageError


def test_load_local_image():
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        img = Image.new("RGB", (10, 10))
        img.save(tmp.name)
        tmp.flush()
        result = load_image(tmp.name)
        assert result.size == (10, 10)


def test_load_missing_file():
    with pytest.raises(InvalidImageError):
        load_image("/nonexistent/path/image.png")


def test_load_unsupported_format():
    with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
        tmp.write(b"not an image")
        tmp.flush()
        with pytest.raises(InvalidImageError):
            load_image(tmp.name)


def test_load_too_large_file():
    with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
        tmp.write(b"x" * (11 * 1024 * 1024))
        tmp.flush()
        with pytest.raises(InvalidImageError):
            load_image(tmp.name)
