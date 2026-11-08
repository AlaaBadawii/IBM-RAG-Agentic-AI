import asyncio
import logging

from multi_agent.agents import travel_coordinator


async def multi_agent_travel_planner_with_language():
    """
    Advanced Multi-Agent Travel Planning System with Language Expert

    This system demonstrates:
    1. Specialized agent rols and coordination
    2. Tool-based inter-agent communication
    3. Requirements-based execution control
    4. Language and cultural expertise integration
    5. comprehensive travel planning workflow
    """

    query = """
    I'm planning a 2-week cultural immersion trip to Japan (Tokyo and Osaka) as a first-time visitor. 
    I want to experience traditional culture, visit historical sites, and interact with locals. 
    I speak only English and want to be respectful of Japanese customs. 
    What should I know about the destination, weather expectations, and language/cultural tips?
    """

    result = await travel_coordinator.run(query)
    print(f"\n\n=======📋 Comprehensive Travel Plan======\n{result.answer.text}")


async def main():
    logging.getLogger('asyncio').setLevel(logging.CRITICAL)
    await multi_agent_travel_planner_with_language()

if __name__ == "__main__":
    asyncio.run(main())
