"""Channel video enumeration + video stats refresh.

Two deterministic jobs that bolt on to Scout's discovery flow:

1. `refresh_channel_videos(session, channel)` — enumerate a channel's uploads
   playlist and insert any new videos as `sources` rows. Called automatically
   on channel approval (full backfill), and daily via the admin refresh
   endpoint (incremental: stops at the most-recent known video_id).

2. `refresh_all_video_stats(session)` — batch-fetch view/like/comment counts
   for every YouTube source and append a row to `video_metrics` only when the
   payload changed vs the latest snapshot (change-only storage — see
   `_metrics_changed`). Called daily so we can see view velocity / detect
   breakouts at 1-day resolution. `refresh_all_channel_stats` does the same
   for `channel_metrics`.

Both jobs are idempotent and safe to re-run. Quota cost:
  - Per-channel enumerate: ~4 quota units for full backfill (200 videos),
    ~1 for incremental (most days no new videos).
  - All-video stats refresh: ~1 unit per 50 videos. ~180 channels × ~200
    videos = ~720 units for a full pass.

Not Temporal-driven — sync, in-process. Matches the rest of Scout.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from jeromelu_shared.db import (
    Channel,
    ChannelMetric,
    Claim,
    Source,
    SourceChunk,
    SourceDocument,
    VideoMetric,
)
from jeromelu_shared.youtube import extract_video_id
from sqlalchemy import Integer, distinct, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..common.pipeline_run import start_deterministic_run
from . import client as youtube_api

logger = logging.getLogger(__name__)


# Only the time-varying fields belong in the video_metrics JSONB. Identity
# fields (duration, description, thumbnail, title) are written to columns on
# `sources` so they're queryable without unpacking JSON.
_METRIC_FIELDS = ("views", "likes", "comments")


_video_id_from_url = extract_video_id


PIPELINE_YOUTUBE_REFRESH_VIDEOS = "youtube-refresh-videos"
PIPELINE_YOUTUBE_CHANNEL_VIDEOS = "youtube-channel-videos"
PIPELINE_YOUTUBE_CHANNEL_STATS = "youtube-channel-stats"


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


def _source_ids_missing_initial_video_metrics(
    session: Session,
    channel_id: UUID,
    video_ids: list[str],
) -> dict[str, UUID]:
    """Return listed video_id -> source_id for rows still missing their first metric.

    Full-backfill retries need this because an older failed approval-time run
    may have committed `sources` rows before `video_metrics` were written.
    """
    wanted = set(video_ids)
    if not wanted:
        return {}

    rows = session.execute(
        select(Source.source_id, Source.canonical_url)
        .where(Source.channel_id == channel_id)
        .where(Source.source_type == "youtube")
        .where(Source.canonical_url.is_not(None))
    ).all()

    source_ids_by_video_id: dict[str, UUID] = {}
    for source_id, canonical_url in rows:
        video_id = _video_id_from_url(canonical_url)
        if video_id in wanted:
            source_ids_by_video_id[video_id] = source_id

    if not source_ids_by_video_id:
        return {}

    source_ids = list(source_ids_by_video_id.values())
    metric_stmt = select(VideoMetric.source_id).where(VideoMetric.source_id.in_(source_ids)).distinct()
    source_ids_with_metrics = set(session.scalars(metric_stmt).all())
    return {
        video_id: source_id
        for video_id, source_id in source_ids_by_video_id.items()
        if source_id not in source_ids_with_metrics
    }


# ---------------------------------------------------------------------------
# Change-only storage
#
# The metrics tables are time-series, but most daily samples are byte-identical
# to the day before (a long tail of old videos whose views/likes/comments never
# move). We record a new row only when the payload *changed* vs the latest
# snapshot, so storage tracks activity rather than corpus size. Consequences:
#   - The latest row's `sampled_at` means "last CHANGED", not "last CHECKED".
#     Freshness ("was this re-confirmed today?") derives from the last
#     successful refresh run (cron-report / the refresh job's agent_runs row),
#     NOT from this table.
#   - The `*_latest_metrics` views still return the current value — the last
#     change IS the current state.
#   - Velocity reads must use as-of-cutoff semantics (most-recent row ≤ a
#     cutoff), never "the row at exactly N days ago"; gaps are expected.
# ---------------------------------------------------------------------------


def _metrics_changed(previous: dict | None, current: dict) -> bool:
    """True when `current` should be recorded — i.e. there is no prior snapshot,
    or the payload differs from the most recent stored one.

    `current` is the already-sliced payload (videos: `_METRIC_FIELDS`;
    channels: the subscribers/videos/views/country/channel_published_at dict).
    Comparison is plain dict equality, so JSONB key order and int/str
    round-tripping don't matter."""
    return previous is None or previous != current


def _latest_video_metrics(session: Session) -> dict[UUID, dict]:
    """source_id → its most-recent recorded metrics payload (the set the
    `video_latest_metrics` view exposes). Loaded once per refresh so the write
    loop can skip re-recording an unchanged snapshot. `metrics` is JSONB-typed,
    so rows come back as `dict`."""
    stmt = (
        select(VideoMetric.source_id, VideoMetric.metrics)
        .distinct(VideoMetric.source_id)
        .order_by(VideoMetric.source_id, VideoMetric.sampled_at.desc())
    )
    return {row.source_id: row.metrics for row in session.execute(stmt)}


def _latest_channel_metrics(session: Session) -> dict[UUID, dict]:
    """channel_id → its most-recent recorded metrics payload (the set the
    `channel_latest_metrics` view exposes). Twin of `_latest_video_metrics`."""
    stmt = (
        select(ChannelMetric.channel_id, ChannelMetric.metrics)
        .distinct(ChannelMetric.channel_id)
        .order_by(ChannelMetric.channel_id, ChannelMetric.sampled_at.desc())
    )
    return {row.channel_id: row.metrics for row in session.execute(stmt)}


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
    daily runs only fetch what's new. Pass `full_backfill=True` to ignore
    the cursor and pull up to `max_results` videos regardless.

    For each listed video whose `sources` row has no metrics yet, also writes
    a snapshot row into `video_metrics` (one batched stats call per 50 videos).

    Returns a small dict with counts for logging / API responses.
    """
    if channel.platform != "youtube" or not channel.external_id:
        return {"channel_id": str(channel.channel_id), "skipped": "not_youtube"}

    cursor_video_id = None if full_backfill else _most_recent_known_video_id(session, channel.channel_id)

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
    # call (handled below for rows still missing their first metrics).
    inserted_source_ids: dict[str, UUID] = {}  # video_id → source_id
    metrics_recorded = 0

    try:
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

        # Snapshot stats for newly inserted rows and for retry rows left without
        # a first metric by an older failed approval-time run.
        source_ids_for_metrics = _source_ids_missing_initial_video_metrics(
            session,
            channel.channel_id,
            [v["video_id"] for v in videos],
        )
        if source_ids_for_metrics:
            stats = youtube_api.get_video_stats(list(source_ids_for_metrics.keys()))
            sampled_at = datetime.now(UTC)
            for video_id, source_id in source_ids_for_metrics.items():
                entry = stats.get(video_id)
                if not entry:
                    continue
                # Patch identity fields that videos.list returns but playlistItems
                # didn't (duration in particular).
                duration = entry.get("duration_seconds")
                if duration is not None:
                    session.execute(
                        update(Source).where(Source.source_id == source_id).values(duration_seconds=duration)
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
    except Exception:
        session.rollback()
        raise

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
# All-video daily stats refresh
# ---------------------------------------------------------------------------


def refresh_all_video_stats(session: Session) -> dict[str, Any]:
    """Snapshot views/likes/comments for every active YouTube source AND
    sync identity fields (description, thumbnail, duration, title) onto
    each `sources` row.

    Two outcomes per video, both paid for in the same `videos.list` call:
      1. A new row in `video_metrics` carrying just the time-varying fields
         (views/likes/comments) — but **only when the payload changed** vs the
         video's latest snapshot (change-only storage; see `_metrics_changed`).
         Unchanged samples are skipped. Use `video_latest_metrics` for current
         state and the table itself for history.
      2. The `sources` row is updated to mirror YouTube's current identity
         fields. These can change (creators edit descriptions to add
         chapter timestamps, thumbnails get refreshed) so always-overwrite
         keeps the DB in sync rather than letting it drift. This is independent
         of the metric skip — identity always syncs.

    The skip applies only here. The first-snapshot writers — `refresh_channel_videos`
    (new-video discovery plus retry rows with no metrics), the channel-approval
    snapshot in `routers/recon.py`, and the `canonicalise_handles` backfill —
    have no prior metric row, so a skip would be a no-op; they're intentionally
    left unconditional.

    Quota: ~1 unit per 50 videos. ~180 channels × ~200 videos = ~720 units.
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
        return {"videos_refreshed": 0, "videos_unchanged": 0, "sources_synced": 0, "batches": 0}

    # Latest recorded metrics per source — loaded once so the loop can skip
    # re-recording an unchanged snapshot (change-only storage).
    latest = _latest_video_metrics(session)

    sampled_at = datetime.now(UTC)
    refreshed = 0
    unchanged = 0
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
                session.execute(update(Source).where(Source.source_id == source_id).values(**source_updates))
                sources_synced += 1

            metric_payload = {k: entry[k] for k in _METRIC_FIELDS if k in entry}
            if metric_payload:
                if _metrics_changed(latest.get(source_id), metric_payload):
                    session.add(
                        VideoMetric(
                            source_id=source_id,
                            sampled_at=sampled_at,
                            source="youtube_api",
                            metrics=metric_payload,
                        )
                    )
                    refreshed += 1
                else:
                    unchanged += 1

    session.commit()
    logger.info(
        "Refreshed video stats: %d recorded, %d unchanged in %d API batches, %d sources synced with identity fields",
        refreshed,
        unchanged,
        batches,
        sources_synced,
    )

    return {
        "videos_total": len(video_to_source),
        "videos_refreshed": refreshed,
        "videos_unchanged": unchanged,
        "sources_synced": sources_synced,
        "batches": batches,
    }


# ---------------------------------------------------------------------------
# Daily channel stats refresh
# ---------------------------------------------------------------------------


def refresh_all_channel_stats(session: Session) -> dict[str, Any]:
    """Snapshot subscriber / video / view counts for every active YouTube
    channel and append a row to `channel_metrics`.

    Cheap: 1 quota unit per 50 channels (channels.list batches up to 50).
    ~150 channels = 3 units per pass — safe to run daily.

    Two outcomes per channel, both paid for in the same channels.list call:
      1. New row in `channel_metrics` with the time-varying popularity
         fields (subscribers, videos, views) — but **only when the payload
         changed** vs the channel's latest snapshot (change-only storage; see
         `_metrics_changed`). Unchanged samples are skipped. Use
         `channel_latest_metrics` for current state and the table itself for
         trend analysis.
      2. Identity fields (handle, avatar_url) synced onto the `channels`
         row when the API returns them — keeps the wiki UI in sync without
         a separate fetch. Independent of the metric skip — identity always syncs.
    """
    channels = list(
        session.scalars(
            select(Channel)
            .where(Channel.platform == "youtube")
            .where(Channel.active.is_(True))
            .where(Channel.external_id.is_not(None))
        )
    )
    if not channels:
        return {
            "channels_total": 0,
            "metrics_recorded": 0,
            "channels_unchanged": 0,
            "channels_synced": 0,
            "batches": 0,
        }

    # Latest recorded metrics per channel — loaded once for change-only skip.
    latest = _latest_channel_metrics(session)

    by_external_id = {c.external_id: c for c in channels}
    external_ids = list(by_external_id.keys())
    sampled_at = datetime.now(UTC)

    metrics_recorded = 0
    unchanged = 0
    channels_synced = 0
    batches = 0
    for i in range(0, len(external_ids), 50):
        batch = external_ids[i : i + 50]
        stats = youtube_api.get_channel_stats(batch)
        batches += 1
        for entry in stats:
            channel = by_external_id.get(entry["channel_id"])
            if not channel:
                continue

            # Sync identity fields onto the channels row when the API gives
            # us something different from what we have. Only overwrite when
            # we got a non-empty value back — defensive against the API
            # dropping a field we already have stored.
            channel_updates: dict[str, Any] = {}
            new_handle = entry.get("handle")
            if new_handle and new_handle != channel.handle:
                channel_updates["handle"] = new_handle
            new_avatar = entry.get("avatar_url")
            if new_avatar and new_avatar != channel.logo_url:
                channel_updates["logo_url"] = new_avatar
            if channel_updates:
                session.execute(
                    update(Channel).where(Channel.channel_id == channel.channel_id).values(**channel_updates)
                )
                channels_synced += 1

            # Time-varying popularity fields → channel_metrics. Match the
            # canonical shape established in migration 023 + recon.py
            # _normalised_youtube_metrics: subscribers / videos / views /
            # country / channel_published_at.
            metric_payload: dict[str, Any] = {}
            if entry.get("subs") is not None:
                metric_payload["subscribers"] = entry["subs"]
            if entry.get("video_count"):
                metric_payload["videos"] = entry["video_count"]
            if entry.get("view_count"):
                metric_payload["views"] = entry["view_count"]
            if entry.get("country"):
                metric_payload["country"] = entry["country"]
            if entry.get("published_at"):
                metric_payload["channel_published_at"] = entry["published_at"]

            if metric_payload:
                if _metrics_changed(latest.get(channel.channel_id), metric_payload):
                    session.add(
                        ChannelMetric(
                            channel_id=channel.channel_id,
                            platform="youtube",
                            sampled_at=sampled_at,
                            source="youtube_api",
                            metrics=metric_payload,
                        )
                    )
                    metrics_recorded += 1
                else:
                    unchanged += 1

    session.commit()
    logger.info(
        "Refreshed channel stats: %d recorded, %d unchanged in %d API batches, %d identity-synced",
        metrics_recorded,
        unchanged,
        batches,
        channels_synced,
    )

    return {
        "channels_total": len(channels),
        "metrics_recorded": metrics_recorded,
        "channels_unchanged": unchanged,
        "channels_synced": channels_synced,
        "batches": batches,
    }


# ---------------------------------------------------------------------------
# Coverage audit — reported vs ingested
# ---------------------------------------------------------------------------


def audit_channel_coverage(session: Session) -> dict[str, Any]:
    """Per-channel funnel — how far each channel's videos have travelled
    through the pipeline. Surfaces both ingestion gaps and downstream
    processing dropoffs.

    Stages (per channel) — same vocabulary as /admin/pipeline:
      - reported    YouTube's video count (channel_metrics latest snapshot)
      - tracked     rows in `sources` for this channel
      - transcribed sources whose transcript has been saved
                    (SourceDocument.s3_key IS NOT NULL)
      - chunked     sources with SourceDocument.chunk_count > 0
      - cleaned     sources with at least one SourceChunk where clean_text
                    IS NOT NULL
      - extracted   sources with at least one Claim row

    Also surfaces totals to mirror the per-row Chunks/Claims columns on the
    /admin/pipeline view:
      - chunks_total  SUM(SourceDocument.chunk_count) across the channel
      - claims_total  COUNT(Claim) across the channel

    `gap = reported - tracked` is preserved for the headline summary line.

    Pure DB read — no YouTube API calls. Reported-count freshness depends
    on the daily `refresh_all_channel_stats()` cron.
    """
    tracked_subq = (
        select(
            Source.channel_id,
            func.count().label("tracked_videos"),
        )
        .where(Source.source_type == "youtube")
        .group_by(Source.channel_id)
        .subquery()
    )
    # "Transcribed" — distinct sources with at least one SourceDocument that
    # has an s3_key (transcript saved). Mirrors /admin/pipeline.
    transcribed_subq = (
        select(
            Source.channel_id,
            func.count(distinct(Source.source_id)).label("transcribed_videos"),
        )
        .join(SourceDocument, SourceDocument.source_id == Source.source_id)
        .where(Source.source_type == "youtube")
        .where(SourceDocument.s3_key.is_not(None))
        .group_by(Source.channel_id)
        .subquery()
    )
    # "Chunked" — distinct sources whose SourceDocument has chunks loaded,
    # plus the total chunk count across the channel for the right-hand
    # Chunks column. Mirrors /admin/pipeline's `chunked` boolean.
    chunked_subq = (
        select(
            Source.channel_id,
            func.count(distinct(Source.source_id)).label("chunked_videos"),
            func.coalesce(func.sum(SourceDocument.chunk_count), 0).label("chunks_total"),
        )
        .join(SourceDocument, SourceDocument.source_id == Source.source_id)
        .where(Source.source_type == "youtube")
        .where(SourceDocument.chunk_count > 0)
        .group_by(Source.channel_id)
        .subquery()
    )
    # "Cleaned" — distinct sources with at least one SourceChunk whose
    # clean_text is populated. Mirrors /admin/pipeline's bool_or check.
    cleaned_subq = (
        select(
            Source.channel_id,
            func.count(distinct(Source.source_id)).label("cleaned_videos"),
        )
        .join(SourceDocument, SourceDocument.source_id == Source.source_id)
        .join(SourceChunk, SourceChunk.document_id == SourceDocument.document_id)
        .where(Source.source_type == "youtube")
        .where(SourceChunk.clean_text.is_not(None))
        .group_by(Source.channel_id)
        .subquery()
    )
    # "Extracted" — distinct sources with at least one Claim, plus the
    # total claim count for the channel. Mirrors /admin/pipeline's
    # `extracted` boolean and the per-row Claims column.
    extracted_subq = (
        select(
            Source.channel_id,
            func.count(distinct(Source.source_id)).label("extracted_videos"),
            func.count(Claim.claim_id).label("claims_total"),
        )
        .join(SourceDocument, SourceDocument.source_id == Source.source_id)
        .join(Claim, Claim.document_id == SourceDocument.document_id)
        .where(Source.source_type == "youtube")
        .group_by(Source.channel_id)
        .subquery()
    )
    latest_subq = (
        select(
            ChannelMetric.channel_id,
            ChannelMetric.sampled_at,
            ChannelMetric.metrics["videos"].astext.cast(Integer).label("reported_videos"),
        )
        .distinct(ChannelMetric.channel_id)
        .order_by(ChannelMetric.channel_id, ChannelMetric.sampled_at.desc())
        .subquery()
    )
    stmt = (
        select(
            Channel.channel_id,
            Channel.slug,
            Channel.name,
            Channel.external_id,
            tracked_subq.c.tracked_videos,
            transcribed_subq.c.transcribed_videos,
            chunked_subq.c.chunked_videos,
            chunked_subq.c.chunks_total,
            cleaned_subq.c.cleaned_videos,
            extracted_subq.c.extracted_videos,
            extracted_subq.c.claims_total,
            latest_subq.c.reported_videos,
            latest_subq.c.sampled_at,
        )
        .select_from(Channel)
        .outerjoin(tracked_subq, tracked_subq.c.channel_id == Channel.channel_id)
        .outerjoin(transcribed_subq, transcribed_subq.c.channel_id == Channel.channel_id)
        .outerjoin(chunked_subq, chunked_subq.c.channel_id == Channel.channel_id)
        .outerjoin(cleaned_subq, cleaned_subq.c.channel_id == Channel.channel_id)
        .outerjoin(extracted_subq, extracted_subq.c.channel_id == Channel.channel_id)
        .outerjoin(latest_subq, latest_subq.c.channel_id == Channel.channel_id)
        .where(Channel.platform == "youtube")
        .where(Channel.active.is_(True))
        .order_by(Channel.name)
    )

    per_channel: list[dict[str, Any]] = []
    channels_with_gap = 0
    total_gap = 0
    for r in session.execute(stmt).all():
        tracked = int(r.tracked_videos or 0)
        transcribed = int(r.transcribed_videos or 0)
        chunked = int(r.chunked_videos or 0)
        cleaned = int(r.cleaned_videos or 0)
        extracted = int(r.extracted_videos or 0)
        chunks_total = int(r.chunks_total or 0)
        claims_total = int(r.claims_total or 0)
        reported = int(r.reported_videos) if r.reported_videos is not None else None
        gap = (reported - tracked) if reported is not None else None
        if gap is not None and gap > 0:
            total_gap += gap
            channels_with_gap += 1
        per_channel.append(
            {
                "channel_id": str(r.channel_id),
                "slug": r.slug,
                "name": r.name,
                "external_id": r.external_id,
                "reported_videos": reported,
                "tracked_videos": tracked,
                "transcribed_videos": transcribed,
                "chunked_videos": chunked,
                "cleaned_videos": cleaned,
                "extracted_videos": extracted,
                "chunks_total": chunks_total,
                "claims_total": claims_total,
                "gap": gap,
                "metrics_sampled_at": r.sampled_at.isoformat() if r.sampled_at else None,
            }
        )

    return {
        "channels_total": len(per_channel),
        "channels_with_gap": channels_with_gap,
        "total_gap": total_gap,
        "per_channel": per_channel,
    }


def refresh_all_channels_incremental(session: Session) -> dict[str, Any]:
    """Walk every active YouTube channel and pull any new videos. Cheap:
    ~1 quota unit per channel for incremental (most weeks, no new videos
    means a single playlistItems page that hits the cursor immediately)."""
    stmt = select(Channel).where(Channel.platform == "youtube").where(Channel.active.is_(True))
    channels = list(session.scalars(stmt))

    per_channel: list[dict[str, Any]] = []
    total_inserted = 0
    for channel in channels:
        try:
            result = refresh_channel_videos(session, channel)
        except Exception as e:
            logger.warning("refresh_channel_videos failed for %s: %s", channel.external_id, e)
            per_channel.append(
                {
                    "channel_id": str(channel.channel_id),
                    "external_id": channel.external_id,
                    "error": str(e),
                }
            )
            continue
        total_inserted += result.get("videos_inserted", 0)
        per_channel.append(result)

    return {
        "channels_processed": len(channels),
        "total_videos_inserted": total_inserted,
        "per_channel": per_channel,
    }


# ---------------------------------------------------------------------------
# Audited job wrappers
# ---------------------------------------------------------------------------


def _enumerate_channel_failures(result: dict[str, Any] | None) -> list[dict[str, Any]]:
    per_channel = (result or {}).get("per_channel") or []
    return [row for row in per_channel if row.get("error")]


def _compact_enumerate_detail(result: dict[str, Any]) -> dict[str, Any]:
    """Summarise the per-channel enumerate result for agent_runs.detail_json."""
    per_channel = result.get("per_channel") or []
    failed = _enumerate_channel_failures(result)
    detail = {k: v for k, v in result.items() if k != "per_channel"}
    detail["per_channel_count"] = len(per_channel)
    detail["channels_failed"] = len(failed)
    if failed:
        detail["channel_errors"] = failed[:20]
    return detail


def _channel_detail(channel: Channel) -> dict[str, Any]:
    return {
        "channel_id": str(channel.channel_id),
        "channel_slug": getattr(channel, "slug", None),
        "channel_name": channel.name,
        "external_id": channel.external_id,
    }


def run_youtube_refresh_videos(
    session: Session,
    *,
    skip_stats: bool = False,
    skip_enumerate: bool = False,
) -> dict[str, Any]:
    """Run the daily YouTube refresh endpoint under a Scout agent_runs row."""
    run = start_deterministic_run(
        session,
        pipeline=PIPELINE_YOUTUBE_REFRESH_VIDEOS,
        brief=(
            "YouTube refresh: incremental channel video enumeration "
            f"and video stats (skip_enumerate={skip_enumerate}, skip_stats={skip_stats})"
        ),
        detail={"skip_stats": skip_stats, "skip_enumerate": skip_enumerate},
        max_wall_seconds=1800,
    )
    enumerate_result: dict[str, Any] | None = None
    stats_result: dict[str, Any] | None = None

    try:
        if not skip_enumerate:
            enumerate_result = refresh_all_channels_incremental(session)
            run.detail["enumerate"] = _compact_enumerate_detail(enumerate_result)
        if not skip_stats:
            stats_result = refresh_all_video_stats(session)
            run.detail["stats"] = stats_result
    except Exception as e:
        if enumerate_result is not None:
            run.detail["enumerate"] = _compact_enumerate_detail(enumerate_result)
        if stats_result is not None:
            run.detail["stats"] = stats_result
        run.fail(e, summary_text=f"YouTube refresh-videos failed: {e}")
        raise

    channels_processed = (enumerate_result or {}).get("channels_processed", 0)
    videos_inserted = (enumerate_result or {}).get("total_videos_inserted", 0)
    videos_refreshed = (stats_result or {}).get("videos_refreshed", 0)
    enumerate_failures = _enumerate_channel_failures(enumerate_result)
    if enumerate_failures:
        error = RuntimeError(
            f"{len(enumerate_failures)} of {channels_processed} YouTube channel enumerations failed"
        )
        run.detail["partial_failure"] = True
        run.fail(
            error,
            summary_text=(
                "YouTube refresh-videos partial failure: "
                f"channels_processed={channels_processed}, "
                f"channels_failed={len(enumerate_failures)}, "
                f"videos_inserted={videos_inserted}, "
                f"videos_refreshed={videos_refreshed}"
            ),
        )
        return {
            "run_id": run.run_id,
            "ok": False,
            "enumerate": enumerate_result,
            "stats": stats_result,
            "error": str(error),
        }

    run.complete(
        summary_text=(
            "YouTube refresh-videos: "
            f"channels_processed={channels_processed}, "
            f"videos_inserted={videos_inserted}, "
            f"videos_refreshed={videos_refreshed}"
        )
    )

    return {
        "run_id": run.run_id,
        "ok": True,
        "enumerate": enumerate_result,
        "stats": stats_result,
    }


def run_youtube_channel_videos(
    session: Session,
    channel: Channel,
    *,
    max_results: int = 200,
    full_backfill: bool = False,
) -> dict[str, Any]:
    """Enumerate one channel's uploads under a Scout agent_runs row."""
    run = start_deterministic_run(
        session,
        pipeline=PIPELINE_YOUTUBE_CHANNEL_VIDEOS,
        brief=(
            f"YouTube channel video enumerate: {channel.name} "
            f"(full_backfill={full_backfill}, max_results={max_results})"
        ),
        detail={
            **_channel_detail(channel),
            "full_backfill": full_backfill,
            "max_results": max_results,
        },
        max_wall_seconds=900,
    )
    try:
        result = refresh_channel_videos(
            session,
            channel,
            max_results=max_results,
            full_backfill=full_backfill,
        )
        run.detail.update(result)
    except Exception as e:
        run.fail(e, summary_text=f"YouTube channel video enumerate failed: {e}")
        raise

    run.complete(
        summary_text=(
            "YouTube channel video enumerate: "
            f"channel_id={channel.channel_id}, "
            f"videos_inserted={result.get('videos_inserted', 0)}, "
            f"metrics_recorded={result.get('metrics_recorded', 0)}"
        )
    )
    return {"run_id": run.run_id, "ok": True, **result}


def run_youtube_channel_stats(session: Session) -> dict[str, Any]:
    """Run the YouTube channel metrics refresh under a Scout agent_runs row."""
    run = start_deterministic_run(
        session,
        pipeline=PIPELINE_YOUTUBE_CHANNEL_STATS,
        brief="YouTube channel stats refresh",
        detail={},
        max_wall_seconds=600,
    )
    try:
        result = refresh_all_channel_stats(session)
        run.detail.update(result)
    except Exception as e:
        run.fail(e, summary_text=f"YouTube channel stats refresh failed: {e}")
        raise

    run.complete(
        summary_text=(
            "YouTube channel stats refresh: "
            f"channels_total={result.get('channels_total', 0)}, "
            f"metrics_recorded={result.get('metrics_recorded', 0)}, "
            f"channels_unchanged={result.get('channels_unchanged', 0)}"
        )
    )
    return {"run_id": run.run_id, "ok": True, **result}
