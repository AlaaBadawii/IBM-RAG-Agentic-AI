"""Configurations for the Image Captioning application."""
import os

from dotenv import load_dotenv

load_dotenv()


MODEL_REGISTRY = {
    "primary": os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash"),
    "fallback": os.getenv("OPENROUTER_FALLBACK_MODEL", ""),
}


def get_model_config(model_name: str = None) -> dict:
    """Return model configuration, validating required variables."""
    name = model_name or os.environ.get("OPENROUTER_MODEL", "")
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    if not name:
        raise ValueError("OPENROUTER_MODEL is not set")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not set")

    return {"model_name": name, "api_key": api_key, "base_url": base_url}


def get_available_models() -> list:
    """Return list of configured model names."""
    models = [os.environ.get("OPENROUTER_MODEL", MODEL_REGISTRY["primary"])]
    fallback = os.environ.get("OPENROUTER_FALLBACK_MODEL", MODEL_REGISTRY["fallback"])
    if fallback:
        models.append(fallback)
    return models


model_config = get_model_config()