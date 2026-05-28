"""Sync avatar manifest with clip files on disk.

Scans services/web/public/avatar/ for .mp4 files, adds any missing clips
to manifest.json with defaults inferred from the filename.

Usage:
    python scripts/sync_manifest.py          # preview what would change
    python scripts/sync_manifest.py --write  # apply changes

Filename conventions:
    idle-1.mp4          -> category=idle,      mood=neutral,     loop=true,  priority=0
    confident-1.mp4     -> category=reaction,  mood=confident,   loop=false, priority=10
    glance-left.mp4     -> category=directional, mood=glance-left, loop=false, priority=5
    micro-blink.mp4     -> category=micro,     mood=micro-blink, loop=false, priority=0
"""

import json
import subprocess
import sys
from pathlib import Path

AVATAR_DIR = Path("services/web/public/avatar")
MANIFEST_PATH = AVATAR_DIR / "manifest.json"

# Maps filename prefix to (category, mood, loop, priority).
# Order matters — first match wins.
CATEGORY_RULES = {
    # Idle
    "idle": ("idle", "neutral", True, 0),
    "breathing": ("idle", "neutral", True, 0),
    # Reactions
    "greeting": ("reaction", "greeting", False, 10),
    "watching": ("reaction", "watching", False, 10),
    "confident": ("reaction", "confident", False, 10),
    "annoyed": ("reaction", "annoyed", False, 10),
    "celebrating": ("reaction", "celebrating", False, 10),
    "impatient": ("reaction", "impatient", False, 10),
    "engaged": ("reaction", "engaged", False, 10),
    # Directional
    "glance": ("directional", None, False, 5),  # mood from full stem
    # Micro
    "micro": ("micro", None, False, 0),  # mood from full stem
}


def get_duration_ms(clip_path: Path) -> int:
    """Get clip duration in milliseconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-show_entries",
        "format=duration",
        "-of",
        "csv=p=0",
        str(clip_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return int(float(result.stdout.strip()) * 1000)
    except Exception:
        pass
    return 5000  # fallback


def classify(stem: str) -> dict:
    """Infer category, mood, loop, and priority from a filename stem."""
    for prefix, (category, mood, loop, priority) in CATEGORY_RULES.items():
        if stem.startswith(prefix):
            if mood is None:
                mood = stem  # use full stem, e.g. "glance-left", "micro-blink"
            return {
                "category": category,
                "mood": mood,
                "loop": loop,
                "priority": priority,
            }
    # Unknown — default to reaction
    return {
        "category": "reaction",
        "mood": stem.split("-")[0] if "-" in stem else stem,
        "loop": False,
        "priority": 10,
    }


def main():
    write_mode = "--write" in sys.argv

    if not MANIFEST_PATH.exists():
        manifest = {"clips": []}
    else:
        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)

    existing_files = {clip["file"] for clip in manifest["clips"]}

    # Find mp4 files not yet in manifest
    mp4_files = sorted(AVATAR_DIR.glob("*.mp4"))
    new_clips = []

    for mp4 in mp4_files:
        if mp4.name in existing_files:
            continue

        stem = mp4.stem  # e.g. "confident-1", "glance-left", "micro-blink"
        info = classify(stem)
        duration = get_duration_ms(mp4)

        entry = {
            "id": stem,
            "file": mp4.name,
            "category": info["category"],
            "mood": info["mood"],
            "duration_ms": duration,
            "loop": info["loop"],
            "transitions_to": [],
            "priority": info["priority"],
        }
        new_clips.append(entry)

    if not new_clips:
        print("Manifest is up to date — no new clips found.")
        return

    print(f"Found {len(new_clips)} new clip(s):\n")
    for clip in new_clips:
        print(f"  {clip['file']}")
        print(
            f"    id={clip['id']}  category={clip['category']}  "
            f"mood={clip['mood']}  duration={clip['duration_ms']}ms  "
            f"loop={clip['loop']}  priority={clip['priority']}"
        )
        print()

    if write_mode:
        manifest["clips"].extend(new_clips)
        with open(MANIFEST_PATH, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"Added {len(new_clips)} clip(s) to {MANIFEST_PATH}")
    else:
        print("Dry run — pass --write to apply changes.")


if __name__ == "__main__":
    main()
