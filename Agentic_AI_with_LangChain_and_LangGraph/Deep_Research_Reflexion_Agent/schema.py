from pydantic import BaseModel, Field


class Reflection(BaseModel):
    """Schema for a reflection"""

    missing: str = Field(description="What information is missing?")
    superfluous: str = Field(description="What information is unnecessary?")


class AnswerQuestion(BaseModel):
    """Schema for an answer to a question"""

    answer: str = Field(description="Main response to the question")
    reflection: Reflection = Field(description="Self-critique of the answer")
    search_queries: list[str] = Field(description="Queries for additional research")


class ReviseAnswer(AnswerQuestion):
    """Revise your original answer to your question."""
    references: list[str] = Field(description="Citations motivating your updated answer.")