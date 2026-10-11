import os

from dotenv import load_dotenv
from langchain_ibm import ChatWatsonx
from pydantic import SecretStr

load_dotenv()

required = [
    "WATSONX_API_KEY",
    "WATSONX_PROJECT_ID",
    "WATSONX_URL",
    "WATSONX_MODEL_ID",
]

missing = [key for key in required if not os.getenv(key)]
if missing:
    raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

llm = ChatWatsonx(
    model_id=os.environ["WATSONX_MODEL_ID"],
    url=SecretStr(os.environ["WATSONX_URL"]),
    project_id=os.environ["WATSONX_PROJECT_ID"],
    apikey=SecretStr(os.environ["WATSONX_API_KEY"]),
    params={
        "max_completion_tokens": 1024,
        "temperature": 0.5,
    },
)
