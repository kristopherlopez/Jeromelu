"""Trim and prepare avatar video clips for the web.

Usage:
    python scripts/trim_clip.py assets/raw_clip.mp4 --out services/web/public/avatar/idle-2.mp4
    python scripts/trim_clip.py assets/raw_clip.mp4 --start 0.3 --end 4.0 --out ...

Features:
    - Strips audio
    - Crops to square (center crop)
    - Scales to 400x400
    - Compresses with H.264 CRF 28
    - Optional start/end trimming
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def get_video_info(path: str) -> dict:
    """Get video dimensions and duration via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            path,
        ],
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    video_stream = next(s for s in data["streams"] if s["codec_type"] == "video")
    return {
        "width": int(video_stream["width"]),
        "height": int(video_stream["height"]),
        "duration": float(data["format"]["duration"]),
    }


def trim_clip(
    input_path: str,
    output_path: str,
    start: float | None = None,
    end: float | None = None,
    size: int = 400,
    crf: int = 28,
) -> None:
    """Process a raw clip into a web-ready avatar video."""
    info = get_video_info(input_path)
    w, h = info["width"], info["height"]

    # Center crop to square
    square = min(w, h)
    crop_x = (w - square) // 2
    crop_y = (h - square) // 2

    vf = f"crop={square}:{square}:{crop_x}:{crop_y},scale={size}:{size}"

    cmd = ["ffmpeg", "-y"]

    if start is not None:
        cmd += ["-ss", str(start)]

    cmd += ["-i", input_path]

    if end is not None:
        if start is not None:
            cmd += ["-t", str(end - start)]
        else:
            cmd += ["-t", str(end)]

    cmd += [
        "-an",  # strip audio
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-crf",
        str(crf),
        "-preset",
        "slow",
        "-movflags",
        "+faststart",
        "-pix_fmt",
        "yuv420p",
        output_path,
    ]

    print(f"Processing: {input_path} -> {output_path}")
    print(f"  Crop: {square}x{square} from ({crop_x},{crop_y})")
    print(f"  Scale: {size}x{size}, CRF: {crf}")
    if start or end:
        print(f"  Trim: {start or 0:.1f}s - {end or info['duration']:.1f}s")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    # Report output size
    out_size = Path(output_path).stat().st_size / 1024
    print(f"  Output: {out_size:.0f}KB")


def main():
    parser = argparse.ArgumentParser(description="Trim and prepare avatar clips")
    parser.add_argument("input", help="Input video file")
    parser.add_argument("--out", required=True, help="Output file path")
    parser.add_argument("--start", type=float, default=None, help="Start time (seconds)")
    parser.add_argument("--end", type=float, default=None, help="End time (seconds)")
    parser.add_argument("--size", type=int, default=400, help="Output size (default: 400)")
    parser.add_argument("--crf", type=int, default=28, help="CRF quality (default: 28)")

    args = parser.parse_args()
    trim_clip(args.input, args.out, args.start, args.end, args.size, args.crf)


if __name__ == "__main__":
    main()
