"""One-time backfill: ingest ALL videos from whitelisted channels.

Usage: python -m app.backfill
"""

import asyncio
import json
import logging
import subprocess
import sys

from jeromelu_shared.config import settings
from jeromelu_shared.db import SessionLocal, Source, SourceDocument
from jeromelu_shared.s3 import get_s3_client, upload_raw

from youtube_utils import fetch_transcript
from youtube_utils.exceptions import NoTranscriptAvailable, RateLimitError

from app.activities.collection import (
    _build_s3_json,
    _segments_to_plain_text,
    _compute_checksum,
)
from app.activities.discovery import load_channels
from app.activities.indexing import _parse_published_at, _checksum_exists

from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def discover_all_videos(channel_id: str) -> list[dict]:
    """Get ALL videos from a channel (no limit)."""
    channel_url = f"https://www.youtube.com/channel/{channel_id}/videos"
    logger.info("Fetching full video list for channel %s...", channel_id)

    result = subprocess.run(
        [
            "yt-dlp",
            "--print", "%(id)s\t%(title)s\t%(upload_date)s",
            "--skip-download",
            channel_url,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        logger.error("yt-dlp failed: %s", result.stderr[-300:])
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


def main():
    channels = load_channels()
    if not channels:
        logger.error("No channels configured")
        return

    # Ensure S3 bucket exists
    s3_client = get_s3_client()
    try:
        s3_client.head_bucket(Bucket=settings.s3_raw_bucket)
    except Exception:
        s3_client.create_bucket(Bucket=settings.s3_raw_bucket)

    for ch in channels:
        channel_id = ch["channel_id"]
        channel_name = ch["name"]

        # Get all videos
        all_videos = discover_all_videos(channel_id)
        logger.info("Found %d total videos on %s", len(all_videos), channel_name)

        # Filter out already ingested
        session = SessionLocal()
        all_urls = [f"https://www.youtube.com/watch?v={v['video_id']}" for v in all_videos]
        existing = set()
        if all_urls:
            results = session.query(Source.canonical_url).filter(
                Source.canonical_url.in_(all_urls)
            ).all()
            existing = {r[0] for r in results}

        new_videos = [v for v in all_videos if f"https://www.youtube.com/watch?v={v['video_id']}" not in existing]
        logger.info("Need to backfill %d videos (%d already ingested)", len(new_videos), len(all_videos) - len(new_videos))

        collected = 0
        indexed = 0
        skipped = 0
        errors = []

        for i, video in enumerate(new_videos):
            video["channel_id"] = channel_id
            video["channel_name"] = channel_name
            video["url"] = f"https://www.youtube.com/watch?v={video['video_id']}"

            video_id = video["video_id"]
            progress = f"[{i+1}/{len(new_videos)}]"

            # Collect transcript
            try:
                segments = fetch_transcript(video_id)
            except RateLimitError as e:
                logger.warning("%s Rate limited on %s — stopping backfill to avoid ban", progress, video_id)
                errors.append({"video_id": video_id, "error": str(e)})
                break  # Stop entirely on rate limit
            except NoTranscriptAvailable as e:
                logger.warning("%s No transcript for %s: %s — skipping", progress, video_id, e)
                skipped += 1
                continue
            except Exception as e:
                logger.error("%s Failed to fetch %s: %s", progress, video_id, e)
                errors.append({"video_id": video_id, "error": str(e)})
                continue

            # Upload to S3
            s3_doc = _build_s3_json(video, segments)
            s3_key = f"youtube/{channel_id}/{video_id}.json"
            s3_body = json.dumps(s3_doc, ensure_ascii=False, indent=2)
            upload_raw(s3_key, s3_body)

            plain_text = _segments_to_plain_text(segments)
            checksum = _compute_checksum(plain_text)
            collected += 1

            # Index in DB
            if _checksum_exists(session, checksum):
                logger.info("%s Duplicate content for %s — skipping DB write", progress, video_id)
                skipped += 1
                continue

            source = Source(
                source_type="youtube",
                title=video["title"],
                creator_name=channel_name,
                canonical_url=video["url"],
                approved_flag=True,
                ingestion_status="completed",
                published_at=_parse_published_at(video.get("published_at", "")),
                ingested_at=datetime.now(timezone.utc),
            )
            session.add(source)
            session.flush()

            document = SourceDocument(
                source_id=source.source_id,
                raw_text=plain_text,
                transcript_available=True,
                language="en",
                checksum=checksum,
            )
            session.add(document)
            session.commit()
            indexed += 1

            logger.info("%s Ingested: %s", progress, video["title"])

        session.close()

        logger.info(
            "\nBackfill complete for %s:\n  Total: %d\n  Already ingested: %d\n  Collected: %d\n  Indexed: %d\n  Skipped (no transcript/dupe): %d\n  Errors: %d",
            channel_name,
            len(all_videos),
            len(all_videos) - len(new_videos),
            collected,
            indexed,
            skipped,
            len(errors),
        )
        if errors:
            for e in errors:
                logger.error("  Error: %s — %s", e["video_id"], e["error"])


if __name__ == "__main__":
    main()
