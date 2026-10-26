from typing import Literal

from pydantic import BaseModel, Field

grades = Literal[
    "ultra-conservative", "conservative", "moderate", "aggressive", "high risk", "MISSING"
]


# evaluator output schema
class Feedback(BaseModel):
    grade: grades = Field(
        description="Classify the investment based on risk level, ranging from ultra-conservative to high risk."
    )
    feedback: str = Field(
        description="Provide reasoning for the risk classification assigned to the investment suggestion."
    )
