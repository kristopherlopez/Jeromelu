"""Fetch YouTube video transcripts."""

import logging

from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)
from youtube_transcript_api.proxies import WebshareProxyConfig

from .exceptions import NoTranscriptAvailable, RateLimitError

logger = logging.getLogger(__name__)


def fetch_transcript(
    video_id: str,
    proxy: dict | None = None,
) -> list[dict]:
    """Fetch transcript segments for a YouTube video.

    Args:
        video_id: YouTube video ID (e.g. "dQw4w9WgXcQ").
        proxy: Optional Webshare proxy credentials dict with keys
               "username" and "password".

    Returns:
        List of segment dicts with keys: start, end, text, speaker.

    Raises:
        NoTranscriptAvailable: Video has no transcript.
        RateLimitError: YouTube rate-limited the request.
    """
    try:
        proxy_config = None
        if proxy:
            proxy_config = WebshareProxyConfig(
                proxy_username=proxy["username"],
                proxy_password=proxy["password"],
            )
        ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config)
        transcript = ytt_api.fetch(video_id)
        return [
            {
                "start": snippet.start,
                "end": snippet.start + snippet.duration,
                "text": snippet.text,
                "speaker": None,
            }
            for snippet in transcript
        ]
    except (NoTranscriptFound, TranscriptsDisabled) as e:
        raise NoTranscriptAvailable(str(e)) from e
    except Exception as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "rate" in error_msg or "too many" in error_msg:
            raise RateLimitError(f"Rate limited fetching transcript for {video_id}") from e
        raise
