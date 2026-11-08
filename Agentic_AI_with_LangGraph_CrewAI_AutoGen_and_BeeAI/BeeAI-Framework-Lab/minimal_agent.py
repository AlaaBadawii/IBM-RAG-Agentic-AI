import asyncio
import logging

from beeai_framework.agents.experimental import RequirementAgent
from beeai_framework.memory import UnconstrainedMemory

from llm import get_llm


async def minimal_tracked_agent_example():
    """Minimal RequirementAgent example."""

    # Initialize the LLM
    llm = get_llm("gemini")

    system_instructions = """
    You're an expert cybersecurity analyst specializing in threat
    assessment and risk analysis.

    Your methodology:
    1. Analyze the threat landscape systematically.
    2. Research authoritative sources when available.
    3. Provide comprehensive risk assessments with actionable recommendations.
    4. Focus on practical, implementable security measures.
    """

    # Initialize the agent
    minimal_agent = RequirementAgent(
        llm=llm,
        tools=[],
        memory=UnconstrainedMemory(),  # Instantiate the memory class
        instructions=system_instructions,
    )

    analysis_query = """
    Analyze the cybersecurity risks of quantum computing for financial
    institutions.

    What are the main threats, timeline for concern, and recommended
    preparation strategies?
    """

    # Run the agent
    result = await minimal_agent.run(analysis_query)

    # Display the result
    print("\n💬 Pure LLM Analysis:\n")
    print(result.answer.text)


async def main():
    logging.basicConfig(level=logging.INFO)
    await minimal_tracked_agent_example()


if __name__ == "__main__":
    asyncio.run(main())
