"""S3 key helpers for Miner media acquisition."""

from __future__ import annotations

from typing import Protocol

YOUTUBE_MEDIA_PREFIX = "youtube"
AUDIO_SUFFIX = ".m4a"
PERSISTENT_VIDEO_SUFFIX = ".video.mp4"


class YoutubeMediaIdentity(Protocol):
    video_id: str
    channel_external_id: str


def youtube_media_key(media: YoutubeMediaIdentity, suffix: str) -> str:
    return f"{YOUTUBE_MEDIA_PREFIX}/{media.channel_external_id}/{media.video_id}{suffix}"


def youtube_audio_key(media: YoutubeMediaIdentity) -> str:
    return youtube_media_key(media, AUDIO_SUFFIX)


def youtube_persistent_video_key(media: YoutubeMediaIdentity) -> str:
    return youtube_media_key(media, PERSISTENT_VIDEO_SUFFIX)
