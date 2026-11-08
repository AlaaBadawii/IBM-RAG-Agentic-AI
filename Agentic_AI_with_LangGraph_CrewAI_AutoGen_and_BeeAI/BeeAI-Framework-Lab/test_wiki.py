import asyncio
import traceback

from beeai_framework.tools.search.wikipedia import (
    WikipediaTool,
    WikipediaToolInput,
)


async def main():
    wikipedia = WikipediaTool()

    query = WikipediaToolInput(query="Quantum computing")

    try:
        result = await wikipedia.run(query)
        print("Wikipedia response:")
        print(result.get_text_content())

    except Exception:
        print("Wikipedia tool failed:")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
