"""Video worker — yt-dlp + ffmpeg utility surface.

Lives next to the API in docker-compose.prod.yml on an internal network only
(no host port bind, no Caddy route). The API talks to it as
``http://video-worker:8000`` via the docker DNS name.

Why a separate service: per ``feedback_api_container_lean.md``, heavy /
native deps (here yt-dlp + ffmpeg) stay out of the API container. The API
keeps a thin HTTP client (``app/analyst/video_staging.py``); the actual
download + frame extraction runs here.

Endpoints:

  GET  /health                  — liveness check
  POST /stage-video             — yt-dlp → S3 staging key
  POST /extract-frame           — yt-dlp + ffmpeg → JPG bytes
  DELETE /staging/{key:path}    — explicit S3 cleanup (S3 lifecycle is the
                                  belt-and-braces backstop)

The worker has no DB, no auth, and no public exposure. Trust boundary is
the docker network — the API is the only client.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator
from uuid import uuid4

import boto3
import yt_dlp
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
)
logger = logging.getLogger("video-worker")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    """Worker config. Same names as the API where they overlap so a
    single ``/opt/jeromelu/.env`` covers both."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    s3_audio_bucket: str = "jeromelu-raw-transcripts"
    aws_default_region: str = "ap-southeast-2"
    staging_prefix: str = "staging/video"
    default_quality: str = "360"


settings = Settings()


def _s3():
    return boto3.client("s3", region_name=settings.aws_default_region)


# ---------------------------------------------------------------------------
# yt-dlp / ffmpeg primitives
# ---------------------------------------------------------------------------

_VIDEO_ID_RE = re.compile(r"(?:v=|/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})")


def _video_id_from_url(url: str) -> str:
    m = _VIDEO_ID_RE.search(url)
    if not m:
        raise HTTPException(
            status_code=400,
            detail=f"could not parse YouTube video id from {url!r}",
        )
    return m.group(1)


def _yt_dlp_low_res(video_id: str, output_dir: Path, quality: str) -> Path:
    """Same selector + post-conditions as the original
    ``app/analyst/video_staging.py:_yt_dlp_low_res_video``. Kept identical
    so the GPU pipeline sees the same pixel density it was tuned against."""
    fmt = (
        f"best[ext=mp4][vcodec!*=none][acodec!*=none][height<={quality}]"
        f"/best[vcodec!*=none][acodec!*=none][height<={quality}]"
        f"/worst[vcodec!*=none][acodec!*=none]"
    )
    opts = {
        "format": fmt,
        "outtmpl": str(output_dir / f"{video_id}.%(ext)s"),
        "logger": logger,
        "quiet": True,
        "noprogress": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"yt-dlp failed for {video_id}: {exc}",
        ) from exc

    candidates = list(output_dir.glob(f"{video_id}.*"))
    if not candidates:
        raise HTTPException(
            status_code=502,
            detail=f"yt-dlp produced no output for {video_id}",
        )
    mp4s = [c for c in candidates if c.suffix == ".mp4"]
    return mp4s[0] if mp4s else candidates[0]


def _ffmpeg_frame(video_path: Path, ts: float, dest: Path) -> None:
    """Single JPEG at ``ts``. Raises 502 on ffmpeg failure."""
    if shutil.which("ffmpeg") is None:
        raise HTTPException(status_code=500, detail="ffmpeg not on PATH")
    proc = subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", f"{ts:.3f}",
            "-i", str(video_path),
            "-frames:v", "1",
            "-q:v", "2",
            str(dest),
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace")[:500]
        raise HTTPException(
            status_code=502,
            detail=f"ffmpeg frame extraction failed at ts={ts}: {err}",
        )


# ---------------------------------------------------------------------------
# FastAPI surface
# ---------------------------------------------------------------------------

app = FastAPI(title="video-worker", version="1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class StageVideoRequest(BaseModel):
    canonical_url: str = Field(..., description="YouTube watch URL")
    quality: str | None = Field(default=None, description="Max height; defaults to worker's DEFAULT_QUALITY")


class StageVideoResponse(BaseModel):
    staging_key: str
    bucket: str
    size_bytes: int


@app.post("/stage-video", response_model=StageVideoResponse)
def stage_video(body: StageVideoRequest) -> StageVideoResponse:
    """Pull a YouTube video, upload to a per-request staging key in S3.

    Caller is responsible for ``DELETE /staging/{key}`` once done. The
    ``staging/video/`` S3 prefix has a 24h lifecycle rule as the backstop
    if the caller crashes or forgets.
    """
    video_id = _video_id_from_url(body.canonical_url)
    quality = body.quality or settings.default_quality
    request_id = uuid4().hex
    staging_key = f"{settings.staging_prefix}/{request_id}.mp4"

    with tempfile.TemporaryDirectory(prefix="video-worker-stage-") as tmp:
        local = _yt_dlp_low_res(video_id, Path(tmp), quality)
        size = local.stat().st_size
        _s3().upload_file(
            str(local),
            settings.s3_audio_bucket,
            staging_key,
            ExtraArgs={"ContentType": "video/mp4"},
        )
        logger.info(
            "Staged video s3://%s/%s (%.1f MB) for %s",
            settings.s3_audio_bucket, staging_key, size / (1024 * 1024), video_id,
        )

    return StageVideoResponse(
        staging_key=staging_key,
        bucket=settings.s3_audio_bucket,
        size_bytes=size,
    )


class ExtractFrameRequest(BaseModel):
    canonical_url: str | None = Field(
        default=None,
        description="YouTube watch URL — supply this OR persistent_video_s3_key",
    )
    persistent_video_s3_key: str | None = Field(
        default=None,
        description="S3 key for an already-staged mp4 — fast path that skips yt-dlp",
    )
    ts: float = Field(..., ge=0, description="Frame timestamp in seconds")
    quality: str | None = Field(default=None)


@app.post("/extract-frame")
def extract_frame(body: ExtractFrameRequest) -> Response:
    """Pull (or download) a video, dump one JPEG at ``ts``, return the bytes.

    Two acquisition modes:
      - ``persistent_video_s3_key`` set: fetch the mp4 from S3 (no yt-dlp).
      - ``canonical_url`` set: yt-dlp on the fly. Cleaned up on exit.

    Returns image/jpeg bytes inline. Caller writes them to disk if needed.
    """
    if not body.canonical_url and not body.persistent_video_s3_key:
        raise HTTPException(
            status_code=400,
            detail="Supply either canonical_url or persistent_video_s3_key",
        )

    quality = body.quality or settings.default_quality

    with tempfile.TemporaryDirectory(prefix="video-worker-frame-") as tmp:
        tmp_path = Path(tmp)
        if body.persistent_video_s3_key:
            video_path = tmp_path / "video.mp4"
            _s3().download_file(
                settings.s3_audio_bucket,
                body.persistent_video_s3_key,
                str(video_path),
            )
        else:
            video_id = _video_id_from_url(body.canonical_url)
            video_path = _yt_dlp_low_res(video_id, tmp_path, quality)

        frame_path = tmp_path / "frame.jpg"
        _ffmpeg_frame(video_path, body.ts, frame_path)
        return Response(
            content=frame_path.read_bytes(),
            media_type="image/jpeg",
        )


@app.delete("/staging/{key:path}")
def delete_staging(key: str) -> dict[str, str]:
    """Best-effort delete of a staging key. The 24h S3 lifecycle is the
    backstop — we log on failure rather than raising 5xx."""
    if not key.startswith(f"{settings.staging_prefix}/"):
        raise HTTPException(
            status_code=400,
            detail=f"key must be under {settings.staging_prefix}/",
        )
    try:
        _s3().delete_object(Bucket=settings.s3_audio_bucket, Key=key)
        logger.info("Deleted s3://%s/%s", settings.s3_audio_bucket, key)
    except Exception as exc:
        logger.warning("delete_staging failed for %s: %s", key, exc)
        return {"status": "warn", "detail": str(exc)}
    return {"status": "ok"}
