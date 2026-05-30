"""YouTube URL parsing helpers shared by Miner and downstream agents."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_VIDEO_ID_PATTERNS = (
    re.compile(r"youtube\.com/watch\?.*?v=([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"youtube\.com/shorts/([A-Za-z0-9_-]{11})"),
)
_CHANNEL_ID_PATTERN = re.compile(r"youtube\.com/channel/(UC[A-Za-z0-9_-]{22})")
_HANDLE_PATTERN = re.compile(r"youtube\.com/@([A-Za-z0-9_.-]+)")


def extract_video_id(url: str | None) -> str | None:
    """Return the 11-character YouTube video id from a URL, or None."""
    if not url:
        return None

    for pattern in _VIDEO_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)

    try:
        parsed = urlparse(url)
    except Exception:
        return None
    host = parsed.netloc.lower()
    if host and not (host.endswith("youtube.com") or host == "youtu.be"):
        return None
    query = parse_qs(parsed.query)

    values = query.get("v") or []
    if values and re.fullmatch(r"[A-Za-z0-9_-]{11}", values[0]):
        return values[0]
    return None


def extract_channel_external_id(url: str | None) -> str | None:
    """Return a UC... channel id or @handle from a YouTube channel URL."""
    if not url:
        return None

    match = _CHANNEL_ID_PATTERN.search(url)
    if match:
        return match.group(1)

    match = _HANDLE_PATTERN.search(url)
    if match:
        return f"@{match.group(1)}"

    return None


def extract_youtube_id(kind: str, url: str | None) -> str | None:
    """Extract the canonical external id for a YouTube channel or video URL."""
    if kind == "video":
        return extract_video_id(url)
    if kind == "channel":
        return extract_channel_external_id(url)
    return None
