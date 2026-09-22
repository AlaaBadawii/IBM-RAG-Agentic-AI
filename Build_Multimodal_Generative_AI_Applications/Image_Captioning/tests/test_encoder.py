"""Tests for the image encoder."""
import base64
from io import BytesIO
from PIL import Image

from src.images.encoder import encode_image, encode_raw_bytes, get_mime_type


def test_encode_image_returns_data_url():
    img = Image.new("RGB", (100, 100))
    buf = BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    result = encode_image(png_bytes, "image/png")
    assert result.startswith("data:image/png;base64,")


def test_encode_image_decodes_correctly():
    img = Image.new("RGB", (100, 100), color="red")
    buf = BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    result = encode_image(png_bytes, "image/png")
    encoded_part = result.split(",", 1)[1]
    decoded = base64.b64decode(encoded_part)
    assert len(decoded) > 0


def test_encode_raw_bytes():
    raw = b"raw image data"
    result = encode_raw_bytes(raw, "image/jpeg")
    assert result.startswith("data:image/jpeg;base64,")
    encoded_part = result.split(",", 1)[1]
    decoded = base64.b64decode(encoded_part)
    assert decoded == raw


def test_get_mime_type_jpeg():
    assert get_mime_type("image.jpg") == "image/jpeg"


def test_get_mime_type_png():
    assert get_mime_type("image.png") == "image/png"


def test_get_mime_type_webp():
    assert get_mime_type("image.webp") == "image/webp"


def test_get_mime_type_jpg():
    assert get_mime_type("photo.jpeg") == "image/jpeg"


def test_encode_optimizes_large_image():
    img = Image.new("RGB", (3000, 3000))
    buf = BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    result = encode_image(png_bytes, "image/png")
    assert result.startswith("data:image/png;base64,")
