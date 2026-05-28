"""Generate avatar clips via Replicate video generation APIs.

Supports multiple models (default: Veo 3.1 Fast).

Usage:
    # Veo 3.1 (default)
    python scripts/video/generate_clip.py idle-2 \
        --prompt "Living portrait, natural idle animation, subtle breathing..."

    # Veo 3.1 with start/end frames
    python scripts/video/generate_clip.py idle-2 \
        --prompt "Living portrait, natural idle animation..." \
        --start-image assets/avatar/reference.png \
        --end-image assets/avatar/reference.png

    # Kling v3
    python scripts/video/generate_clip.py idle-2 \
        --model kling \
        --prompt "Living portrait, natural idle animation..." \
        --start-image assets/avatar/reference.png

    # With all options
    python scripts/video/generate_clip.py confident-1 \
        --prompt "Living portrait, person develops a subtle confident smirk..." \
        --start-image assets/avatar/reference.png \
        --category reaction --mood confident --duration 5 \
        --aspect-ratio 16:9 --priority 10

    # Skip post-processing (keep raw file only)
    python scripts/video/generate_clip.py idle-2 --prompt "..." --raw-only

    # Talking clip (keep audio)
    python scripts/video/generate_clip.py talking-confident-1 \
        --prompt "..." --category talking --mood confident --keep-audio
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AVATAR_DIR = REPO_ROOT / "services" / "web" / "public" / "avatar"
CLIPS_DIR = AVATAR_DIR / "clips"
MANIFEST_PATH = AVATAR_DIR / "manifest.json"
RAW_DIR = REPO_ROOT / "assets" / "avatar" / "raw"
TRIM_SCRIPT = REPO_ROOT / "scripts" / "video" / "trim_clip.py"

NEGATIVE_PROMPT = (
    "no camera shake, no zoom, no pan, no morphing, no warping, no distortion, "
    "no face deformation, no identity change, no fast motion, no text, no watermark"
)

# ---------------------------------------------------------------------------
# Model configurations
# ---------------------------------------------------------------------------

MODELS = {
    "veo": {
        "replicate_id": "google/veo-3.1-fast",
        "start_image_param": "image",
        "end_image_param": "last_frame",
        "durations": [4, 6, 8],
        "default_duration": 8,
        "aspect_ratios": ["16:9", "9:16"],
        "default_aspect_ratio": "16:9",
        "has_resolution": True,
        "default_resolution": "1080p",
        "has_mode": False,
        "default_audio": True,
    },
    "kling": {
        "replicate_id": "kwaivgi/kling-v3-video",
        "start_image_param": "start_image",
        "end_image_param": "end_image",
        "durations": [5, 10],
        "default_duration": 5,
        "aspect_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "21:9"],
        "default_aspect_ratio": "1:1",
        "has_resolution": False,
        "default_resolution": None,
        "has_mode": True,
        "default_audio": False,
    },
}

DEFAULT_MODEL = "veo"


def _open_image(path_str: str) -> open:
    """Validate and open an image file for upload."""
    img_path = Path(path_str)
    if not img_path.exists():
        print(f"Error: Image not found: {path_str}", file=sys.stderr)
        sys.exit(1)
    return open(img_path, "rb")


def generate_clip(
    prompt: str,
    model: str = DEFAULT_MODEL,
    start_image: str | None = None,
    end_image: str | None = None,
    duration: int | None = None,
    mode: str = "standard",
    aspect_ratio: str | None = None,
    resolution: str | None = None,
    negative_prompt: str = NEGATIVE_PROMPT,
    generate_audio: bool | None = None,
    seed: int | None = None,
) -> str:
    """Call Replicate API and return the output video URL."""
    import replicate

    cfg = MODELS[model]

    if duration is None:
        duration = cfg["default_duration"]
    if aspect_ratio is None:
        aspect_ratio = cfg["default_aspect_ratio"]
    if generate_audio is None:
        generate_audio = cfg["default_audio"]

    input_params = {
        "prompt": prompt,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "negative_prompt": negative_prompt,
        "generate_audio": generate_audio,
    }

    if cfg["has_resolution"]:
        input_params["resolution"] = resolution or cfg["default_resolution"]

    if cfg["has_mode"]:
        input_params["mode"] = mode

    if seed is not None:
        input_params["seed"] = seed

    if start_image:
        input_params[cfg["start_image_param"]] = _open_image(start_image)

    if end_image:
        if not start_image:
            print("Error: --end-image requires --start-image", file=sys.stderr)
            sys.exit(1)
        input_params[cfg["end_image_param"]] = _open_image(end_image)

    model_label = cfg["replicate_id"].split("/")[-1]
    print(f"Generating clip via {model_label} ({duration}s, {aspect_ratio})...")
    print(f"  Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    if start_image:
        print(f"  Start image: {start_image}")
    if end_image:
        print(f"  End image: {end_image}")

    start = time.time()
    output = replicate.run(cfg["replicate_id"], input=input_params)
    elapsed = time.time() - start

    print(f"  Generated in {elapsed:.0f}s")
    print(f"  URL: {output}")

    return str(output)


def download_video(url: str, dest: Path) -> Path:
    """Download video from URL to local path."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading to {dest}...")
    urllib.request.urlretrieve(url, str(dest))
    size_kb = dest.stat().st_size / 1024
    print(f"  Downloaded: {size_kb:.0f}KB")
    return dest


def post_process(raw_path: Path, output_path: Path, keep_audio: bool = False) -> Path:
    """Run trim_clip.py to crop, scale, and compress."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(TRIM_SCRIPT),
        str(raw_path),
        "--out",
        str(output_path),
    ]

    print(f"Post-processing: {raw_path.name} -> {output_path.name}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error during post-processing: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    if result.stdout:
        print(result.stdout.strip())

    return output_path


def update_manifest(
    clip_id: str,
    filename: str,
    category: str,
    mood: str,
    duration_ms: int,
    loop: bool,
    priority: int,
    keep_audio: bool = False,
    script_text: str | None = None,
) -> None:
    """Add or update a clip entry in manifest.json."""
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
    else:
        manifest = {"clips": []}

    entry = {
        "id": clip_id,
        "file": filename,
        "category": category,
        "mood": mood,
        "duration_ms": duration_ms,
        "loop": loop,
        "transitions_to": [],
        "priority": priority,
    }

    if script_text:
        entry["script"] = script_text

    # Replace existing entry or append
    existing_idx = next((i for i, c in enumerate(manifest["clips"]) if c["id"] == clip_id), None)
    if existing_idx is not None:
        manifest["clips"][existing_idx] = entry
        print(f"  Updated manifest entry: {clip_id}")
    else:
        manifest["clips"].append(entry)
        print(f"  Added manifest entry: {clip_id}")

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Generate avatar clips via Replicate video APIs")
    parser.add_argument("clip_id", help="Clip ID (e.g. idle-2, confident-1)")
    parser.add_argument("--prompt", required=True, help="Generation prompt")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        choices=list(MODELS.keys()),
        help=f"Video model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument("--start-image", default=None, help="First frame image for image-to-video mode")
    parser.add_argument("--end-image", default=None, help="Last frame image (requires --start-image)")
    parser.add_argument("--category", default=None, help="Clip category (idle/reaction/directional/micro/talking)")
    parser.add_argument("--mood", default=None, help="Mood tag (neutral/confident/annoyed/etc.)")
    parser.add_argument("--duration", type=int, default=None, help="Video duration in seconds")
    parser.add_argument("--mode", default="standard", choices=["standard", "pro"], help="Quality mode (Kling only)")
    parser.add_argument("--aspect-ratio", default=None, help="Aspect ratio")
    parser.add_argument("--resolution", default=None, choices=["720p", "1080p"], help="Resolution (Veo only)")
    parser.add_argument("--priority", type=int, default=None, help="Manifest priority (default: auto)")
    parser.add_argument("--loop", action="store_true", help="Mark clip as looping")
    parser.add_argument("--raw-only", action="store_true", help="Download raw file only, skip post-processing")
    parser.add_argument("--keep-audio", action="store_true", help="Keep audio track (for talking clips)")
    parser.add_argument("--no-manifest", action="store_true", help="Skip manifest update")
    parser.add_argument("--no-upload", action="store_true", help="Skip S3 upload")
    parser.add_argument("--generate-audio", action="store_true", default=None, help="Enable native audio generation")
    parser.add_argument("--no-audio", action="store_true", help="Disable native audio generation")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--script", default=None, help="Script text for talking clips")

    args = parser.parse_args()

    # Resolve audio flag
    if args.no_audio:
        args.generate_audio = False
    elif args.generate_audio is None:
        args.generate_audio = None  # let model default apply

    # Infer defaults from clip_id
    if args.category is None:
        if args.clip_id.startswith("idle-") or args.clip_id.startswith("breathing-"):
            args.category = "idle"
        elif args.clip_id.startswith("micro-"):
            args.category = "micro"
        elif args.clip_id.startswith("glance-"):
            args.category = "directional"
        elif args.clip_id.startswith("talking-"):
            args.category = "talking"
        else:
            args.category = "reaction"

    if args.mood is None:
        # Strip trailing -N variant number to get mood
        parts = args.clip_id.rsplit("-", 1)
        if len(parts) == 2 and parts[1].isdigit():
            args.mood = parts[0]
        else:
            args.mood = args.clip_id

    if args.priority is None:
        priority_map = {"idle": 0, "micro": 2, "directional": 5, "reaction": 10, "talking": 15}
        args.priority = priority_map.get(args.category, 0)

    if args.category == "idle":
        args.loop = True

    if args.category == "talking":
        args.keep_audio = True
        if args.generate_audio is None:
            args.generate_audio = True

    # Validate duration against model
    cfg = MODELS[args.model]
    duration = args.duration or cfg["default_duration"]
    if duration not in cfg["durations"]:
        print(
            f"Warning: duration {duration}s not supported by {args.model} "
            f"(valid: {cfg['durations']}). Using {cfg['default_duration']}s.",
            file=sys.stderr,
        )
        duration = cfg["default_duration"]
    args.duration = duration

    # Generate
    url = generate_clip(
        prompt=args.prompt,
        model=args.model,
        start_image=args.start_image,
        end_image=args.end_image,
        duration=args.duration,
        mode=args.mode,
        aspect_ratio=args.aspect_ratio,
        resolution=args.resolution,
        generate_audio=args.generate_audio,
        seed=args.seed,
    )

    # Download raw
    raw_path = RAW_DIR / f"{args.clip_id}_raw.mp4"
    download_video(url, raw_path)

    if args.raw_only:
        print(f"\nDone (raw only): {raw_path}")
        return

    # Post-process
    output_path = CLIPS_DIR / f"{args.clip_id}.mp4"
    post_process(raw_path, output_path, keep_audio=args.keep_audio)

    # Upload to S3
    if not args.no_upload:
        try:
            sys.path.insert(0, str(REPO_ROOT / "packages" / "shared"))
            from jeromelu_shared.s3 import get_asset_url, upload_asset

            s3_key = f"avatar/clips/{args.clip_id}.mp4"
            upload_asset(s3_key, str(output_path))
            asset_url = get_asset_url(s3_key)
            print(f"  Uploaded to S3: {asset_url}")
        except Exception as e:
            print(f"  S3 upload skipped: {e}", file=sys.stderr)

    # Update manifest
    if not args.no_manifest:
        update_manifest(
            clip_id=args.clip_id,
            filename=f"clips/{args.clip_id}.mp4",
            category=args.category,
            mood=args.mood,
            duration_ms=args.duration * 1000,
            loop=args.loop,
            priority=args.priority,
            keep_audio=args.keep_audio,
            script_text=args.script,
        )

    print(f"\nDone: {output_path}")
    print(f"Raw kept at: {raw_path}")


if __name__ == "__main__":
    main()
