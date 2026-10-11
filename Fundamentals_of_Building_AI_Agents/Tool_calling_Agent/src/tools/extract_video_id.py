"""Extract the video ID from a YouTube URL."""

import re

from langchain.tools import tool


@tool
def extract_video_id(url: str) -> str:
    """
    Extract the video ID from a YouTube URL.

    Args:
        url (str): The YouTube URL.
    Returns:
        str: The extracted video ID.
    Raises:
        ValueError: If the URL is not a valid YouTube URL or the video ID cannot
        be extracted.
    """
    # Regular expression to match YouTube video URLs
    youtube_regex = r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})"
    match = re.match(youtube_regex, url)
    if not match:
        raise ValueError("Invalid YouTube URL")
    return match.group(1)


if __name__ == "__main__":
    # Example usage
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    try:
        video_id = extract_video_id.invoke({"url": test_url})
        print(f"Extracted video ID: {video_id}")
    except ValueError as e:
        print(f"Error: {e}")
    
