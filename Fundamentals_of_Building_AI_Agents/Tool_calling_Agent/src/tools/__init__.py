from .extract_video_id import extract_video_id
from .fetch_transcript import fetch_transcript
from .get_full_metadata import get_full_metadata
from .get_thumbnails import get_thumbnails
from .search_youtube import search_youtube

tools = {
    "extract_video_id": extract_video_id,
    "fetch_transcript": fetch_transcript,
    "get_full_metadata": get_full_metadata,
    "get_thumbnails": get_thumbnails,
    "search_youtube": search_youtube
}