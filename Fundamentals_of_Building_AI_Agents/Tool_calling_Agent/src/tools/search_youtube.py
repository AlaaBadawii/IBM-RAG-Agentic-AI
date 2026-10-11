"""Search for YouTube videos based on a query."""
import logging
from pprint import pprint

from langchain.tools import tool
from pytube import Search

logging.getLogger("pytube.contrib.search").setLevel(logging.ERROR)


@tool
def search_youtube(query: str) -> list[dict[str, str]]:
    """
    Search for YouTube videos based on a query.

    Args:
        query (str): The search query.
    Returns:
        list[dict[str, str]]: A list of dictionaries containing video titles and URLs.
    Raises:
        Exception: If the search fails.
    """
    try:
        search = Search(query)
        return [
            {"title": video.title, "url": video.watch_url, "id": video.video_id}
            for video in (search.results or [])
        ]
    except Exception as e:
        raise RuntimeError(f"Failed to search YouTube for query '{query}': {e}") from e


if __name__ == "__main__":
    # Example usage
    test_query = "LangChain VS LangGraph"
    try:
        results: list[dict[str, str]] = search_youtube.run({"query": test_query})
        pprint(results)
    except RuntimeError as e:
        print(f"Error: {e}")
