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
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
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

    s3_audio_bucket: str = "jeromelu-raw-audio"
    aws_default_region: str = "ap-southeast-2"
    staging_prefix: str = "staging/video"
    default_quality: str = "360"

    # LRU cache for persistent_video_s3_key downloads. Sized to fit a
    # handful of typical 360p episode mp4s (each ~135MB). Set to 0 to
    # disable the cache entirely.
    cache_dir: str = "/var/cache/video-worker"
    cache_max_bytes: int = 4 * 1024 * 1024 * 1024  # 4 GB


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


def _yt_dlp_section(
    video_id: str,
    output_dir: Path,
    ts: float,
    quality: str,
    pad_seconds: float = 3.0,
) -> tuple[Path, float]:
    """Pull only a small range around ``ts`` instead of the full video.

    yt-dlp's ``download_sections`` flag asks the server for just the
    matching segment, which collapses single-frame extraction time from
    "wait for the whole episode to download" to "wait for ~6 seconds of
    video". The output is keyframe-aligned and **rebased to start_time
    = 0** by yt-dlp's ffmpeg post-processor — so the caller has to
    subtract the requested section start before seeking. We return the
    section's start timestamp alongside the path so the caller can do
    that math.
    """
    start = max(0.0, ts - pad_seconds)
    end = ts + pad_seconds
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
        "download_ranges": yt_dlp.utils.download_range_func(None, [(start, end)]),
        "force_keyframes_at_cuts": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"yt-dlp section failed for {video_id}: {exc}",
        ) from exc

    candidates = list(output_dir.glob(f"{video_id}.*"))
    if not candidates:
        raise HTTPException(
            status_code=502,
            detail=f"yt-dlp section produced no output for {video_id}",
        )
    mp4s = [c for c in candidates if c.suffix == ".mp4"]
    chosen = mp4s[0] if mp4s else candidates[0]
    return chosen, start


# ---------------------------------------------------------------------------
# Persistent-mp4 LRU disk cache
# ---------------------------------------------------------------------------

# In-process lock — the worker is uvicorn-single-process, but
# /extract-frame is sync-in-threadpool, so two reassigns racing on the
# same key shouldn't both trigger the S3 download.
_cache_lock = threading.Lock()


def _cache_path(s3_key: str) -> Path:
    """Map an S3 key to a flat cache filename. Slashes become ``__`` so the
    cache directory stays one level deep — easier to inspect, and avoids
    creating per-channel subdirs that complicate eviction."""
    safe = s3_key.replace("/", "__")
    return Path(settings.cache_dir) / safe


def _cache_evict_to_fit(needed_bytes: int) -> None:
    """LRU by access time. Walks the cache dir, evicts oldest first until
    ``cache_max_bytes - needed_bytes`` worth of headroom exists. Cheap —
    runs only on miss, only over a flat directory of a few large files."""
    cache = Path(settings.cache_dir)
    if not cache.exists():
        return
    files = [(p, p.stat()) for p in cache.iterdir() if p.is_file()]
    total = sum(st.st_size for _, st in files)
    target = max(0, settings.cache_max_bytes - needed_bytes)
    if total <= target:
        return
    files.sort(key=lambda x: x[1].st_atime)  # oldest access first
    for path, st in files:
        if total <= target:
            break
        try:
            path.unlink()
            total -= st.st_size
            logger.info("Evicted %s (%.1f MB)", path.name, st.st_size / (1024 * 1024))
        except OSError as exc:
            logger.warning("eviction failed for %s: %s", path, exc)


def _cached_s3_download(s3_key: str) -> Path:
    """Return a local path holding the mp4 for ``s3_key`` — using the
    cache if present, populating it on miss. Touches mtime/atime on hit
    so LRU sees it as recent."""
    if settings.cache_max_bytes <= 0:
        # Cache disabled — fall through to a tempfile each call.
        tmp = Path(tempfile.mkdtemp(prefix="video-worker-nocache-"))
        path = tmp / "video.mp4"
        _s3().download_file(settings.s3_audio_bucket, s3_key, str(path))
        return path

    Path(settings.cache_dir).mkdir(parents=True, exist_ok=True)
    target = _cache_path(s3_key)

    with _cache_lock:
        if target.exists():
            os.utime(target, None)  # bump atime for LRU
            logger.info("cache hit %s", s3_key)
            return target

        # Miss. Probe size first so eviction can be sized correctly.
        head = _s3().head_object(Bucket=settings.s3_audio_bucket, Key=s3_key)
        size = int(head["ContentLength"])
        logger.info("cache miss %s (%.1f MB) — downloading", s3_key, size / (1024 * 1024))
        _cache_evict_to_fit(size)

        # Download to a sibling tmp file then atomic-rename so a crash
        # mid-download doesn't poison the cache with a half-file.
        tmp = target.with_suffix(target.suffix + ".tmp")
        _s3().download_file(settings.s3_audio_bucket, s3_key, str(tmp))
        tmp.rename(target)
        return target


def _ffmpeg_frame(
    video_path: Path,
    ts: float,
    dest: Path,
    bbox: tuple[float, float, float, float] | None = None,
) -> None:
    """Single JPEG at ``ts``. Raises 502 on ffmpeg failure.

    ``bbox`` is the optional crop in source pixels: ``(x1, y1, x2, y2)``.
    When supplied, ffmpeg crops the frame before encoding the JPEG —
    used by the face-gallery thumbnails to avoid sending full frames
    over the wire just to discard everything outside a face. Out-of-
    bounds bboxes are clamped by the ffmpeg crop filter.
    """
    if shutil.which("ffmpeg") is None:
        raise HTTPException(status_code=500, detail="ffmpeg not on PATH")
    cmd = [
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
        # Force full-range JPEG colorspace. Without this, the mjpeg
        # encoder rejects the input with "Could not open encoder /
        # incorrect parameters" on YouTube clips whose YUV is non-full
        # range — a long-standing ffmpeg behaviour, not specific to our
        # pipeline.
        "-pix_fmt",
        "yuvj420p",
    ]
    if bbox is not None:
        x1, y1, x2, y2 = bbox
        w = max(1, round(x2 - x1))
        h = max(1, round(y2 - y1))
        x = max(0, round(x1))
        y = max(0, round(y1))
        cmd += ["-vf", f"crop={w}:{h}:{x}:{y}"]
    cmd.append(str(dest))
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        # Tail the stderr instead of head — ffmpeg dumps its build banner
        # first and the actual error sits at the bottom of the dump.
        err = proc.stderr.decode("utf-8", errors="replace")
        tail = err[-1500:] if len(err) > 1500 else err
        raise HTTPException(
            status_code=502,
            detail=f"ffmpeg frame extraction failed at ts={ts}: ...{tail}",
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
            settings.s3_audio_bucket,
            staging_key,
            size / (1024 * 1024),
            video_id,
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
    prefer_section: bool = Field(
        default=False,
        description=(
            "When true and canonical_url is set, yt-dlp only a few seconds "
            "around ts instead of the full file. Drops single-frame "
            "extraction from ~30s to ~3s — used by reassign."
        ),
    )
    bbox: tuple[float, float, float, float] | None = Field(
        default=None,
        description=(
            "Optional crop in source pixels (x1, y1, x2, y2). When set, "
            "ffmpeg crops the frame before encoding — keeps face-gallery "
            "thumbnail bytes small."
        ),
    )


@app.post("/extract-frame")
def extract_frame(body: ExtractFrameRequest) -> Response:
    """Pull (or download) a video, dump one JPEG at ``ts``, return the bytes.

    Acquisition modes (chosen in order):
      - ``prefer_section`` + ``canonical_url``: yt-dlp a ~6s slice around
        ``ts``. Fast cold-start, no S3 hit at all.
      - ``persistent_video_s3_key``: fetch the mp4 from S3, populating
        the LRU disk cache so subsequent clicks on the same source are
        ~instant. No yt-dlp.
      - ``canonical_url``: yt-dlp the full file (legacy fallback).

    Returns image/jpeg bytes inline.
    """
    if not body.canonical_url and not body.persistent_video_s3_key:
        raise HTTPException(
            status_code=400,
            detail="Supply either canonical_url or persistent_video_s3_key",
        )

    quality = body.quality or settings.default_quality

    with tempfile.TemporaryDirectory(prefix="video-worker-frame-") as tmp:
        tmp_path = Path(tmp)
        # ts inside the resolved video file. The section path strips
        # the start of the original video off, so the requested ts has
        # to be rebased; the other paths preserve the original timeline.
        seek_ts = body.ts
        if body.prefer_section and body.canonical_url:
            video_id = _video_id_from_url(body.canonical_url)
            video_path, section_start = _yt_dlp_section(video_id, tmp_path, body.ts, quality)
            seek_ts = max(0.0, body.ts - section_start)
        elif body.persistent_video_s3_key:
            video_path = _cached_s3_download(body.persistent_video_s3_key)
        else:
            video_id = _video_id_from_url(body.canonical_url)
            video_path = _yt_dlp_low_res(video_id, tmp_path, quality)

        frame_path = tmp_path / "frame.jpg"
        _ffmpeg_frame(video_path, seek_ts, frame_path, bbox=body.bbox)
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
