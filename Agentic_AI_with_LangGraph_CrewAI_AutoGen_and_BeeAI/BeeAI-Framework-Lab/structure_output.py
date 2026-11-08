import asyncio
import logging

from beeai_framework.backend import (
    SystemMessage,
    UserMessage,
)
from pydantic import BaseModel, Field

from llm import get_llm


class BusinessPlan(BaseModel):
    """A comprehensive business plan structure."""

    business_name: str = Field(description="Catchy name for the business")
    elevator_pitch: str = Field(description="30-second description of the business")
    target_market: str = Field(description="Primary target audience")
    unique_value_proposition: str = Field(
        description="What makes this business special"
    )
    revenue_streams: list[str] = Field(description="Ways the business will make money")
    startup_costs: str = Field(description="Estimated initial investment needed")
    key_success_factors: list[str] = Field(description="Critical elements for success")


async def structured_output_example():
    llm = get_llm("gemini")

    messages = [
        SystemMessage(content="You're an expert business consultant and enterprenure."),
        UserMessage(
            content="Create a business plan for a mobile app that helps people find and book unique local experiences in their city."
        ),
    ]

    response = await llm.create_structure(
        schema=BusinessPlan,
        messages=messages,
    )

    print(
        "User: Create a business plan for a mobile app that helps people find and book unique local experiences in their city."
    )
    print("\n🚀 AI-Generated Business Plan:")
    print(f"\n💡 Business Name: {response.object['business_name']}")
    print(f"\n🎯 Elevator Pitch: {response.object['elevator_pitch']}")
    print(f"\n👥 Target Market: {response.object['target_market']}")
    print(f"\n⭐ Unique Value Proposition: {response.object['unique_value_proposition']}")
    print(f"\n💰 Revenue Streams: {', '.join(response.object['revenue_streams'])}")
    print(f"\n💵 Startup Costs: {response.object['startup_costs']}")
    print("\n🔑 Key Success Factors:")
    for factor in response.object["key_success_factors"]:
        print(f"  - {factor}")


async def main():
    logging.getLogger("asyncio").setLevel(
        logging.CRITICAL
    )  # Suppress unwanted warnings
    await structured_output_example()


if __name__ == "__main__":
    asyncio.run(main())
