import asyncio
import logging
import traceback

from beeai_framework.agents.experimental import RequirementAgent
from beeai_framework.agents.experimental.requirements.conditional import (
    ConditionalRequirement,
)
from beeai_framework.memory import UnconstrainedMemory
from beeai_framework.middleware.trajectory import GlobalTrajectoryMiddleware
from beeai_framework.tools import Tool
from beeai_framework.tools.search.wikipedia import WikipediaTool

from llm import get_llm


class DebugWikipediaTool(WikipediaTool):
    """
    Diagnostic wrapper around WikipediaTool.

    Logs the input received by the tool and its successful response.
    """

    async def _run(self, input, options, run):
        print("\n========== WIKIPEDIA DEBUG ==========")
        print("Input type:", type(input))
        print("Input value:", repr(input))
        print("====================================\n")

        try:
            result = await super()._run(input, options, run)

            print("\n========== WIKIPEDIA RESULT =========")
            print(result.get_text_content())
            print("====================================\n")

            return result

        except Exception:
            print("\n========== WIKIPEDIA ERROR =========")
            traceback.print_exc()
            print("====================================\n")
            raise


async def wikipedia_enhanced_agent_example():

    llm = get_llm("watsonx")

    SYSTEM_INSTRUCTIONS = """
You are an expert cybersecurity analyst specializing in threat
assessment and risk analysis.

Your methodology:
1. Analyze the threat landscape systematically.
2. Use WikipediaTool to retrieve relevant Wikipedia articles.
3. Analyze the retrieved information.
4. Provide practical, implementable security recommendations.

IMPORTANT WIKIPEDIA TOOL RULES:

The WikipediaTool retrieves Wikipedia pages. It is NOT a general
web search engine.

When calling WikipediaTool:
- Use only a short, recognizable Wikipedia article title.
- Keep the query under 80 characters.
- Examples:
    "Quantum computing"
    "Post-quantum cryptography"
    "Cryptography"
- Never include "site:wikipedia.org".
- Never use search operators such as OR.
- Never include dates or long natural-language questions.
- Never generate multiple search queries in one tool call.

If a relevant page cannot be retrieved, do not repeatedly
generate alternative long queries.

RESEARCH INTEGRITY:
- Do not claim that information was researched if retrieval failed.
- Clearly distinguish retrieved information from your own
  general knowledge.
- Do not invent sources or citations.
"""

    wikipedia_tool = DebugWikipediaTool()

    wikipedia_agent = RequirementAgent(
        llm=llm,
        tools=[wikipedia_tool],
        memory=UnconstrainedMemory(),
        instructions=SYSTEM_INSTRUCTIONS,
        middlewares=[GlobalTrajectoryMiddleware(included=[Tool])],
        requirements=[
            ConditionalRequirement(
                WikipediaTool,
                max_invocations=2,
            )
        ],
    )

    ANALYSIS_QUERY = """
Analyze the cybersecurity risks of quantum computing for
financial institutions.

First, retrieve the Wikipedia article titled "Quantum computing".
If relevant, retrieve "Post-quantum cryptography".

Use the retrieved information to explain:
1. Main cybersecurity threats.
2. Potential timeline of concern.
3. Recommended preparation strategies.

Do not use WikipediaTool with any other query.
"""

    result = await wikipedia_agent.run(ANALYSIS_QUERY)

    print("\n========== FINAL AGENT ANSWER ==========")
    print(result.answer.text)
    print("========================================\n")


async def main():
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)

    await wikipedia_enhanced_agent_example()


if __name__ == "__main__":
    asyncio.run(main())
