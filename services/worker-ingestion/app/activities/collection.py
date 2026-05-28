"""Collection activity — fetch transcript via youtube-transcript-api, store JSON in S3."""

import hashlib
import json
import logging
from dataclasses import dataclass

from jeromelu_shared.config import settings
from jeromelu_shared.s3 import download_raw, upload_raw
from temporalio import activity
from youtube_utils import fetch_transcript
from youtube_utils.exceptions import NoTranscriptAvailable, RateLimitError

logger = logging.getLogger(__name__)


@dataclass
class CollectionResult:
    video_id: str
    s3_key: str
    checksum: str
    plain_text: str
    success: bool
    error: str | None = None


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
    s3_key = f"youtube/{video['channel_id']}/{video_id}.json"

    # Skip if transcript already exists in S3
    try:
        existing = download_raw(s3_key)
        doc = json.loads(existing)
        segments = doc.get("segments", [])
        plain_text = _segments_to_plain_text(segments)
        checksum = _compute_checksum(plain_text)
        logger.info("S3 hit for %s — skipping download", video_id)
        return {
            "video_id": video_id,
            "s3_key": s3_key,
            "checksum": checksum,
            "plain_text": plain_text,
            "success": True,
            "error": None,
        }
    except Exception:
        pass  # Not in S3 — proceed with collection

    logger.info("Collecting transcript for video %s: %s", video_id, video.get("title", ""))

    try:
        proxy = None
        if settings.webshare_proxy_username:
            proxy = {
                "username": settings.webshare_proxy_username,
                "password": settings.webshare_proxy_password,
            }
        segments = fetch_transcript(video_id, proxy=proxy)
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
    except NoTranscriptAvailable as e:
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
