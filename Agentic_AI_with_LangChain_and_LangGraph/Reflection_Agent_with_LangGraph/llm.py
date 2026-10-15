import os

from dotenv import load_dotenv
from langchain_ibm import ChatWatsonx
from pydantic import SecretStr

load_dotenv()

required_vars = [
    "WATSONX_API_KEY",
    "WATSONX_PROJECT_ID",
    "WATSONX_PROJECT_NAME",
    "WATSONX_URL",
    "WATSONX_MODEL_ID",
]

missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise OSError(f"Missing required environment variables: {', '.join(missing_vars)}")

api_key = os.environ["WATSONX_API_KEY"]
project_id = os.environ["WATSONX_PROJECT_ID"]
project_name = os.environ["WATSONX_PROJECT_NAME"]
url = os.environ["WATSONX_URL"]
model_id = os.environ["WATSONX_MODEL_ID"]


llm = ChatWatsonx(
    apikey=SecretStr(api_key),
    project_id=project_id,
    url=SecretStr(url),
    model_id=model_id,
)

