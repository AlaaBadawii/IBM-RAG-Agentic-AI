from langchain_openai import ChatOpenAI

from config import MAX_TOKENS, OPENROUTER_API_KEY, OPENROUTER_BASE_URL, TEMPERATURE


def create_llm(model_name: str) -> ChatOpenAI:
    """
    Create a ChatOpenAI instance with the specified model name, temperature, and max tokens.

    Args:
        model_name (str): The name of the model to use.
        temperature (float): The temperature for the model's responses.
        max_tokens (int): The maximum number of tokens for the model's responses.

    Returns:
        ChatOpenAI: An instance of ChatOpenAI configured with the specified parameters.
    """
    return ChatOpenAI(
        model=model_name,
        api_key=OPENROUTER_API_KEY, # type: ignore
        base_url=OPENROUTER_BASE_URL,
        temperature=TEMPERATURE,
        max_completion_tokens=MAX_TOKENS,
    )
