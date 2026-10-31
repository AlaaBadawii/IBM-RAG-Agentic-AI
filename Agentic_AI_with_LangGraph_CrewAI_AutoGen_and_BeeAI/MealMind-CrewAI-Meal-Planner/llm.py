"""LLM client for the LangGraph-Orchestration-Evaluation lab.

The watsonx.ai client is created lazily, on first use, so that importing this
module (or any module that imports it) never authenticates against IBM Cloud
and never performs a network request. Call :func:`get_llm` to obtain the cached
client.
"""

import os
from functools import lru_cache

from crewai import LLM
from dotenv import load_dotenv

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
def get_llm() -> LLM:
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

    return LLM(
        project_id=os.environ["WATSONX_PROJECT_ID"],
        base_url=os.environ["WATSONX_URL"],
        model=os.environ["WATSONX_MODEL_ID"],
        api_key=os.environ["WATSONX_API_KEY"]
    )
