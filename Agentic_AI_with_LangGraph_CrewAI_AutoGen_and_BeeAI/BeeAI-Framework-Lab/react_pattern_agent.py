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


async def react_pattern_agent():
    llm = get_llm("watsonx")

    # SAME SYSTEM PROMPT as previous examples
    SYSTEM_INSTRUCTIONS = """
    You are an expert cybersecurity analyst specializing in threat assessment and risk analysis.

    Your methodology:
    1. Analyze the threat landscape systematically
    2. Research authoritative sources when available
    3. Provide comprehensive risk assessment with actionable recommendations
    4. Focus on practical, implementable security measures
    """

    react_agent = RequirementAgent(
        llm=llm,
        tools=[ThinkTool(), WikipediaTool()],
        memory=UnconstrainedMemory(),
        instructions=SYSTEM_INSTRUCTIONS,
        middlewares=[GlobalTrajectoryMiddleware(included=[Tool])],
        requirements=[
            ConditionalRequirement(
                ThinkTool,
                force_at_step=1,
                force_after=Tool,
                min_invocations=1,
                max_invocations=5,
                consecutive_allowed=False
            )
        ]
    )

    # SAME QUERY as previous examples
    ANALYSIS_QUERY = """Analyze the cybersecurity risks of quantum computing for financial institutions. 
    What are the main threats, timeline for concern, and recommended preparation strategies?"""

    result = await react_agent.run(ANALYSIS_QUERY)
    print(f"\n🧠 Reasoning + Research Analysis:\n{result.answer.text}")


async def main() -> None:
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)
    await react_pattern_agent()


if __name__ == "__main__":
    asyncio.run(main())
