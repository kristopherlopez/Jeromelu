"""
Bulk-ingest all raw transcripts from production S3 via the admin API.

Lists all objects in the raw-transcripts S3 bucket, extracts channel_id
and video_id from the key, and calls POST /api/admin/ingest-raw for each.

Usage:
    python scripts/bulk_ingest_raw.py [--dry-run] [--api-url URL] [--admin-key KEY]
"""

import argparse
import json
import sys
import time

import boto3
import requests

PROD_API = "https://api.jeromelu.ai"
PROD_RAW_BUCKET = "jeromelu-raw-transcripts"
REGION = "ap-southeast-2"


def list_raw_transcripts():
    client = boto3.client("s3", region_name=REGION)
    paginator = client.get_paginator("list_objects_v2")
    transcripts = []
    for page in paginator.paginate(Bucket=PROD_RAW_BUCKET, Prefix="youtube/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            # youtube/{channel_id}/{video_id}.json
            parts = key.split("/")
            if len(parts) == 3 and parts[2].endswith(".json"):
                channel_id = parts[1]
                video_id = parts[2].replace(".json", "")
                transcripts.append((channel_id, video_id))
    return transcripts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--api-url", default=PROD_API)
    parser.add_argument("--admin-key", required=True)
    args = parser.parse_args()

    transcripts = list_raw_transcripts()
    print(f"Found {len(transcripts)} raw transcripts in S3\n")

    if args.dry_run:
        for ch, vid in transcripts:
            print(f"  [dry-run] would ingest: {ch}/{vid}")
        return

    success = 0
    skipped = 0
    errors = 0

    for i, (channel_id, video_id) in enumerate(transcripts, 1):
        try:
            resp = requests.post(
                f"{args.api_url}/api/admin/ingest-raw",
                json={"video_id": video_id, "channel_id": channel_id},
                headers={"X-Admin-Key": args.admin_key},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("skipped"):
                    skipped += 1
                    print(f"  [{i}/{len(transcripts)}] SKIP {video_id}")
                else:
                    success += 1
                    chunks = data.get("chunks_created", 0)
                    print(f"  [{i}/{len(transcripts)}] OK   {video_id} ({chunks} chunks)")
            else:
                errors += 1
                detail = resp.json().get("detail", resp.text)[:100]
                print(f"  [{i}/{len(transcripts)}] ERR  {video_id}: {resp.status_code} {detail}", file=sys.stderr)
        except Exception as e:
            errors += 1
            print(f"  [{i}/{len(transcripts)}] ERR  {video_id}: {e}", file=sys.stderr)

    print(f"\nDone: {success} ingested, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    main()
