"""HTTP client for the video-worker sidecar (services/video-worker).

The API talks to the worker over the docker-internal network. The worker
owns yt-dlp + ffmpeg so the API image stays lean (see
``feedback_api_container_lean.md``).

Public surface:
    fetch_frame_to(...)  — pull one JPEG from a video into a local Path.
    stage_video(...)     — yt-dlp a YouTube URL to an S3 staging key.
    delete_staging(...)  — explicit cleanup of a staging key.

All functions raise :class:`VideoWorkerError` on transport / 5xx errors.
The 24h S3 lifecycle on ``staging/video/`` is the safety net if a caller
crashes between ``stage_video`` and ``delete_staging``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

from jeromelu_shared.config import settings

logger = logging.getLogger(__name__)


class VideoWorkerError(Exception):
    """Raised when the worker is unreachable or returns a non-2xx."""


def _client(timeout: float) -> httpx.Client:
    return httpx.Client(base_url=settings.video_worker_url, timeout=timeout)


def fetch_frame_to(
    dest: Path,
    *,
    canonical_url: str | None = None,
    persistent_video_s3_key: str | None = None,
    ts: float,
    quality: str | None = None,
    prefer_section: bool = False,
    bbox: tuple[float, float, float, float] | None = None,
    timeout: float = 600.0,
) -> None:
    """Ask the worker for one JPEG at ``ts`` and write its bytes to ``dest``.

    Supply at least one of ``canonical_url`` (yt-dlp on the worker) or
    ``persistent_video_s3_key`` (worker downloads the staged mp4 from S3
    and skips yt-dlp). When both are given, ``prefer_section=True`` asks
    the worker to yt-dlp only a few seconds around ``ts`` instead of
    pulling the full file — single-frame fast path used by reassign.
    """
    if not canonical_url and not persistent_video_s3_key:
        raise VideoWorkerError(
            "Supply at least one of canonical_url or persistent_video_s3_key"
        )

    payload: dict[str, object] = {"ts": ts}
    if canonical_url:
        payload["canonical_url"] = canonical_url
    if persistent_video_s3_key:
        payload["persistent_video_s3_key"] = persistent_video_s3_key
    if quality:
        payload["quality"] = quality
    if prefer_section:
        payload["prefer_section"] = True
    if bbox is not None:
        payload["bbox"] = list(bbox)

    try:
        with _client(timeout) as c:
            r = c.post("/extract-frame", json=payload)
    except httpx.HTTPError as exc:
        raise VideoWorkerError(f"video-worker unreachable: {exc}") from exc

    if r.status_code != 200:
        raise VideoWorkerError(
            f"video-worker /extract-frame returned {r.status_code}: {r.text[:300]}"
        )

    dest.write_bytes(r.content)


def stage_video(
    canonical_url: str,
    *,
    quality: str | None = None,
    timeout: float = 600.0,
) -> str:
    """Stage a YouTube video to S3. Returns the staging key (the bucket
    matches ``settings.s3_audio_bucket``). Caller MUST call
    :func:`delete_staging` once done."""
    payload: dict[str, object] = {"canonical_url": canonical_url}
    if quality:
        payload["quality"] = quality

    try:
        with _client(timeout) as c:
            r = c.post("/stage-video", json=payload)
    except httpx.HTTPError as exc:
        raise VideoWorkerError(f"video-worker unreachable: {exc}") from exc

    if r.status_code != 200:
        raise VideoWorkerError(
            f"video-worker /stage-video returned {r.status_code}: {r.text[:300]}"
        )
    return r.json()["staging_key"]


def delete_staging(staging_key: str, *, timeout: float = 30.0) -> None:
    """Best-effort delete. Logs a warning on failure rather than raising —
    the S3 lifecycle rule on ``staging/video/`` cleans up after 24h."""
    try:
        with _client(timeout) as c:
            r = c.delete(f"/staging/{staging_key}")
        if r.status_code != 200:
            logger.warning(
                "video-worker /staging delete returned %d: %s",
                r.status_code, r.text[:300],
            )
    except httpx.HTTPError as exc:
        logger.warning("delete_staging unreachable: %s", exc)
