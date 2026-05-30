"""Shared source helpers for Miner media acquisition."""

from __future__ import annotations

from dataclasses import dataclass

from jeromelu_shared.db import Source
from jeromelu_shared.youtube import extract_video_id


@dataclass(frozen=True)
class YoutubeMediaSource:
    source_id: str
    video_id: str
    channel_external_id: str


def resolve_youtube_media_source(
    source: Source,
    *,
    error_cls: type[Exception],
) -> YoutubeMediaSource:
    """Validate a Source row and return the fields needed for media S3 keys."""
    if source.source_type != "youtube":
        raise error_cls(f"media acquisition only supports source_type='youtube', got {source.source_type!r}")

    video_id = extract_video_id(source.canonical_url)
    if not video_id:
        raise error_cls(f"could not parse video_id from {source.canonical_url!r}")

    if not source.channel_id:
        raise error_cls(f"source {source.source_id} has no channel_id; cannot derive S3 path")

    channel_external_id = source.channel.external_id if source.channel else None
    if not channel_external_id:
        raise error_cls(f"channel {source.channel_id} has no external_id; cannot derive S3 path")

    return YoutubeMediaSource(
        source_id=str(source.source_id),
        video_id=video_id,
        channel_external_id=channel_external_id,
    )
