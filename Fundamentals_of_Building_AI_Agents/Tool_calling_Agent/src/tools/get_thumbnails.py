"""Get thumbnails for a YouTube video."""

import yt_dlp
from langchain.tools import tool


@tool
def get_thumbnails(video_url: str) -> list[dict]:
    """
    Get thumbnails for a YouTube video.

    Args:
        video_url (str): The URL of the YouTube video.
    Returns:
        list[dict]: A list of dictionaries containing thumbnail URLs and their resolutions.
    Raises:
        Exception: If the thumbnails cannot be fetched.
    """
    try:
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            info_dict = ydl.extract_info(video_url, download=False)
            thumbnails = info_dict.get("thumbnails") or []
            return [
                {"url": thumb.get("url"), "resolution": thumb.get("resolution")}
                for thumb in thumbnails
            ]
    except Exception as e:
        raise RuntimeError(
            f"Failed to fetch thumbnails for video URL '{video_url}': {e}"
        ) from e


if __name__ == "__main__":
    # Example usage
    test_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    try:
        thumbnails = get_thumbnails.run({"video_url": test_video_url})
        print(f"Fetched thumbnails: {thumbnails}")
    except RuntimeError as e:
        print(f"Error: {e}")
