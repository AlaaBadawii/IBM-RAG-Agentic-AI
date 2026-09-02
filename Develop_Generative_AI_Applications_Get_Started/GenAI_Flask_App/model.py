from config import (
    GRANITE_MODEL_ID,
    LLAMA_MODEL_ID,
    MAX_TOKENS,
    MISTRAL_MODEL_ID,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_SITE_NAME,
    OPENROUTER_SITE_URL,
    TEMPERATURE,
)
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class AIResponse(BaseModel):
    summary: str = Field(description="Summary of the user's message")
    sentiment: int = Field(description="Sentiment score from 0 (negative) to 100 (positive)")
    response: str = Field(description="Suggested response to the user")


json_parser = JsonOutputParser(pydantic_object=AIResponse)


def initialize_model(model_id: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=model_id,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        default_headers={
            "HTTP-Referer": OPENROUTER_SITE_URL,
            "X-Title": OPENROUTER_SITE_NAME,
        },
    )


llama_llm = initialize_model(LLAMA_MODEL_ID)
granite_llm = initialize_model(GRANITE_MODEL_ID)
mistral_llm = initialize_model(MISTRAL_MODEL_ID)


prompt_template = ChatPromptTemplate.from_messages(
    [
        ("system", "{system_prompt}\n\n{format_prompt}"),
        ("human", "{user_prompt}"),
    ]
)


def get_ai_response(model: ChatOpenAI, system_prompt: str, user_prompt: str) -> dict:
    chain = prompt_template | model | json_parser
    return chain.invoke(
        {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "format_prompt": json_parser.get_format_instructions(),
        }
    )


def llama_response(system_prompt: str, user_prompt: str) -> dict:
    return get_ai_response(llama_llm, system_prompt, user_prompt)


def granite_response(system_prompt: str, user_prompt: str) -> dict:
    return get_ai_response(granite_llm, system_prompt, user_prompt)


def mistral_response(system_prompt: str, user_prompt: str) -> dict:
    return get_ai_response(mistral_llm, system_prompt, user_prompt)
