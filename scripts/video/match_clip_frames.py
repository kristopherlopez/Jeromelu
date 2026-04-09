"""Auto-detect valid transitions between avatar clips by comparing boundary frames.

Usage:
    python scripts/match_clip_frames.py

Reads:  services/web/public/avatar/manifest.json
Writes: services/web/public/avatar/manifest.json (updates transitions_to)
        assets/avatar/frames/ (extracted boundary frames)

Requires: pip install imagehash Pillow
"""

import json
import subprocess
import sys
from pathlib import Path

try:
    import imagehash
    from PIL import Image
except ImportError:
    print("Install dependencies: pip install imagehash Pillow", file=sys.stderr)
    sys.exit(1)


AVATAR_DIR = Path("services/web/public/avatar")
MANIFEST_PATH = AVATAR_DIR / "manifest.json"
FRAMES_DIR = Path("assets/avatar/frames")

# Maximum perceptual hash distance to consider a match.
# Lower = stricter matching. 8 is a reasonable default.
HASH_THRESHOLD = 8


def extract_frame(clip_path: Path, output_path: Path, position: str = "first") -> bool:
    """Extract first or last frame from a clip."""
    if position == "first":
        cmd = [
            "ffmpeg", "-y", "-i", str(clip_path),
            "-vf", "select=eq(n\\,0)",
            "-frames:v", "1",
            str(output_path),
        ]
    else:  # last
        cmd = [
            "ffmpeg", "-y", "-sseof", "-0.04",
            "-i", str(clip_path),
            "-frames:v", "1",
            str(output_path),
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def compute_hash(image_path: Path) -> imagehash.ImageHash | None:
    """Compute perceptual hash of an image."""
    try:
        img = Image.open(image_path)
        return imagehash.phash(img)
    except Exception:
        return None


def main():
    if not MANIFEST_PATH.exists():
        print(f"Manifest not found: {MANIFEST_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    clips = manifest["clips"]
    if len(clips) < 2:
        print("Need at least 2 clips to match. Skipping.")
        return

    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Extract boundary frames
    print(f"Extracting frames from {len(clips)} clips...")
    frame_data: dict[str, dict] = {}

    for clip in clips:
        clip_path = AVATAR_DIR / clip["file"]
        if not clip_path.exists():
            print(f"  Skipping {clip['id']}: file not found ({clip_path})")
            continue

        first_path = FRAMES_DIR / f"{clip['id']}_first.png"
        last_path = FRAMES_DIR / f"{clip['id']}_last.png"

        ok_first = extract_frame(clip_path, first_path, "first")
        ok_last = extract_frame(clip_path, last_path, "last")

        if ok_first and ok_last:
            first_hash = compute_hash(first_path)
            last_hash = compute_hash(last_path)
            frame_data[clip["id"]] = {
                "first_hash": first_hash,
                "last_hash": last_hash,
            }
            print(f"  {clip['id']}: extracted ✓")
        else:
            print(f"  {clip['id']}: extraction failed")

    # Step 2: Compare end frames to start frames
    print(f"\nComparing frames (threshold: {HASH_THRESHOLD})...")
    matches: dict[str, list[str]] = {clip_id: [] for clip_id in frame_data}

    for clip_a_id, data_a in frame_data.items():
        if data_a["last_hash"] is None:
            continue
        for clip_b_id, data_b in frame_data.items():
            if clip_a_id == clip_b_id:
                continue
            if data_b["first_hash"] is None:
                continue

            distance = data_a["last_hash"] - data_b["first_hash"]
            if distance <= HASH_THRESHOLD:
                matches[clip_a_id].append(clip_b_id)
                print(f"  {clip_a_id} → {clip_b_id} (distance: {distance}) ✓")

    # Step 3: Update manifest
    updated = 0
    for clip in clips:
        if clip["id"] in matches:
            # Respect manual overrides
            if "transitions_override" in clip:
                continue
            new_transitions = matches[clip["id"]]
            if set(new_transitions) != set(clip.get("transitions_to", [])):
                clip["transitions_to"] = new_transitions
                updated += 1

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nDone. Updated transitions for {updated} clip(s).")
    print(f"Manifest written to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
