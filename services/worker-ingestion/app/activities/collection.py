"""Collection activity — fetch transcript via youtube-transcript-api, store JSON in S3."""

import hashlib
import json
import logging
from dataclasses import dataclass

from temporalio import activity
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)
from youtube_transcript_api.proxies import WebshareProxyConfig

from jeromelu_shared.config import settings
from jeromelu_shared.s3 import upload_raw

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when we detect YouTube rate limiting."""


@dataclass
class CollectionResult:
    video_id: str
    s3_key: str
    checksum: str
    plain_text: str
    success: bool
    error: str | None = None


def _fetch_transcript(video_id: str) -> list[dict]:
    """Fetch transcript segments from YouTube.

    Raises RateLimitError for rate limits (skip immediately, don't retry).
    Other errors are raised as-is for Temporal retry.
    """
    try:
        proxy_config = None
        if settings.webshare_proxy_username:
            proxy_config = WebshareProxyConfig(
                proxy_username=settings.webshare_proxy_username,
                proxy_password=settings.webshare_proxy_password,
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
        raise  # Permanent failure — Temporal will not retry ApplicationError
    except Exception as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "rate" in error_msg or "too many" in error_msg:
            raise RateLimitError(f"Rate limited fetching transcript for {video_id}") from e
        raise


def _build_s3_json(video: dict, segments: list[dict]) -> dict:
    """Build the canonical JSON document for S3 storage."""
    return {
        "video_id": video["video_id"],
        "channel_id": video["channel_id"],
        "title": video["title"],
        "published_at": video["published_at"],
        "segments": segments,
    }


def _segments_to_plain_text(segments: list[dict]) -> str:
    """Extract plain text from transcript segments."""
    return " ".join(seg["text"] for seg in segments if seg.get("text"))


def _compute_checksum(text: str) -> str:
    """Compute SHA-256 checksum of the plain text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@activity.defn
async def collect_transcript(video: dict) -> dict:
    """Fetch transcript for a video, store JSON in S3, return result.

    Returns a dict with: video_id, s3_key, checksum, plain_text, success, error
    """
    video_id = video["video_id"]
    logger.info("Collecting transcript for video %s: %s", video_id, video.get("title", ""))

    try:
        segments = _fetch_transcript(video_id)
    except RateLimitError as e:
        logger.warning("Rate limited — skipping video %s: %s", video_id, e)
        return {
            "video_id": video_id,
            "s3_key": "",
            "checksum": "",
            "plain_text": "",
            "success": False,
            "error": f"rate_limit: {e}",
        }
    except (NoTranscriptFound, TranscriptsDisabled) as e:
        logger.warning("No transcript available for video %s: %s", video_id, e)
        return {
            "video_id": video_id,
            "s3_key": "",
            "checksum": "",
            "plain_text": "",
            "success": False,
            "error": f"no_transcript: {e}",
        }

    # Build JSON and upload to S3
    s3_doc = _build_s3_json(video, segments)
    s3_key = f"youtube/{video['channel_id']}/{video_id}.json"

    s3_body = json.dumps(s3_doc, ensure_ascii=False, indent=2)
    upload_raw(s3_key, s3_body)
    logger.info("Uploaded transcript to S3: %s", s3_key)

    # Derive plain text and checksum
    plain_text = _segments_to_plain_text(segments)
    checksum = _compute_checksum(plain_text)

    return {
        "video_id": video_id,
        "s3_key": s3_key,
        "checksum": checksum,
        "plain_text": plain_text,
        "success": True,
        "error": None,
    }
