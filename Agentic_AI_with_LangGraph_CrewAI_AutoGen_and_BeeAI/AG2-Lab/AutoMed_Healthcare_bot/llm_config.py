import os

from dotenv import load_dotenv

load_dotenv()

# LLM config
llm_config = {
    "config_list": [
        {
            "model": os.environ["WATSONX_MODEL_ID"],
            "api_key": os.environ["WATSONX_API_KEY"],
            "base_url": f"{os.environ['WATSONX_URL']}/ml/v1",
            "temperature": 0.0,
            "extra_body": {"project_id": os.environ["WATSONX_PROJECT_ID"]},
        }
    ]
}
