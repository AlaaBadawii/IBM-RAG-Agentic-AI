def warn(*args, **kwargs):
    pass


import warnings

warnings.warn = warn
warnings.filterwarnings("ignore")

import matplotlib as plt
import pandas as pd
from ibm_watson_machine_learning.foundation_models.extensions.langchain import (
    WatsonxLLM,
)
from ibm_watsonx_ai.foundation_models import Model
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent

df = pd.read_csv(
    "https://cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud/ZNoKMJ9rssJn-QbJ49kOzA/student-mat.csv"
)

credentials = {
    "url": "<WATSONX_AI_URL>",
    "apikey": "<WATSONX_AI_APIKEY>",
}

model_id = "<WATSONX_AI_MODEL_ID>"

params = {
    GenParams.TEMPERATURE: 0.5,
    GenParams.MAX_NEW_TOKENS: 256,
}

project_id = "<WATSONX_AI_PROJECT_ID>"
space_id = None
verify = False

model = Model(
    model_id=model_id,
    credentials=credentials,
    project_id=project_id,
    params=params,
    space_id=space_id,  # pyright: ignore[reportArgumentType]
    verify=verify,
)


llm = WatsonxLLM(model=model)

agent = create_pandas_dataframe_agent(
    llm=llm,
    df=df,
    verbose=True,
    handle_parsing_errors=True,
    return_intermediate_steps=True,
    prefix="You are a pandas agent. Always respond using Action/Action Input/Final Answer format. Never output raw data directly.",
)


response = agent.invoke({"input": "Generate a bar chart to plot the gender count."})
print(response["intermediate_steps"][-1][0].tool_input.replace("; ", "\n"))
