from typing import TypedDict
from schemas import grades


class ReflectionState(TypedDict):
    investment_plan: str
    investor_profile: str
    target_grade: grades
    feedback: str
    grade: grades
    n: int
