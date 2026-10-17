"""Shared, offline-safe test configuration for the Deep Research Reflexion Agent.

The default suite must run without real IBM watsonx.ai or Tavily credentials
and must never contact an external service. Placeholder credentials are seeded
here, before any project module is imported, and every test mocks the model and
search calls that it needs.

The package under test is imported from the editable installation rather than
by manipulating ``sys.path``.
"""

import os

# ``dotenv.load_dotenv`` does not override variables that are already set, so
# these placeholders shadow any real values in a local ``.env`` file.
_PLACEHOLDER_ENV = {
    "WATSONX_PROJECT_ID": "test-project-id",
    "WATSONX_URL": "https://eu-de.ml.cloud.ibm.com",
    "WATSONX_MODEL_ID": "ibm/granite-4-h-small",
    "WATSONX_API_KEY": "test-api-key",
    "TAVILY_API_KEY": "test-tavily-api-key",
}

for _key, _value in _PLACEHOLDER_ENV.items():
    os.environ.setdefault(_key, _value)
