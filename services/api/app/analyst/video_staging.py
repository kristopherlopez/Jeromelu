"""Ephemeral video staging for the Lineup pipeline.

Background: ``services/api/app/miner/media/persistent_video.py`` was the
original Phase-4 acquisition path — it persisted the low-res mp4 under
``youtube/<channel>/<video_id>.video.mp4`` and stamped
``sources.video_s3_key`` so the review UI could presign the file for
playback. That was always intended to be a 30-day-lifecycle artefact;
in practice the only consumer that actually needed durable storage was
the review UI's overlay layer.

After Chunk 1 of the ephemeral-video plan, the review UI overlays the
face-track JSON on the YouTube embed directly — the local mp4 isn't on
the critical path anymore. This module replaces persistent acquisition
with a context manager that:

    1. yt-dlps to a temp dir on the API host.
    2. Uploads to a per-request staging key in the audio bucket.
    3. Yields the key to the caller (typically ``visual_identify`` /
       ``visual_identify_remote`` — both expect an S3 key, so the
       contract with the GPU container is unchanged).
    4. Deletes the staging object on exit, success or fail.

Bucket-side safety net: the ``staging/video/`` prefix gets a 24h
lifecycle rule (set in Terraform) so an object survives a process
crash without becoming permanent storage debt.

The pre-existing persistent path stays callable from
``acquire_video_cli.py`` for one-off enrolment / debugging needs, but
the lineup pipeline no longer reaches for it.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from jeromelu_shared.config import settings
from jeromelu_shared.s3 import get_s3_client
from jeromelu_shared.youtube import extract_video_id

logger = logging.getLogger(__name__)


#: Quality cap for ephemeral downloads. Mirrors ``DEFAULT_QUALITY`` in
#: ``miner/media/persistent_video.py`` so the face-detection pipeline sees the same pixel
#: density it was tuned against.
DEFAULT_QUALITY = "360"

#: Staging prefix in the audio bucket. The same bucket hosts the
#: persistent ``youtube/<channel>/<video_id>.video.mp4`` keys; staging
#: lives under its own prefix so a lifecycle rule can target it
#: without affecting the historical persistent rows.
STAGING_PREFIX = "staging/video"


class VideoStagingError(Exception):
    """Raised when ephemeral acquisition or upload fails."""


_video_id_from_url = extract_video_id


def _staging_key(request_id: str) -> str:
    return f"{STAGING_PREFIX}/{request_id}.mp4"


def _yt_dlp_low_res_video(video_id: str, output_dir: Path, quality: str) -> Path:
    """Single-stream low-res download. Same selector as the persistent
    Miner path, so the file format / codec the GPU container sees is
    identical."""
    # Lazy-imported: yt-dlp is not in the API container per
    # feedback_api_container_lean.md. This module is on the API import path
    # via routers/sources.py, but its downloader functions are only invoked
    # by the lineup pipeline (which runs out-of-process). Keeping the import
    # inside the function lets the API boot without yt-dlp installed; if a
    # caller ever invokes this from the API, the ModuleNotFoundError will
    # surface here and signal the architectural boundary was crossed.
    import yt_dlp

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
        raise VideoStagingError(f"yt-dlp failed for {video_id}: {exc}") from exc

    candidates = list(output_dir.glob(f"{video_id}.*"))
    if not candidates:
        raise VideoStagingError(f"yt-dlp produced no output in {output_dir} for {video_id}")
    mp4s = [c for c in candidates if c.suffix == ".mp4"]
    return mp4s[0] if mp4s else candidates[0]


def _upload(local_path: Path, key: str) -> int:
    client = get_s3_client()
    client.upload_file(
        str(local_path),
        settings.s3_audio_bucket,
        key,
        ExtraArgs={"ContentType": "video/mp4"},
    )
    return local_path.stat().st_size


def delete_staging_video(key: str) -> None:
    """Best-effort delete of a staging key. The 24h lifecycle rule
    catches any leak, so we log on failure rather than raising."""
    if not key.startswith(f"{STAGING_PREFIX}/"):
        # Caller handed us a persistent key (legacy ``video_s3_key``).
        # Refuse to delete; only ephemeral staging keys are ours to clean.
        return
    client = get_s3_client()
    try:
        client.delete_object(Bucket=settings.s3_audio_bucket, Key=key)
        logger.info("Deleted staging video: s3://%s/%s", settings.s3_audio_bucket, key)
    except Exception as exc:
        logger.warning(
            "delete_staging_video failed for %s — lifecycle will eventually clean: %s",
            key,
            exc,
        )


def download_persistent_video(video_s3_key: str, dest: Path) -> None:
    """Pull a persisted ``sources.video_s3_key`` mp4 from S3 to ``dest``.

    Used by the legacy fast-path in surfaces that have a stored video key
    (the lone pre-ephemeral source, or a source where someone manually
    ran ``make collect-video``).
    """
    get_s3_client().download_file(
        settings.s3_audio_bucket,
        video_s3_key,
        str(dest),
    )


def extract_frame(video_path: Path, ts: float, dest: Path) -> None:
    """Dump a single JPEG at ``ts`` from a local video file via ffmpeg.

    Raises :class:`VideoStagingError` if ffmpeg is missing or the call
    exits non-zero.
    """
    if shutil.which("ffmpeg") is None:
        raise VideoStagingError("ffmpeg not found on PATH")
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{ts:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(dest),
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise VideoStagingError(
            f"ffmpeg frame extraction failed at ts={ts}: {proc.stderr.decode('utf-8', errors='replace')[:500]}"
        )


def acquire_video_temp(canonical_url: str, *, quality: str = DEFAULT_QUALITY) -> str:
    """Download a YouTube video to a per-request staging key.

    Returns the staging S3 key. Caller MUST call
    :func:`delete_staging_video` on it (a ``finally`` block, or the
    :func:`staged_video` context manager).
    """
    video_id = _video_id_from_url(canonical_url)
    if not video_id:
        raise VideoStagingError(f"could not parse YouTube video id from {canonical_url!r}")

    request_id = uuid4().hex
    key = _staging_key(request_id)

    with tempfile.TemporaryDirectory(prefix="jeromelu-video-staging-") as tmp:
        local_path = _yt_dlp_low_res_video(video_id, Path(tmp), quality)
        size = _upload(local_path, key)
        logger.info(
            "Staged video: s3://%s/%s (%.1f MB)",
            settings.s3_audio_bucket,
            key,
            size / (1024 * 1024),
        )
    return key


@contextmanager
def staged_video_local(canonical_url: str, *, quality: str = DEFAULT_QUALITY) -> Iterator[Path]:
    """yt-dlp the YouTube URL to a local temp file and yield its path.

    Used by surfaces that consume the video file in-process (the reassign
    endpoint extracts a single frame via ffmpeg) — no S3 hop needed, so
    we skip the upload and let the TemporaryDirectory clean up on exit.
    """
    video_id = _video_id_from_url(canonical_url)
    if not video_id:
        raise VideoStagingError(f"could not parse YouTube video id from {canonical_url!r}")

    with tempfile.TemporaryDirectory(prefix="jeromelu-video-local-") as tmp:
        local_path = _yt_dlp_low_res_video(video_id, Path(tmp), quality)
        size = local_path.stat().st_size
        logger.info(
            "Local-staged video: %s (%.1f MB)",
            local_path,
            size / (1024 * 1024),
        )
        yield local_path


@contextmanager
def staged_video(
    canonical_url: str | None, *, persistent_key: str | None = None, quality: str = DEFAULT_QUALITY
) -> Iterator[str | None]:
    """Yield an S3 key the GPU container can consume, with cleanup.

    Three regimes:

    - ``persistent_key`` set (a row still has ``sources.video_s3_key``):
      yields it as-is, does NOT delete on exit. Legacy fast-path for
      sources that haven't been migrated to the ephemeral world yet.
    - ``persistent_key`` is None and ``canonical_url`` is a YouTube URL:
      yt-dlps + uploads to staging, yields the staging key, deletes on
      exit (success or fail).
    - Both are None: yields ``None`` so the caller can branch into
      voice-only fusion without raising.
    """
    if persistent_key:
        yield persistent_key
        return

    if not canonical_url:
        yield None
        return

    key = acquire_video_temp(canonical_url, quality=quality)
    try:
        yield key
    finally:
        delete_staging_video(key)
