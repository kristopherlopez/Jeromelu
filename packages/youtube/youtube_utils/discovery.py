"""Discover videos on a YouTube channel."""

import logging
import subprocess

import feedparser

logger = logging.getLogger(__name__)


def _discover_via_rss(channel_id: str) -> list[dict] | None:
    """Try RSS feed first (free, fast, no API key needed).

    Returns None if RSS is unavailable so caller can fall back.
    """
    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    feed = feedparser.parse(feed_url)

    if feed.get("status") == 404 or not feed.entries:
        return None

    videos = []
    for entry in feed.entries:
        video_id = entry.get("yt_videoid", "")
        if not video_id:
            continue
        videos.append({
            "video_id": video_id,
            "title": entry.get("title", ""),
            "published_at": entry.get("published", ""),
        })

    return videos


def _discover_via_ytdlp(channel_id: str, max_results: int) -> list[dict]:
    """Fallback: use yt-dlp to list recent videos from a channel."""
    channel_url = f"https://www.youtube.com/channel/{channel_id}/videos"
    result = subprocess.run(
        [
            "yt-dlp",
            "--print", "%(id)s\t%(title)s\t%(upload_date)s",
            "--playlist-items", f"1:{max_results}",
            "--skip-download",
            channel_url,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        logger.error("yt-dlp failed for channel %s: %s", channel_id, result.stderr[-300:])
        return []

    videos = []
    for line in result.stdout.strip().split("\n"):
        if not line or "\t" not in line:
            continue
        parts = line.split("\t", 2)
        if len(parts) < 3:
            continue
        video_id, title, upload_date = parts

        published_at = ""
        if upload_date and upload_date != "NA" and len(upload_date) == 8:
            published_at = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}T00:00:00Z"

        videos.append({
            "video_id": video_id,
            "title": title,
            "published_at": published_at,
        })

    return videos


def list_channel_videos(channel_id: str, max_results: int = 15) -> list[dict]:
    """List recent videos from a YouTube channel.

    Tries RSS first (fast, free), falls back to yt-dlp.

    Args:
        channel_id: YouTube channel ID.
        max_results: Maximum number of videos to return.

    Returns:
        List of dicts with keys: video_id, title, published_at.
    """
    videos = _discover_via_rss(channel_id)
    if videos is not None:
        logger.info("RSS: found %d videos on channel %s", len(videos), channel_id)
        return videos[:max_results]

    logger.info("RSS unavailable for %s — falling back to yt-dlp", channel_id)
    videos = _discover_via_ytdlp(channel_id, max_results)
    logger.info("yt-dlp: found %d videos on channel %s", len(videos), channel_id)
    return videos
