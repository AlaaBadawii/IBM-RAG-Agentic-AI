import os

from dotenv import load_dotenv

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

MODELS: dict[str, str] = {
    "llama": "meta-llama/llama-3.1-8b-instruct",
    "llama-70b": "meta-llama/llama-3.3-70b-instruct",
    "mistral": "mistralai/mistral-7b-instruct",
    "deepseek": "deepseek/deepseek-v4-flash",
    "deepseek-r1": "deepseek/deepseek-r1",
    "gemma": "google/gemma-3-4b-it",
    "gemma-27b": "google/gemma-3-27b-it",
    "qwen": "qwen/qwen3-8b",
    "phi": "microsoft/phi-4",
}

GEN_PARAMS: dict[str, int | float] = {
    "temperature": 0.7,
    "max_tokens": 600,
}

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
