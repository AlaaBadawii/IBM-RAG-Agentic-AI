import asyncio
import logging

from beeai_framework.agents.experimental import RequirementAgent
from beeai_framework.agents.experimental.requirements.conditional import (
    ConditionalRequirement,
)
from beeai_framework.memory import UnconstrainedMemory
from beeai_framework.middleware.trajectory import GlobalTrajectoryMiddleware
from beeai_framework.tools import Tool
from beeai_framework.tools.search.wikipedia import WikipediaTool
from beeai_framework.tools.think import ThinkTool

from llm import get_llm


async def reasoning_enhanced_agent_example():
    """
    RequirementAgent with Systematic Reasoning - ThinkTool + wikipediaTool

    Adding ThinkTool enables structured reasoning alongside research.
    Same query, same tracking - now with visible thinking process.
    """
    llm = get_llm("watsonx")

    SYSTEM_INSTRUCTIONS = """
    You are an expert cybersecurity analyst specializing in threat assessment and risk analysis.

    Your methodology:
    1. Analyze the threat landscape systematically
    2. Research authoritative sources when available
    3. Provide comprehensive risk assessment with actionable recommendations
    4. Focus on practical, implementable security measures
    """

    reasoning_agent = RequirementAgent(
        llm=llm,
        tools=[ThinkTool(), WikipediaTool()],
        memory=UnconstrainedMemory(),
        instructions=SYSTEM_INSTRUCTIONS,
        middlewares=[GlobalTrajectoryMiddleware(included=[Tool])],
        requirements=[
            ConditionalRequirement(ThinkTool, max_invocations=2),
            ConditionalRequirement(WikipediaTool, max_invocations=2),
        ],
    )

    ANALYSIS_QUERY = """
    Analyze the cybersecurity risks of quantum computing for financial institutions.
    What are the main threads, timeline for concern, and recommended preparation stratigies?
    """
    result = await reasoning_agent.run(ANALYSIS_QUERY)
    print(f"\n🧠 Reasoning + Research Analysis:\n{result.answer.text}")


async def main() -> None:
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)
    await reasoning_enhanced_agent_example()


if __name__ == "__main__":
    asyncio.run(main())
