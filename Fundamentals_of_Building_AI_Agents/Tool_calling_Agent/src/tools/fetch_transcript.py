from langchain.tools import tool
from youtube_transcript_api._api import YouTubeTranscriptApi


class TranscriptFetchError(Exception):
    """Raised when a YouTube transcript cannot be fetched."""


@tool
def fetch_transcript(video_id: str) -> str:
    """
    Fetch the transcript of a YouTube video using its video ID.

    Args:
        video_id (str): The YouTube video ID.
    Returns:
        str: The transcript of the video as a single string.
    Raises:
        Exception: If the transcript cannot be fetched.
    """
    try:
        transcript_list = YouTubeTranscriptApi().fetch(video_id)

        transcript = " ".join(entry.text for entry in transcript_list)
        return transcript
    except Exception as e:
        raise TranscriptFetchError(
            f"Could not fetch transcript for video ID {video_id}: {e}"
        ) from e


if __name__ == "__main__":
    # Example usage
    test_video_id = "UKPkqrkgKmw"
    try:
        transcript = fetch_transcript.invoke({"video_id": test_video_id})
        print(f"Fetched transcript: {transcript}")
    except TranscriptFetchError as e:
        print(f"Error: {e}")
