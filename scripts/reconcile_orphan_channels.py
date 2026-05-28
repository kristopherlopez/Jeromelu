"""One-off: reconcile orphan Source.channel_id for legacy ingested videos.

Strategy:
  1. Find Sources where channel_id IS NULL and source_type='youtube'.
  2. Recover channel external_id from SourceDocument.s3_key
     (path: youtube/{channel_external_id}/{video_id}.json).
  3. For sources without s3_key, call YouTube videos.list once per video.
  4. Map YouTube external channel id -> Channel.external_id, set Source.channel_id.

Usage (inside api container so DATABASE_URL/YOUTUBE_API_KEY are present):
    python reconcile_orphan_channels.py            # dry run, prints counts
    python reconcile_orphan_channels.py --apply    # writes the UPDATE

Designed to be piped over SSH:
    cat scripts/reconcile_orphan_channels.py | \
        ssh jeromelu-prod 'docker exec -i jeromelu-api python - [--apply]'
"""

import json
import os
import re
import sys
import urllib.request

from sqlalchemy import create_engine, text

DRY_RUN = "--apply" not in sys.argv

DB_URL = os.environ["DATABASE_URL"]
YT_KEY = os.environ.get("YOUTUBE_API_KEY")

S3_RE = re.compile(r"^youtube/([^/]+)/[A-Za-z0-9_-]{11}\.json$")
URL_VID_RE = re.compile(r"[?&]v=([A-Za-z0-9_-]{11})")


def yt_channel_for_video(video_id: str) -> str | None:
    if not YT_KEY:
        return None
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={YT_KEY}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.load(resp)
    items = data.get("items") or []
    if not items:
        return None
    return items[0].get("snippet", {}).get("channelId")


def main() -> None:
    engine = create_engine(DB_URL)
    with engine.begin() as conn:
        channel_rows = conn.execute(
            text("SELECT channel_id, external_id FROM channels WHERE external_id IS NOT NULL")
        ).all()
        channel_map = {ext: cid for cid, ext in channel_rows}
        print(f"Loaded {len(channel_map)} channels with external_id")

        orphan_rows = conn.execute(
            text("""
            SELECT s.source_id, s.canonical_url,
                   (SELECT sd.s3_key
                      FROM source_documents sd
                     WHERE sd.source_id = s.source_id
                       AND sd.s3_key IS NOT NULL
                     LIMIT 1) AS s3_key
              FROM sources s
             WHERE s.channel_id IS NULL
               AND s.source_type = 'youtube'
        """)
        ).all()
        print(f"Found {len(orphan_rows)} orphan youtube sources")

        from_s3: list[tuple] = []
        need_yt: list[tuple] = []
        no_video_id: list[tuple] = []
        for src_id, canonical_url, s3_key in orphan_rows:
            ext = None
            if s3_key:
                m = S3_RE.match(s3_key)
                if m:
                    ext = m.group(1)
            if ext:
                from_s3.append((src_id, ext, canonical_url))
            else:
                m = URL_VID_RE.search(canonical_url or "")
                if m:
                    need_yt.append((src_id, m.group(1), canonical_url))
                else:
                    no_video_id.append((src_id, canonical_url))

        print(f"  via s3_key:        {len(from_s3)}")
        print(f"  via youtube api:   {len(need_yt)}")
        print(f"  no video_id:       {len(no_video_id)}")

        yt_failed: list[tuple] = []
        for src_id, vid, url in need_yt:
            try:
                ext = yt_channel_for_video(vid)
            except Exception as e:
                print(f"    YT call failed for {vid}: {e}")
                ext = None
            if ext:
                from_s3.append((src_id, ext, url))
            else:
                yt_failed.append((src_id, vid, url))

        matched: list[tuple] = []
        unmatched: dict[str, list] = {}
        for src_id, ext, _url in from_s3:
            cid = channel_map.get(ext)
            if cid:
                matched.append((src_id, cid, ext))
            else:
                unmatched.setdefault(ext, []).append(src_id)

        print()
        print(f"Resolved: {len(matched)} sources have a matching Channel row")
        if unmatched:
            print(f"Unmatched external channel ids ({len(unmatched)} distinct):")
            for ext, ids in sorted(unmatched.items(), key=lambda x: -len(x[1])):
                print(f"  {ext}: {len(ids)} sources")
        if yt_failed:
            print(f"YouTube API returned no channel for {len(yt_failed)} videos")
        if no_video_id:
            print(f"Could not parse video_id for {len(no_video_id)} sources")

        if DRY_RUN:
            print("\n[DRY RUN] re-run with --apply to write")
            return

        for src_id, cid, _ in matched:
            conn.execute(
                text("UPDATE sources SET channel_id = :cid WHERE source_id = :sid"),
                {"cid": cid, "sid": src_id},
            )
        print(f"\n[APPLIED] Linked {len(matched)} sources")


if __name__ == "__main__":
    main()
