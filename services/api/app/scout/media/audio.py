"""Audio acquisition — Scout's transcript-pull surface.

For one `sources` row:

    1. yt-dlp audio-only download (m4a) → s3://jeromelu-raw-audio/youtube/
       {channel_id}/{video_id}.m4a. Idempotent on the S3 object.
    2. sources.audio_s3_key set, ingestion_status='collected'.

Extract-only. Producing a structured transcript from this audio is the
[Analyst transcription surface](../analyst/transcribe.py).

Failure mode: yt-dlp errors → ingestion_status='failed', AudioError raised.
No fallback to YouTube auto-captions.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass

from sqlalchemy.orm import Session
from youtube_utils import download_audio
from youtube_utils.exceptions import DownloadError

from jeromelu_shared.config import settings
from jeromelu_shared.db import Source

from .keys import youtube_audio_key
from .s3 import media_object_exists, upload_media_file
from .source import resolve_youtube_media_source

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result + errors
# ---------------------------------------------------------------------------

@dataclass
class AudioResult:
    source_id: str
    audio_s3_key: str
    bytes_uploaded: int | None  # None if the object already existed in S3


class AudioError(Exception):
    """Raised when audio acquisition fails. The source row is marked
    `ingestion_status='failed'` before the exception propagates."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def acquire_audio(session: Session, source: Source) -> AudioResult:
    """Pull audio for a single Source. Idempotent on the S3 object.

    On success: returns ``AudioResult``, source row updated to
    ``ingestion_status='collected'`` and ``audio_s3_key`` populated.

    On failure: ``ingestion_status='failed'``, ``AudioError`` raised.
    """
    media = resolve_youtube_media_source(source, error_cls=AudioError)
    audio_key = youtube_audio_key(media)

    try:
        bytes_uploaded: int | None = None
        if media_object_exists(audio_key):
            logger.info(
                "Audio already in S3: s3://%s/%s",
                settings.s3_audio_bucket, audio_key,
            )
        else:
            with tempfile.TemporaryDirectory(prefix="jeromelu-audio-") as tmp:
                try:
                    local_path = download_audio(
                        media.video_id,
                        output_dir=tmp,
                        format="m4a",
                    )
                except DownloadError as exc:
                    raise AudioError(
                        f"yt-dlp download failed for {media.video_id}: {exc}"
                    ) from exc

                bytes_uploaded = local_path.stat().st_size
                size_mb = bytes_uploaded / (1024 * 1024)
                logger.info("Downloaded audio: %s (%.1f MB)", local_path.name, size_mb)
                upload_media_file(audio_key, str(local_path), content_type="audio/mp4")
                logger.info(
                    "Uploaded to s3://%s/%s",
                    settings.s3_audio_bucket, audio_key,
                )

        source.audio_s3_key = audio_key
        source.ingestion_status = "collected"
        session.commit()

        return AudioResult(
            source_id=media.source_id,
            audio_s3_key=audio_key,
            bytes_uploaded=bytes_uploaded,
        )

    except Exception as exc:
        session.rollback()
        try:
            session.refresh(source)
            source.ingestion_status = "failed"
            session.commit()
        except Exception:
            session.rollback()
            logger.exception(
                "Failed to mark ingestion_status='failed'; manual cleanup required"
            )
        if isinstance(exc, AudioError):
            raise
        raise AudioError(str(exc)) from exc
