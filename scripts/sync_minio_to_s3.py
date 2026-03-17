"""
Sync raw transcripts from local MinIO to production AWS S3.

Reads all objects from the MinIO raw-transcripts bucket and uploads them
to the production S3 bucket, skipping any that already exist in production.

Usage:
    python scripts/sync_minio_to_s3.py [--dry-run]
"""

import argparse
import sys

import boto3
from botocore.config import Config

# --- Configuration ---

MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
MINIO_BUCKET = "jeromelu-raw-transcripts"

PROD_REGION = "ap-southeast-2"
PROD_RAW_BUCKET = "jeromelu-raw-transcripts"
PROD_CLEAN_BUCKET = "jeromelu-clean-documents"


def get_minio_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
    )


def get_prod_client():
    return boto3.client("s3", region_name=PROD_REGION)


def list_all_keys(client, bucket, prefix=""):
    keys = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys


def sync_bucket(minio_client, prod_client, minio_bucket, prod_bucket, prefix="", dry_run=False):
    minio_keys = list_all_keys(minio_client, minio_bucket, prefix)
    prod_keys = set(list_all_keys(prod_client, prod_bucket, prefix))

    new_keys = [k for k in minio_keys if k not in prod_keys]
    skipped = len(minio_keys) - len(new_keys)

    print(f"\n  {minio_bucket} -> {prod_bucket}")
    print(f"  MinIO: {len(minio_keys)} objects | Prod: {len(prod_keys)} objects | New: {len(new_keys)} | Skipped: {skipped}")

    if dry_run:
        for key in new_keys:
            print(f"  [dry-run] would upload: {key}")
        return len(new_keys)

    uploaded = 0
    errors = 0
    for key in new_keys:
        try:
            obj = minio_client.get_object(Bucket=minio_bucket, Key=key)
            body = obj["Body"].read()
            prod_client.put_object(Bucket=prod_bucket, Key=key, Body=body)
            uploaded += 1
            print(f"  [{uploaded}/{len(new_keys)}] {key}")
        except Exception as e:
            errors += 1
            print(f"  [ERROR] {key}: {e}", file=sys.stderr)

    print(f"  Done: {uploaded} uploaded, {errors} errors")
    return uploaded


def main():
    parser = argparse.ArgumentParser(description="Sync MinIO transcripts to production S3")
    parser.add_argument("--dry-run", action="store_true", help="List what would be uploaded without uploading")
    args = parser.parse_args()

    if args.dry_run:
        print("=== DRY RUN ===")

    minio = get_minio_client()
    prod = get_prod_client()

    total = 0
    print("\nSyncing raw transcripts...")
    total += sync_bucket(minio, prod, MINIO_BUCKET, PROD_RAW_BUCKET, prefix="youtube/", dry_run=args.dry_run)

    # Also sync any clean documents if they exist in MinIO
    try:
        minio_clean_keys = list_all_keys(minio, "jeromelu-clean-documents")
        if minio_clean_keys:
            print("\nSyncing clean documents...")
            total += sync_bucket(minio, prod, "jeromelu-clean-documents", PROD_CLEAN_BUCKET, dry_run=args.dry_run)
    except Exception:
        pass  # Clean bucket may not exist in MinIO

    print(f"\n{'Would sync' if args.dry_run else 'Synced'} {total} total objects")


if __name__ == "__main__":
    main()
