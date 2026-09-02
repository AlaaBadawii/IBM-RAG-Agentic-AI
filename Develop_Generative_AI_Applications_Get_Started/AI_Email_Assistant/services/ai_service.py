from config import MODELS
from model import create_llm
from parser import parser
from prompts import EMAIL_PROMPT, SYSTEM_PROMPT


def build_chain(model_name: str):
    """
    Build a chain for generating email responses using the specified prompt and model.

    Returns:
        A chain that can be used to generate email responses.
    """
    model = MODELS[model_name]
    llm = create_llm(model_name=model)

    return EMAIL_PROMPT | llm | parser


def generate_email(model_name: str, email_type: str, tone: str, topic: str):
    """
    Generate an email response based on the provided parameters.

    Args:
        model_name (str): The name of the model to use for generating the response.
        email_type (str): The type of email to generate (e.g., "apology", "follow-up").
        tone (str): The desired tone of the email (e.g., "formal", "casual").
        topic (str): The topic or subject matter of the email.

    Returns:
        The parsed email response object.
    """
    chain = build_chain(model_name=model_name)
    return chain.invoke(
        {
            "system_prompt": SYSTEM_PROMPT,
            "email_type": email_type,
            "tone": tone,
            "topic": topic,
        }
    )