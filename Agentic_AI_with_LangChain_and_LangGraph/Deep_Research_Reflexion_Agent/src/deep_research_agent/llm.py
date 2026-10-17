"""LLM client for the Deep Research Reflexion Agent.

The watsonx.ai client is created lazily, on first use, so that importing this
module (or any module that imports it) never authenticates against IBM Cloud
and never performs a network request. Call :func:`get_llm` to obtain the cached
client.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_ibm import ChatWatsonx
from pydantic import SecretStr

load_dotenv()

REQUIRED_ENV_VARS = (
    "WATSONX_PROJECT_ID",
    "WATSONX_URL",
    "WATSONX_MODEL_ID",
    "WATSONX_API_KEY",
)


def missing_env_vars() -> list[str]:
    """Return the required environment variables that are unset or empty."""

    return [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]


@lru_cache(maxsize=1)
def get_llm() -> ChatWatsonx:
    """Return a cached ``ChatWatsonx`` client, building it on first call.

    Raises:
        OSError: if any required environment variable is missing, with a
            message that names the variables and points at ``.env.example``.
    """

    missing = missing_env_vars()
    if missing:
        raise OSError(
            "Missing required environment variables: "
            f"{', '.join(missing)}. Copy .env.example to .env and fill in your "
            "IBM watsonx.ai credentials."
        )

    return ChatWatsonx(
        project_id=os.environ["WATSONX_PROJECT_ID"],
        url=SecretStr(os.environ["WATSONX_URL"]),
        model_id=os.environ["WATSONX_MODEL_ID"],
        apikey=SecretStr(os.environ["WATSONX_API_KEY"]),
    )


if __name__ == "__main__":
    # Smoke-test the LLM. This performs a real network request and therefore
    # requires valid watsonx.ai credentials.
    prompt = "Any ideas for a healthy breakfast"
    response = get_llm().invoke(prompt)
    print(f"Prompt: {prompt}\nResponse: {response}")
