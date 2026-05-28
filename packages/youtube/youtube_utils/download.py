"""Download YouTube video and audio via yt-dlp."""

import logging
from pathlib import Path

import yt_dlp

from .exceptions import DownloadError

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.youtube.com/watch?v="


def _normalise_url(video_id_or_url: str) -> str:
    if video_id_or_url.startswith(("http://", "https://")):
        return video_id_or_url
    return f"{_BASE_URL}{video_id_or_url}"


def _run_download(url: str, opts: dict) -> Path:
    """Run yt-dlp and return the path to the downloaded file."""
    downloaded: list[str] = []

    class _Hook:
        def __call__(self, d: dict) -> None:
            if d["status"] == "finished":
                downloaded.append(d["filename"])

    opts["progress_hooks"] = [_Hook()]
    opts.setdefault("logger", logger)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as e:
        raise DownloadError(f"yt-dlp failed for {url}: {e}") from e

    if not downloaded:
        raise DownloadError(f"yt-dlp produced no output for {url}")

    # Post-processors may change the extension, so find the actual file.
    # The progress hook captures the pre-postprocessor filename.
    base = Path(downloaded[0])
    # Check if postprocessor renamed the file (e.g. .webm -> .mp3)
    if base.exists():
        return base
    # Look for files with the same stem in the same directory
    for candidate in base.parent.glob(f"{base.stem}.*"):
        return candidate

    raise DownloadError(f"Downloaded file not found at {base}")


def download_audio(
    video_id_or_url: str,
    output_dir: str = ".",
    format: str = "mp3",
) -> Path:
    """Download audio from a YouTube video.

    Args:
        video_id_or_url: YouTube video ID or full URL.
        output_dir: Directory to save the file.
        format: Audio format (mp3, m4a, wav, etc.). Requires ffmpeg.

    Returns:
        Path to the downloaded audio file.
    """
    url = _normalise_url(video_id_or_url)
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(Path(output_dir) / "%(title)s.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": format,
            },
        ],
    }
    return _run_download(url, opts)


def download_video(
    video_id_or_url: str,
    output_dir: str = ".",
    format: str = "mp4",
    quality: str = "best",
) -> Path:
    """Download video from YouTube.

    Args:
        video_id_or_url: YouTube video ID or full URL.
        output_dir: Directory to save the file.
        format: Video container format (mp4, mkv, webm).
        quality: Quality selector — "best", "worst", or a height like "720".

    Returns:
        Path to the downloaded video file.
    """
    url = _normalise_url(video_id_or_url)

    if quality == "best":
        fmt = "bestvideo+bestaudio/best"
    elif quality == "worst":
        fmt = "worstvideo+worstaudio/worst"
    else:
        fmt = f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"

    opts = {
        "format": fmt,
        "outtmpl": str(Path(output_dir) / "%(title)s.%(ext)s"),
        "merge_output_format": format,
    }
    return _run_download(url, opts)
