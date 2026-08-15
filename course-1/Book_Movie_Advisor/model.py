from typing import Literal

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from config import GEN_PARAMS, MODELS, OPENROUTER_API_KEY, OPENROUTER_BASE_URL


class Recommendation(BaseModel):
    """A single recommendation for a book or movie."""
    title: str = Field(description="Title of the book or movie")
    type: Literal["book", "movie"] = Field(
        description="Whether it is a book or a movie"
    )
    genre: str = Field(description="Genre, e.g. thriller, sci-fi, romance")
    why_you_ll_love_it: str = Field(
        description="One sentence explaining why this fits the mood"
    )
    mood_match: int = Field(
        description="How well this matches the mood, score from 0 to 10"
    )
    where_to_find_it: str = Field(
        description="Where to find it, e.g. Netflix, Amazon Prime, bookstore"
    )


class RecommendationList(BaseModel):
    """Wrapper so the LLM returns one JSON object with a 'recommendations' list inside."""

    recommendations: list[Recommendation] = Field(
        description="Exactly 3 recommendations"
    )


parser = JsonOutputParser(pydantic_object=RecommendationList)


_TEMPLATE = """\
You are an expert entertainment advisor who recommends books and movies.
Given a user's mood or interests, you ALWAYS return exactly 3 recommendations.
Never return fewer or more than 3.

Here is one example of the format you must use:

Mood: "I want something funny and light-hearted for a lazy afternoon"
Output:
{{
"recommendations": [
    {{
        "title": "The Hitchhiker's Guide to the Galaxy",
        "type": "book",
        "genre": "comedy sci-fi",
        "why_you_ll_love_it": "Absurd humour and a breezy pace make it perfect for a no-stress afternoon.",
        "mood_match": 9,
        "where_to_find_it": "Any bookstore or borrow from your local library"
    }}
]
}}

Now produce exactly 3 recommendations for the following mood.

{format_instructions}

Mood: {mood}
"""

prompt = PromptTemplate(
    template=_TEMPLATE,
    input_variables=["mood"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)


def build_chain(model_key: str = "llama"):
    llm = ChatOpenAI(
        model=MODELS.get(
            model_key, MODELS["llama"]
        ),
        openai_api_key=OPENROUTER_API_KEY,
        openai_api_base=OPENROUTER_BASE_URL,
        **GEN_PARAMS,
    )
    return prompt | llm | parser
