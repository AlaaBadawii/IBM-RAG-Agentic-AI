"""Get full metadata for a YouTube video."""
from pprint import pprint

import yt_dlp
from langchain.tools import tool


@tool
def get_full_metadata(video_url: str) -> dict:
    """
    Get full metadata for a YouTube video.

    Args:
        video_url (str): The URL of the YouTube video.
    Returns:
        dict: A dictionary containing the full metadata of the video.
    Raises:
        Exception: If the metadata cannot be fetched.
    """
    try:
        with yt_dlp.YoutubeDL() as ydl:
            info_dict = ydl.extract_info(video_url, download=False)
            return {
                "channel": info_dict.get("uploader"),
                "title": info_dict.get("title"),
                "duration": info_dict.get("duration"),
                "views": info_dict.get("view_count"),
                "likes": info_dict.get("like_count"),
                "rating": info_dict.get("average_rating"),
                "categories": info_dict.get("categories"),
                "characters": info_dict.get("chapters"),
            }
    except Exception as e:
        raise RuntimeError(f"Failed to fetch metadata for video URL '{video_url}': {e}") from e

if __name__ == "__main__":
    # Example usage
    test_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    try:
        metadata = get_full_metadata.run({"video_url": test_video_url})
        pprint(metadata)
    except RuntimeError as e:
        print(f"Error: {e}")
