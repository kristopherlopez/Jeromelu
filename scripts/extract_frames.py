"""Extract the first and last frames from every video in assets/."""

import subprocess
import sys
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
FRAMES_DIR = ASSETS_DIR / "frames"
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def get_duration(video: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video),
        ],
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def extract_frame(video: Path, timestamp: str, output: Path):
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss", timestamp,
            "-i", str(video),
            "-frames:v", "1",
            "-q:v", "2",
            str(output),
        ],
        capture_output=True,
    )


def main():
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    videos = [f for f in ASSETS_DIR.iterdir() if f.suffix.lower() in VIDEO_EXTS]
    if not videos:
        print("No videos found in assets/")
        sys.exit(0)

    for video in sorted(videos):
        stem = video.stem
        print(f"Processing {video.name}...")

        # First frame
        first_out = FRAMES_DIR / f"{stem}_first.jpg"
        extract_frame(video, "0", first_out)

        # Last frame
        duration = get_duration(video)
        last_ts = str(max(0, duration - 0.1))
        last_out = FRAMES_DIR / f"{stem}_last.jpg"
        extract_frame(video, last_ts, last_out)

        print(f"  -> {first_out.name}, {last_out.name}")

    print("Done.")


if __name__ == "__main__":
    main()
