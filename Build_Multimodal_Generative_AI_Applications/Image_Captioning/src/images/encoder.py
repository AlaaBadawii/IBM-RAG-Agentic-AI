"""Encoder for image files with optimization."""
import base64
from io import BytesIO

from PIL import Image

MAX_DIMENSION = 1024


def encode_image(image_bytes: bytes, mime_type: str, max_dimension: int = MAX_DIMENSION) -> str:
    """Encode image bytes to a data URL string, optionally optimizing size."""
    img = Image.open(BytesIO(image_bytes))
    img = _optimize_image(img, max_dimension)
    buffer = BytesIO()
    fmt = mime_type.split("/")[-1]
    img.save(buffer, format=fmt)
    optimized_bytes = buffer.getvalue()
    encoded = base64.b64encode(optimized_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def encode_raw_bytes(image_bytes: bytes, mime_type: str) -> str:
    """Encode raw image bytes to a data URL string without optimization."""
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _optimize_image(img: Image.Image, max_dimension: int) -> Image.Image:
    """Resize image if either dimension exceeds max_dimension."""
    w, h = img.size
    if w > max_dimension or h > max_dimension:
        ratio = min(max_dimension / w, max_dimension / h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    return img


def get_mime_type(image_path: str) -> str:
    """Determine MIME type from file extension."""
    ext = image_path.rsplit(".", 1)[-1].lower()
    mapping = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "gif": "image/gif",
    }
    return mapping.get(ext, f"image/{ext}")