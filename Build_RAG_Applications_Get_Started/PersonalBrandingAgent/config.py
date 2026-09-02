"""Config values for the application"""
from dotenv import load_dotenv
import os

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")

MODEL_ID = "deepseek/deepseek-v4-flash"
GEN_PARAMS = {
    "max_new_tokens": 800,
    "temperature": 0.7
}

OPENROUTE_BASE_URL = "https://openrouter.ai/api/v1"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHROMA_DIR = "chroma_db"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K = 5