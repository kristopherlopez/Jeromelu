"""Re-import all sources from the jeromelu-raw-transcripts S3 bucket.

Wipes sources and dependent tables, then re-creates Source + SourceDocument +
SourceChunk rows for every JSON object in s3://jeromelu-raw-transcripts/youtube/.
"""

import hashlib
import json
import logging
import sys
from datetime import datetime, timezone

from sqlalchemy import text

from jeromelu_shared.config import settings
from jeromelu_shared.db import (
    Channel,
    SessionLocal,
    Source,
    SourceChunk,
    SourceDocument,
)
from jeromelu_shared.s3 import get_s3_client
from scripts.extraction.chunker import chunk_segments

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)


def list_s3_objects(client, bucket: str, prefix: str = "youtube/") -> list[str]:
    """List all object keys under the given prefix."""
    keys: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".json"):
                keys.append(obj["Key"])
    return keys


def truncate_tables(session) -> None:
    """Truncate dependent tables in FK-safe order."""
    tables = [
        "claim_chunks",
        "claims",
        "quotes",
        "source_chunks",
        "source_documents",
        "sources",
    ]
    for table in tables:
        session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
    session.commit()
    logger.info("Truncated tables: %s", ", ".join(tables))


def import_object(session, client, bucket: str, key: str, channel_cache: dict) -> bool:
    """Download one S3 JSON object and insert Source + Document + Chunks.

    Returns True on success, False on skip/error.
    """
    try:
        resp = client.get_object(Bucket=bucket, Key=key)
        data = json.loads(resp["Body"].read())
    except Exception:
        logger.exception("Failed to download/parse %s", key)
        return False

    video_id = data.get("video_id")
    channel_ext_id = data.get("channel_id")
    title = data.get("title", "Unknown")
    published_at = data.get("published_at")
    segments = data.get("segments", [])

    if not video_id:
        logger.warning("Skipping %s — no video_id", key)
        return False

    # Resolve channel
    channel_id_fk = None
    creator_name = None
    if channel_ext_id:
        if channel_ext_id not in channel_cache:
            ch = session.query(Channel).filter(
                Channel.external_id == channel_ext_id
            ).first()
            channel_cache[channel_ext_id] = ch
        ch = channel_cache[channel_ext_id]
        if ch:
            channel_id_fk = ch.channel_id
            creator_name = ch.name

    # Build plain text
    plain_text = " ".join(seg["text"] for seg in segments)
    checksum = hashlib.sha256(plain_text.encode()).hexdigest()

    # Parse published_at
    pub_dt = None
    if published_at:
        try:
            pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    canonical_url = f"https://youtube.com/watch?v={video_id}"

    # Source
    source = Source(
        channel_id=channel_id_fk,
        source_type="youtube",
        title=title,
        creator_name=creator_name,
        canonical_url=canonical_url,
        approved_flag=True,
        ingestion_status="completed",
        published_at=pub_dt,
        ingested_at=datetime.now(timezone.utc),
    )
    session.add(source)
    session.flush()

    # SourceDocument
    chunk_dicts = chunk_segments(segments)
    document = SourceDocument(
        source_id=source.source_id,
        s3_key=key,
        raw_text=plain_text,
        transcript_available=True,
        language="en",
        checksum=checksum,
        chunk_count=len(chunk_dicts),
    )
    session.add(document)
    session.flush()

    # SourceChunks
    for cd in chunk_dicts:
        chunk = SourceChunk(
            document_id=document.document_id,
            chunk_index=cd["chunk_index"],
            raw_text=cd["raw_text"],
            clean_text=cd.get("clean_text"),
            start_offset=cd.get("start_offset"),
            end_offset=cd.get("end_offset"),
            start_ts=cd.get("start_ts"),
            end_ts=cd.get("end_ts"),
        )
        session.add(chunk)

    return True


def main() -> None:
    client = get_s3_client()
    bucket = settings.s3_raw_bucket

    logger.info("Listing objects in s3://%s/youtube/ ...", bucket)
    keys = list_s3_objects(client, bucket)
    logger.info("Found %d JSON objects", len(keys))

    if not keys:
        logger.warning("No objects found — nothing to import.")
        return

    session = SessionLocal()
    try:
        logger.info("Truncating dependent tables ...")
        truncate_tables(session)

        channel_cache: dict = {}
        imported = 0
        skipped = 0

        for i, key in enumerate(keys, 1):
            ok = import_object(session, client, bucket, key, channel_cache)
            if ok:
                imported += 1
            else:
                skipped += 1

            if i % 25 == 0:
                session.commit()
                logger.info("Progress: %d/%d (imported=%d, skipped=%d)", i, len(keys), imported, skipped)

        session.commit()
        logger.info("Done. Imported %d sources, skipped %d.", imported, skipped)

    except Exception:
        session.rollback()
        logger.exception("Import failed — rolled back.")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
