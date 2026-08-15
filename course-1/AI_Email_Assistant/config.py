import os

from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

MODELS = {
    "deepseek": "deepseek/deepseek-v4-flash",
    "laguna": "meta-llama/llama-3.1-8b-instruct",
    "mistral": "mistralai/mistral-7b-instruct",
    "qwen": "qwen/qwen3-8b",
}

TEMPERATURE = 0.7
MAX_TOKENS = 2000