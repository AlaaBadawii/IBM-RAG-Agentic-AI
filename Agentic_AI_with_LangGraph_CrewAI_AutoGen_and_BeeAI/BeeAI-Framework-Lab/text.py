import os
import requests
from dotenv import load_dotenv

# Explicitly load .env from the current working directory.
load_dotenv(dotenv_path=".env")

api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    raise ValueError("OPENROUTER_API_KEY was not loaded.")

response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    json={
        "model": "deepseek/deepseek-v4-flash",
        "messages": [
            {"role": "user", "content": "Hello! Are you working?"}
        ],
    },
    timeout=60,
)

print("Status:", response.status_code)
print(response.text)