"""Shared S3 raw-snapshot archive for all Miner pipelines (D10).

Every Miner pipeline calls `archive_response(...)` after a successful upstream
fetch but before any DB writes. The raw response is persisted to S3 with a
deterministic, idempotent key so:
  - re-extraction is free (read back from S3, no re-fetch)
  - drift detection has a real artefact to diff against
  - historical backfill writes immutable archive once

Per D13, S3 is the durable capture; the DB is downstream and re-derivable.

Path convention (per D10):
  s3://{s3_clean_bucket}/miner/{source}/{pipeline}/{identity_path}.json

S3 write failures do NOT crash the pipeline. The DB extraction path is the
fallback; we log loudly and record the failure in the pipeline's audit row
so a retry / backfill knows to re-archive.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from jeromelu_shared.config import settings

logger = logging.getLogger(__name__)


MINER_S3_PREFIX = "miner"


def build_key(source: str, pipeline: str, identity_path: str) -> str:
    """Compose the S3 key for a Miner snapshot.

    Args:
        source: e.g. "nrlcom", "supercoach", "nrlsupercoachstats"
        pipeline: e.g. "draw", "match-centre", "classic/players-cf"
        identity_path: the call-identity portion ending in `.json`,
            e.g. "111/2026/round-07.json", "2026/20260512.json"

    Returns:
        Full S3 key (no leading slash).
    """
    return f"{MINER_S3_PREFIX}/{source}/{pipeline}/{identity_path}"


def archive_response(
    *,
    source: str,
    pipeline: str,
    identity_path: str,
    payload: dict[str, Any] | list[Any] | str | bytes,
) -> str | None:
    """Persist the raw upstream response to S3 under the Miner prefix.

    Returns the S3 key on success, None on failure. Caller writes the
    returned key into `agent_runs.detail_json.s3_archive_key` so the
    audit trail names the artefact.

    Failures (network, credentials, bucket missing) are logged at ERROR
    but swallowed — the upstream DB path proceeds. The audit row
    should set `detail_json.s3_archive_failed=true` when this returns
    None so a follow-up sweep can re-archive.
    """
    key = build_key(source, pipeline, identity_path)
    bucket = settings.s3_clean_bucket

    try:
        # Lazy import — keeps the test import path light when boto3 isn't
        # configured (the audit_audit module already does this).
        from jeromelu_shared.s3 import get_s3_client
    except Exception:
        logger.exception("miner.common.archive: failed to import get_s3_client")
        return None

    if isinstance(payload, (dict, list)):
        body: bytes = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    elif isinstance(payload, str):
        body = payload.encode("utf-8")
    else:
        body = payload

    try:
        client = get_s3_client()
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
        )
    except Exception:
        logger.exception(
            "miner.common.archive: put_object failed bucket=%s key=%s",
            bucket,
            key,
        )
        return None

    logger.info(
        "miner.common.archive: wrote %d bytes to s3://%s/%s",
        len(body),
        bucket,
        key,
    )
    return key


__all__ = ["MINER_S3_PREFIX", "archive_response", "build_key"]
