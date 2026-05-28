"""Upload all processed avatar clips to S3.

Usage:
    python scripts/video/upload_clips_to_s3.py          # dry-run
    python scripts/video/upload_clips_to_s3.py --write  # upload
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "packages" / "shared"))

from jeromelu_shared.s3 import get_asset_url, upload_asset  # noqa: E402  # sys.path manipulation above must run first

CLIPS_DIR = REPO_ROOT / "services" / "web" / "public" / "avatar" / "clips"


def main():
    write = "--write" in sys.argv
    clips = sorted(CLIPS_DIR.glob("*.mp4"))

    if not clips:
        print("No clips found in", CLIPS_DIR)
        return

    print(f"Found {len(clips)} clips in {CLIPS_DIR}")
    if not write:
        print("Dry run — pass --write to upload\n")

    for clip in clips:
        s3_key = f"avatar/clips/{clip.name}"
        if write:
            upload_asset(s3_key, str(clip))
            url = get_asset_url(s3_key)
            print(f"  Uploaded: {clip.name} -> {url}")
        else:
            print(f"  Would upload: {clip.name} -> s3://jeromelu-public-assets/{s3_key}")

    print(f"\n{'Uploaded' if write else 'Would upload'} {len(clips)} clips.")


if __name__ == "__main__":
    main()
