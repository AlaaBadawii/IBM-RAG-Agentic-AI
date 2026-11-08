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


async def controlled_execution_example():
    """
    RequirementAgent with controllled execution - requirements system

    requirements provide precise control over tool execution order and behavior.
    same query, same tracking - but with strict execution roles.
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

    controlled_agent = RequirementAgent(
        llm=llm,
        tools=[ThinkTool(), WikipediaTool()],
        memory=UnconstrainedMemory(),
        instructions=SYSTEM_INSTRUCTIONS,
        middlewares=[GlobalTrajectoryMiddleware(included=[Tool])],
        requirements=[
            ConditionalRequirement(
                ThinkTool, force_at_step=1, min_invocations=1, max_invocations=3, consecutive_allowed=False
            ),
            ConditionalRequirement(
                WikipediaTool, only_after=[ThinkTool], min_invocations=1, max_invocations=2
            ),
        ],
    )

    # SAME QUERY as all previous examples
    ANALYSIS_QUERY = """Analyze the cybersecurity risks of quantum computing for financial institutions. 
    What are the main threats, timeline for concern, and recommended preparation strategies?"""

    result = await controlled_agent.run(ANALYSIS_QUERY)
    print(f"\n🔧 Controlled Execution Analysis:\n{result.answer.text}")


async def main() -> None:
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)
    await controlled_execution_example()


if __name__ == "__main__":
    asyncio.run(main())
