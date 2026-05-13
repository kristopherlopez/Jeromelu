"""Shared helpers for walking scout/* archives.

Provides:
  - list_keys(prefix)           — paginated list of all keys under a prefix
  - read_json(key)              — fetch one archive as parsed JSON
  - read_json_concurrent(keys)  — fetch many archives in parallel (yields tuples)

Logs progress every N files so a long backfill is visible. All errors are
logged but the walk continues; the caller decides whether per-file failures
should abort.
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Iterator

from jeromelu_shared.config import settings
from jeromelu_shared.s3 import get_s3_client

logger = logging.getLogger(__name__)


def list_keys(prefix: str) -> list[str]:
    """List every object key under the given S3 prefix in the clean bucket."""
    client = get_s3_client()
    bucket = settings.s3_clean_bucket
    keys: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []) or []:
            keys.append(obj["Key"])
    return keys


def read_json(key: str) -> dict[str, Any] | list[Any]:
    """Fetch one archive object and parse as JSON."""
    client = get_s3_client()
    bucket = settings.s3_clean_bucket
    resp = client.get_object(Bucket=bucket, Key=key)
    return json.loads(resp["Body"].read())


def read_json_concurrent(
    keys: list[str],
    *,
    max_workers: int = 16,
    log_every: int = 100,
) -> Iterator[tuple[str, dict[str, Any] | list[Any] | None, Exception | None]]:
    """Fetch many archives concurrently, yielding (key, payload, error).

    On any per-key failure, payload=None and error=<exception>.
    Caller decides what to do with errors.
    """
    total = len(keys)
    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(read_json, k): k for k in keys}
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                payload = fut.result()
                yield key, payload, None
            except Exception as e:  # noqa: BLE001 — surface to caller
                yield key, None, e
            completed += 1
            if completed % log_every == 0 or completed == total:
                logger.info("  s3-walk: %d / %d archives read", completed, total)
