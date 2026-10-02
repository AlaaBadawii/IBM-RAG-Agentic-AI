import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv()

llm = ChatOpenAI(
    model="deepseek/deepseek-v4-flash",
    api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
    base_url=os.getenv("BASE_URL"),
)

from langchain_core.messages import SystemMessage

response = llm.invoke(
    [
        SystemMessage(
            content="You are a friendly and natural AI assistant. "
            "Respond conversationally without unnecessarily emphasizing "
            "that you are an AI unless it is relevant."
        ),
        ("human", "Hello, how are you?"),
    ]
)

print(response.content)
