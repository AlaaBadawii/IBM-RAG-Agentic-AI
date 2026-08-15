from langchain_core.prompts import PromptTemplate

from parser import parser

SYSTEM_PROMPT = """You are an expert communication coach. You help users write professional, effective and well-structured emails. For every request you produce a polished email together with a clear subject line and actionable improvement suggestions.

You MUST always respond with a plain JSON object and nothing else. Never include markdown code fences, commentary or extra text around the JSON."""

EMAIL_PROMPT_TEMPLATE = """{system_prompt}

Here is an example of what we expect:

Example INPUT:

Topic:
Interview apology

Example OUTPUT:

{{
  "subject": "Apology for Missing the Interview",
  "email": "Dear [Hiring Manager],\n\nI am writing to sincerely apologize for missing my interview on [date]. The meeting was unfortunately lost due to a family emergency. I remain very interested in the position and would be grateful for the chance to reschedule at your earliest convenience.\n\nBest regards,\n[Your Name]",
  "tone": "formal",
  "improvements": [
    "Provide a specific new date and time for the rescheduled interview",
    "Apologize earlier in the email to acknowledge the impact on the interviewer",
    "Add a line expressing continued enthusiasm for the role"
  ]
}}

Now write the email.

Email type: {email_type}
Tone: {tone}
Topic:
{topic}

{format_instructions}"""

EMAIL_PROMPT = PromptTemplate(
    template=EMAIL_PROMPT_TEMPLATE,
    input_variables=["system_prompt", "email_type", "tone", "topic"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)