"""Discovery activity — find new videos on whitelisted YouTube channels."""

import logging
import subprocess
from datetime import datetime, timezone

import feedparser
from temporalio import activity

from jeromelu_shared.db import Channel, SessionLocal, Source

logger = logging.getLogger(__name__)

# Max recent videos to check per channel per sweep
MAX_VIDEOS_PER_CHANNEL = 15


def _load_youtube_channels(session) -> list[Channel]:
    """Load active YouTube channels with an external_id from the DB."""
    return session.query(Channel).filter(
        Channel.platform == "youtube",
        Channel.active == True,  # noqa: E712
        Channel.external_id.isnot(None),
    ).all()


def _discover_via_rss(channel_id: str) -> list[dict] | None:
    """Try RSS feed first (free, fast, no dependencies).

    Returns None if RSS is unavailable (404), so caller can fall back.
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


def _discover_via_ytdlp(channel_id: str) -> list[dict]:
    """Fallback: use yt-dlp to list recent videos from a channel."""
    channel_url = f"https://www.youtube.com/channel/{channel_id}/videos"
    # Use tab as delimiter since video titles can contain pipes
    result = subprocess.run(
        [
            "yt-dlp",
            "--print", "%(id)s\t%(title)s\t%(upload_date)s",
            "--playlist-items", f"1:{MAX_VIDEOS_PER_CHANNEL}",
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

        # Convert YYYYMMDD to ISO format
        published_at = ""
        if upload_date and upload_date != "NA" and len(upload_date) == 8:
            published_at = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}T00:00:00Z"

        videos.append({
            "video_id": video_id,
            "title": title,
            "published_at": published_at,
        })

    return videos


def _get_existing_video_urls(session, urls: list[str]) -> set[str]:
    """Check which video URLs already exist in the DB."""
    if not urls:
        return set()
    results = session.query(Source.canonical_url).filter(
        Source.canonical_url.in_(urls)
    ).all()
    return {r[0] for r in results}


@activity.defn
async def discover_new_videos() -> list[dict]:
    """Poll all whitelisted channels for new videos not yet in DB."""
    session = SessionLocal()
    try:
        channels = _load_youtube_channels(session)
        if not channels:
            logger.info("No active YouTube channels in DB — skipping discovery")
            return []

        all_videos: list[dict] = []

        for ch in channels:
            channel_id = ch.external_id
            channel_name = ch.name

            try:
                # Try RSS first (fast, free)
                videos = _discover_via_rss(channel_id)
                if videos is not None:
                    logger.info("RSS: found %d videos on %s", len(videos), channel_name)
                else:
                    # Fallback to yt-dlp
                    logger.info("RSS unavailable for %s — falling back to yt-dlp", channel_name)
                    videos = _discover_via_ytdlp(channel_id)
                    logger.info("yt-dlp: found %d videos on %s", len(videos), channel_name)

                # Attach channel metadata to each video
                for v in videos:
                    v["channel_id"] = channel_id
                    v["channel_name"] = channel_name
                    v["url"] = f"https://www.youtube.com/watch?v={v['video_id']}"

                all_videos.extend(videos)

                # Update last_polled_at
                ch.last_polled_at = datetime.now(timezone.utc)

            except Exception:
                logger.exception("Failed to discover videos for channel %s", channel_name)

        if not all_videos:
            session.commit()
            return []

        # Filter out videos already in DB (watermark via canonical_url)
        all_urls = [v["url"] for v in all_videos]
        existing_urls = _get_existing_video_urls(session, all_urls)

        new_videos = [v for v in all_videos if v["url"] not in existing_urls]

        # Only ingest content published from 2026-01-01 onwards
        cutoff = datetime(2026, 1, 1, tzinfo=timezone.utc)
        filtered = []
        for v in new_videos:
            pub = v.get("published_at", "")
            if not pub:
                filtered.append(v)  # Keep videos without a date (rare edge case)
                continue
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                if dt >= cutoff:
                    filtered.append(v)
            except ValueError:
                filtered.append(v)  # Keep if date can't be parsed
        skipped = len(new_videos) - len(filtered)
        if skipped:
            logger.info("Filtered out %d videos published before 2026-01-01", skipped)
        new_videos = filtered
        logger.info(
            "Discovered %d new videos (%d already ingested)",
            len(new_videos), len(all_videos) - len(new_videos),
        )

        session.commit()
    finally:
        session.close()

    return new_videos
