"""Persistent video acquisition for legacy/debug visual workflows.

For one ``sources`` row:

    1. yt-dlp video download at low resolution (default 360p) →
       s3://jeromelu-raw-audio/youtube/{channel_id}/{video_id}.video.mp4
       (low-res sits in the same bucket as audio for lifecycle simplicity).
    2. ``sources.video_s3_key`` populated.

Independent of audio acquisition — running ``acquire_persistent_video`` on a row
that already has ``audio_s3_key`` set is fine and won't disturb the audio
state. Idempotent on the S3 object.

This is not the main visual-ID path anymore; Analyst now stages video
ephemerally per request. Keep this for one-off enrolment/debugging and old
rows with persistent ``sources.video_s3_key``.

Failure mode: ``PersistentVideoError`` raised, sources row left as-is.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yt_dlp
from jeromelu_shared.config import settings
from jeromelu_shared.db import Source
from sqlalchemy.orm import Session
from youtube_utils.exceptions import DownloadError

from .keys import youtube_persistent_video_key
from .s3 import media_object_exists, upload_media_file
from .source import resolve_youtube_media_source

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result + errors
# ---------------------------------------------------------------------------


@dataclass
class PersistentVideoResult:
    source_id: str
    video_s3_key: str
    bytes_uploaded: int | None  # None if the object already existed in S3


class PersistentVideoError(Exception):
    """Raised when video acquisition fails."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

#: Default quality for face-detection downloads. 240p is enough for
#: detection of front-facing podcast faces but degrades on side angles
#: and small/distant faces. 360p is the balance.
DEFAULT_QUALITY = "360"


def _yt_dlp_low_res_video(video_id: str, output_dir: Path, quality: str) -> Path:
    """Download a single-stream low-res video via yt-dlp.

    Avoids the ``bestvideo+bestaudio`` merge path (which produced flaky
    filename detection in ``youtube_utils.download.download_video``).
    Prefers a single combined-stream format (audio baked in) at the
    requested height, falling back gracefully.
    """
    # Single-stream selector: prefer mp4 of the requested height-or-less,
    # then any combined stream at that height, then any worst combined.
    fmt = (
        f"best[ext=mp4][vcodec!*=none][acodec!*=none][height<={quality}]"
        f"/best[vcodec!*=none][acodec!*=none][height<={quality}]"
        f"/worst[vcodec!*=none][acodec!*=none]"
    )
    out_template = str(output_dir / f"{video_id}.%(ext)s")
    opts = {
        "format": fmt,
        "outtmpl": out_template,
        "logger": logger,
        "quiet": True,
        "noprogress": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    except Exception as exc:
        raise DownloadError(f"yt-dlp failed for {video_id}: {exc}") from exc

    # Find the resulting file. Single-stream fmt → no merge → file lands
    # at <video_id>.<ext> where ext is whatever the chosen format used.
    candidates = list(output_dir.glob(f"{video_id}.*"))
    if not candidates:
        raise DownloadError(f"yt-dlp produced no output in {output_dir} for {video_id}")
    # Prefer mp4 if multiple; otherwise the first match.
    mp4s = [c for c in candidates if c.suffix == ".mp4"]
    return mp4s[0] if mp4s else candidates[0]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def acquire_persistent_video(
    session: Session,
    source: Source,
    *,
    quality: str = DEFAULT_QUALITY,
) -> PersistentVideoResult:
    """Pull video for a single Source. Idempotent on the S3 object.

    Sets ``sources.video_s3_key``. Does not touch ``ingestion_status``
    or any other state — video acquisition is independent of Miner's
    main audio-first lifecycle.
    """
    media = resolve_youtube_media_source(source, error_cls=PersistentVideoError)
    video_key = youtube_persistent_video_key(media)

    bytes_uploaded: int | None = None
    if media_object_exists(video_key):
        logger.info(
            "Video already in S3: s3://%s/%s",
            settings.s3_audio_bucket,
            video_key,
        )
    else:
        with tempfile.TemporaryDirectory(prefix="jeromelu-video-") as tmp:
            try:
                local_path = _yt_dlp_low_res_video(media.video_id, Path(tmp), quality)
            except DownloadError as exc:
                raise PersistentVideoError(f"yt-dlp video download failed for {media.video_id}: {exc}") from exc

            bytes_uploaded = local_path.stat().st_size
            size_mb = bytes_uploaded / (1024 * 1024)
            logger.info(
                "Downloaded video: %s (%.1f MB, quality<=%s)",
                local_path.name,
                size_mb,
                quality,
            )
            upload_media_file(video_key, str(local_path), content_type="video/mp4")
            logger.info(
                "Uploaded to s3://%s/%s",
                settings.s3_audio_bucket,
                video_key,
            )

    source.video_s3_key = video_key
    session.commit()

    return PersistentVideoResult(
        source_id=media.source_id,
        video_s3_key=video_key,
        bytes_uploaded=bytes_uploaded,
    )
