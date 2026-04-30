"""Channel video enumeration + video stats refresh.

Two deterministic jobs that bolt on to Scout's discovery flow:

1. `refresh_channel_videos(session, channel)` — enumerate a channel's uploads
   playlist and insert any new videos as `sources` rows. Called automatically
   on channel approval (full backfill), and weekly via the admin refresh
   endpoint (incremental: stops at the most-recent known video_id).

2. `refresh_all_video_stats(session)` — batch-fetch view/like/comment counts
   for every YouTube source and append a row to `video_metrics`. Called
   weekly so we can see which videos are gaining traction.

Both jobs are idempotent and safe to re-run. Quota cost:
  - Per-channel enumerate: ~4 quota units for full backfill (200 videos),
    ~1 for incremental (most weeks no new videos).
  - All-video stats refresh: ~1 unit per 50 videos. ~150 channels × ~200
    videos = ~600 units for a full pass.

Not Temporal-driven — sync, in-process. Matches the rest of Scout.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from jeromelu_shared.db import Channel, Source, VideoMetric

from . import youtube_api

logger = logging.getLogger(__name__)


# Only the time-varying fields belong in the video_metrics JSONB. Identity
# fields (duration, description, thumbnail, title) are written to columns on
# `sources` so they're queryable without unpacking JSON.
_METRIC_FIELDS = ("views", "likes", "comments")


_VIDEO_ID_RE = re.compile(r"(?:v=|/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})")


def _video_id_from_url(url: str | None) -> str | None:
    """Pull the 11-char YouTube video id out of a watch URL. None if not present."""
    if not url:
        return None
    m = _VIDEO_ID_RE.search(url)
    return m.group(1) if m else None


def _most_recent_known_video_id(session: Session, channel_id: UUID) -> str | None:
    """Return the video_id of the newest already-known video for `channel_id`,
    or None if we have no videos for it yet. Used as the incremental cursor."""
    stmt = (
        select(Source.canonical_url)
        .where(Source.channel_id == channel_id)
        .where(Source.source_type == "youtube")
        .order_by(Source.published_at.desc().nullslast(), Source.created_at.desc())
        .limit(1)
    )
    row = session.execute(stmt).first()
    if not row:
        return None
    return _video_id_from_url(row[0])


def _parse_published_at(raw: str | None) -> datetime | None:
    """Parse YouTube's RFC 3339 timestamp ('2026-04-29T08:30:00Z'). None if blank."""
    if not raw:
        return None
    try:
        # Python 3.11+ handles 'Z'; older versions need the swap.
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Per-channel video enumeration
# ---------------------------------------------------------------------------

def refresh_channel_videos(
    session: Session,
    channel: Channel,
    max_results: int = 200,
    full_backfill: bool = False,
) -> dict[str, Any]:
    """Enumerate `channel`'s uploads playlist and insert any new videos.

    By default uses the most-recent already-known video_id as a cursor, so
    weekly runs only fetch what's new. Pass `full_backfill=True` to ignore
    the cursor and pull up to `max_results` videos regardless.

    For each new video inserted into `sources`, also writes a snapshot row
    into `video_metrics` (one batched stats call per 50 videos).

    Returns a small dict with counts for logging / API responses.
    """
    if channel.platform != "youtube" or not channel.external_id:
        return {"channel_id": str(channel.channel_id), "skipped": "not_youtube"}

    cursor_video_id = (
        None if full_backfill else _most_recent_known_video_id(session, channel.channel_id)
    )

    videos = youtube_api.list_channel_videos(
        channel.external_id,
        after_video_id=cursor_video_id,
        max_results=max_results,
    )
    if not videos:
        return {
            "channel_id": str(channel.channel_id),
            "videos_listed": 0,
            "videos_inserted": 0,
            "metrics_recorded": 0,
        }

    # Insert with the metadata that playlistItems already gave us at no extra
    # cost — description, thumbnail. duration_seconds requires a videos.list
    # call (handled below for newly-inserted rows only).
    inserted_source_ids: dict[str, UUID] = {}  # video_id → source_id
    for v in videos:
        published_at = _parse_published_at(v.get("published_at"))
        stmt = (
            pg_insert(Source)
            .values(
                channel_id=channel.channel_id,
                source_type="youtube",
                title=v["title"] or v["video_id"],
                description=v.get("description") or None,
                thumbnail_url=v.get("thumbnail_url"),
                creator_name=channel.name,
                canonical_url=v["url"],
                approved_flag=True,  # parent channel is already approved
                ingestion_status="pending",
                published_at=published_at,
            )
            .on_conflict_do_nothing(index_elements=["canonical_url"])
            .returning(Source.source_id)
        )
        result = session.execute(stmt).first()
        if result:
            inserted_source_ids[v["video_id"]] = result[0]

    # Snapshot stats for the videos we just inserted. Skip the call entirely
    # if we inserted nothing (incremental no-op case).
    metrics_recorded = 0
    if inserted_source_ids:
        stats = youtube_api.get_video_stats(list(inserted_source_ids.keys()))
        sampled_at = datetime.now(timezone.utc)
        for video_id, source_id in inserted_source_ids.items():
            entry = stats.get(video_id)
            if not entry:
                continue
            # Patch identity fields that videos.list returns but playlistItems
            # didn't (duration in particular).
            duration = entry.get("duration_seconds")
            if duration is not None:
                session.execute(
                    update(Source)
                    .where(Source.source_id == source_id)
                    .values(duration_seconds=duration)
                )
            metric_payload = {k: entry[k] for k in _METRIC_FIELDS if k in entry}
            if metric_payload:
                session.add(
                    VideoMetric(
                        source_id=source_id,
                        sampled_at=sampled_at,
                        source="youtube_api",
                        metrics=metric_payload,
                    )
                )
                metrics_recorded += 1

    session.commit()

    logger.info(
        "Enumerated channel %s (%s): %d listed, %d inserted, %d metrics recorded",
        channel.name,
        channel.external_id,
        len(videos),
        len(inserted_source_ids),
        metrics_recorded,
    )

    return {
        "channel_id": str(channel.channel_id),
        "videos_listed": len(videos),
        "videos_inserted": len(inserted_source_ids),
        "metrics_recorded": metrics_recorded,
    }


# ---------------------------------------------------------------------------
# All-video weekly stats refresh
# ---------------------------------------------------------------------------

def refresh_all_video_stats(session: Session) -> dict[str, Any]:
    """Snapshot views/likes/comments for every active YouTube source AND
    sync identity fields (description, thumbnail, duration, title) onto
    each `sources` row.

    Two outcomes per video, both paid for in the same `videos.list` call:
      1. A new row in `video_metrics` carrying just the time-varying fields
         (views/likes/comments). Use `video_latest_metrics` for current
         state and the table itself for history.
      2. The `sources` row is updated to mirror YouTube's current identity
         fields. These can change (creators edit descriptions to add
         chapter timestamps, thumbnails get refreshed) so always-overwrite
         keeps the DB in sync rather than letting it drift.

    Quota: ~1 unit per 50 videos. ~150 channels × ~200 videos = ~600 units.
    """
    stmt = (
        select(Source.source_id, Source.canonical_url)
        .where(Source.source_type == "youtube")
        .where(Source.canonical_url.is_not(None))
    )
    rows = session.execute(stmt).all()

    # Build a {video_id → source_id} map; skip rows whose canonical_url
    # doesn't parse (defensive, shouldn't happen for YouTube sources).
    video_to_source: dict[str, UUID] = {}
    for source_id, url in rows:
        vid = _video_id_from_url(url)
        if vid:
            video_to_source[vid] = source_id

    if not video_to_source:
        return {"videos_refreshed": 0, "sources_synced": 0, "batches": 0}

    sampled_at = datetime.now(timezone.utc)
    refreshed = 0
    sources_synced = 0
    batches = 0
    video_ids = list(video_to_source.keys())
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        stats = youtube_api.get_video_stats(batch)
        batches += 1
        for video_id, entry in stats.items():
            source_id = video_to_source.get(video_id)
            if not source_id or not entry:
                continue

            # Sync identity fields onto the source row. Only set keys we
            # actually got back — this avoids clobbering existing data with
            # NULL when the API drops a field.
            source_updates: dict[str, Any] = {}
            for src_col, api_key in (
                ("title", "title"),
                ("description", "description"),
                ("thumbnail_url", "thumbnail_url"),
                ("duration_seconds", "duration_seconds"),
            ):
                if api_key in entry:
                    source_updates[src_col] = entry[api_key]
            if source_updates:
                session.execute(
                    update(Source)
                    .where(Source.source_id == source_id)
                    .values(**source_updates)
                )
                sources_synced += 1

            metric_payload = {k: entry[k] for k in _METRIC_FIELDS if k in entry}
            if metric_payload:
                session.add(
                    VideoMetric(
                        source_id=source_id,
                        sampled_at=sampled_at,
                        source="youtube_api",
                        metrics=metric_payload,
                    )
                )
                refreshed += 1

    session.commit()
    logger.info(
        "Refreshed video stats: %d videos in %d API batches, "
        "%d sources synced with identity fields",
        refreshed,
        batches,
        sources_synced,
    )

    return {
        "videos_total": len(video_to_source),
        "videos_refreshed": refreshed,
        "sources_synced": sources_synced,
        "batches": batches,
    }


# ---------------------------------------------------------------------------
# Combined weekly job — used by the admin endpoint
# ---------------------------------------------------------------------------

def refresh_all_channels_incremental(session: Session) -> dict[str, Any]:
    """Walk every active YouTube channel and pull any new videos. Cheap:
    ~1 quota unit per channel for incremental (most weeks, no new videos
    means a single playlistItems page that hits the cursor immediately)."""
    stmt = (
        select(Channel)
        .where(Channel.platform == "youtube")
        .where(Channel.active.is_(True))
    )
    channels = list(session.scalars(stmt))

    per_channel: list[dict[str, Any]] = []
    total_inserted = 0
    for channel in channels:
        try:
            result = refresh_channel_videos(session, channel)
        except Exception as e:
            logger.warning(
                "refresh_channel_videos failed for %s: %s", channel.external_id, e
            )
            per_channel.append({
                "channel_id": str(channel.channel_id),
                "external_id": channel.external_id,
                "error": str(e),
            })
            continue
        total_inserted += result.get("videos_inserted", 0)
        per_channel.append(result)

    return {
        "channels_processed": len(channels),
        "total_videos_inserted": total_inserted,
        "per_channel": per_channel,
    }
