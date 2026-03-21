"""Search for YouTube channels by topic via yt-dlp."""

import logging

import yt_dlp

from .exceptions import SearchError

logger = logging.getLogger(__name__)


def search_channels(
    query: str,
    max_results: int = 10,
) -> list[dict]:
    """Search YouTube for channels matching a topic.

    Searches for videos matching the query, then extracts unique channels
    from the results.

    Args:
        query: Search term (e.g. "NRL supercoach").
        max_results: Maximum channels to return.

    Returns:
        List of dicts with keys: channel_id, title, channel_url.

    Raises:
        SearchError: Search failed.
    """
    # Search more videos than channels needed, since multiple videos
    # may come from the same channel
    search_count = max_results * 5

    opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            results = ydl.extract_info(
                f"ytsearch{search_count}:{query}", download=False
            )
    except Exception as e:
        raise SearchError(f"Failed to search YouTube: {e}") from e

    seen: set[str] = set()
    channels: list[dict] = []

    for entry in results.get("entries", []):
        if not entry:
            continue
        channel_id = entry.get("channel_id") or entry.get("uploader_id")
        if not channel_id or channel_id in seen:
            continue
        seen.add(channel_id)
        channels.append({
            "channel_id": channel_id,
            "title": entry.get("channel") or entry.get("uploader") or "",
            "channel_url": entry.get("channel_url") or f"https://www.youtube.com/channel/{channel_id}",
        })
        if len(channels) >= max_results:
            break

    logger.info("Found %d channels for query '%s'", len(channels), query)
    return channels
