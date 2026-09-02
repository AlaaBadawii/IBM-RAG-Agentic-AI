import os

from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


OPENROUTER_SITE_URL = os.environ.get("OPENROUTER_SITE_URL", "http://localhost:5000")
OPENROUTER_SITE_NAME = os.environ.get("OPENROUTER_SITE_NAME", "GenAI Flask App")

TEMPERATURE = 0
MAX_TOKENS = 256

LLAMA_MODEL_ID = "meta-llama/llama-3.1-8b-instruct"
GRANITE_MODEL_ID = "deepseek/deepseek-r1"
MISTRAL_MODEL_ID = "mistralai/mistral-7b-instruct"
