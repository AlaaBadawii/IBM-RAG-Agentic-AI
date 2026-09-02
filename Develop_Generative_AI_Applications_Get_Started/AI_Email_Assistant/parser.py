
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field


class EmailResponse(BaseModel):
    subject: str = Field(..., description="The subject of the email")
    email: str = Field(..., description="The body of the email")
    tone: str = Field(..., description="The tone of the email (e.g., formal, casual, friendly)")
    improvements: list[str] = Field(..., description="Suggestions for improving the email")


parser = JsonOutputParser(pydantic_object=EmailResponse)
