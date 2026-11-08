"""
This example demonstrates how to use a simple prompt template with the BeeAI framework.
The SimplePromptTemplate class allows you to define a prompt template with placeholders for variables.
You can then render the template with specific values for those variables, and use the rendered prompt to interact with a chat model.
"""
import asyncio
import logging
from typing import cast

from beeai_framework.backend import ChatModel, ChatModelParameters, UserMessage


class SimplePromptTemplate:
    """Simple template using Python string formating"""

    def __init__(self, template: str):
        self.template = template

    def render(self, variables: dict) -> str:
        formatted_template = self.template

        for key in variables:
            formatted_template = formatted_template.replace(
                f"{{{{{key}}}}}", f"{{{key}}}"
            )

        return formatted_template.format(**variables)


async def prompt_template_example():
    llm = ChatModel.from_name(
        "watsonx:ibm/granite-4-h-small", ChatModelParameters(temperature=0)
    )

    template_content = """
    You're a seniior Data Scientist evaluating a machine learning project propsal.

    Project Details:
    - Project Name: {{project_name}}
    - Business Problem: {{business_problem}}
    - Avilable Data: {{data_description}}
    - Timeline: {{timeline}}
    - Success Metrics: {{success_metrics}}

    Please provide:
    1. Feasiblility assessment (1-10 scale)
    2. Key teachnical challenges
    3. Recommended approach
    4. Risk mitigation strategies
    5. Expected outcome

    Be specific and actionable in your recommendation.
    """

    prompt_template = SimplePromptTemplate(template_content)

    project_senarios = [
        {
            "project_name": "Smart Inventory Optimization",
            "business_problem": "Reduce inventory costs while maintaining 95% product availability",
            "data_description": "2 years of sales data, supplier lead times, seasonal patterns, 500K records",
            "timeline": "3 months development, 1 month testing",
            "success_metrics": "15% cost reduction, maintain 95% availability, <2% forecast error",
        },
        {
            "project_name": "Fraud Detection System",
            "business_problem": "Detect fraudulent transactions in real-time with minimal false positives",
            "data_description": "1M transaction records, user behavior data, device fingerprints",
            "timeline": "6 months development, 2 months validation",
            "success_metrics": "95% fraud detection rate, <1% false positive rate, <100ms response time",
        },
    ]

    for i, scenario in enumerate(project_senarios, 1):
        print(f"\n==== Project Evaluation {i}: {scenario['project_name']}====")

        render_prompt = prompt_template.render(scenario)
        print("\n  Rendered prompt:")
        print(render_prompt)

        messages = [UserMessage(content=render_prompt)]
        response = await llm.create(messages=cast(list, messages))

        print("### LLM Response ###\n")
        print(response.get_text_content())


async def main():
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)
    await prompt_template_example()


if __name__ == "__main__":
    asyncio.run(main())
