"""Shared IBM watsonx.ai configuration for NourishBot.

Credentials are read from environment variables so the project can run against
a personal IBM Cloud watsonx.ai project. When no API key is supplied, the
client falls back to the configuration used by the IBM Skills Network lab
environment (``project_id="skills-network"``).
"""

import os
from pathlib import Path

from ibm_watsonx_ai import Credentials

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_WATSONX_URL = "https://us-south.ml.cloud.ibm.com"
DEFAULT_WATSONX_PROJECT_ID = "skills-network"

VISION_MODEL_ID = "meta-llama/llama-3-2-90b-vision-instruct"
TEXT_MODEL_ID = "ibm/granite-4-h-small"


def get_watsonx_credentials() -> Credentials:
    """Build watsonx.ai credentials from the environment.

    If ``WATSONX_API_KEY`` is not set, the credentials object is created
    without an API key. This preserves the original lab behaviour, where the
    Skills Network environment injects authentication.
    """
    api_key = os.getenv("WATSONX_API_KEY")
    url = os.getenv("WATSONX_URL") or DEFAULT_WATSONX_URL

    if api_key:
        return Credentials(url=url, api_key=api_key)
    return Credentials(url=url)


def get_watsonx_project_id() -> str:
    """Return the configured watsonx.ai project ID."""
    return os.getenv("WATSONX_PROJECT_ID") or DEFAULT_WATSONX_PROJECT_ID
