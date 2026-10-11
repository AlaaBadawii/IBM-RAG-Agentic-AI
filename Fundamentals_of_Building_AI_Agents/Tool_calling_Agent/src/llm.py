"""Configuration file for the LLM agent."""

import warnings

from ibm_watsonx_ai.utils.warnings import WatsonxAPIWarning

warnings.filterwarnings(
    "ignore",
    message=r"The value of 'max_tokens'.*",
    category=WatsonxAPIWarning,
)

import os

from dotenv import load_dotenv
from langchain_ibm import ChatWatsonx
from pydantic import SecretStr

import tools

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
    api_key=SecretStr(api_key),
    project_id=project_id,
    url=SecretStr(url),
    model_id=model_id,
    params={"temperature": 0.7, "max_output_tokens": 512}
)



llm_with_tools = llm.bind_tools(list(tools.tools.values()))

if __name__ == "__main__":
    print("Testing Watsonx connection...")

    response = llm_with_tools.invoke("Search YouTube for Python tutorials.")

    print("\nTool calls:")
    print(response.tool_calls)

    print("\nModel response:")
    print(response.content)
    