"""Indexing activity — write Source and SourceDocument records to DB."""

import logging
from datetime import datetime, timezone

from temporalio import activity

from jeromelu_shared.db import Channel, SessionLocal, Source, SourceDocument

logger = logging.getLogger(__name__)


def _parse_published_at(published_at: str) -> datetime | None:
    """Parse published_at string to datetime, return None on failure."""
    if not published_at:
        return None
    try:
        return datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _checksum_exists(session, checksum: str) -> bool:
    """Check if a document with this checksum already exists (dedup)."""
    return session.query(SourceDocument.document_id).filter(
        SourceDocument.checksum == checksum
    ).first() is not None


@activity.defn
async def index_document(video: dict, collection_result: dict) -> dict:
    """Write Source + SourceDocument records to DB.

    Returns dict with: source_id, document_id, success, error, skipped
    """
    video_id = video["video_id"]
    checksum = collection_result["checksum"]
    plain_text = collection_result["plain_text"]
    s3_key = collection_result["s3_key"]

    session = SessionLocal()
    try:
        # Checksum dedup — skip if we already have this exact content
        if _checksum_exists(session, checksum):
            logger.info("Duplicate content detected for video %s (checksum %s) — skipping", video_id, checksum[:12])
            return {
                "source_id": None,
                "document_id": None,
                "success": True,
                "error": None,
                "skipped": True,
            }

        # Look up channel by external_id
        channel = None
        ext_id = video.get("channel_id")
        if ext_id:
            channel = session.query(Channel).filter(
                Channel.external_id == ext_id
            ).first()

        # Create Source record (one per video)
        source = Source(
            channel_id=channel.channel_id if channel else None,
            source_type="youtube",
            title=video.get("title", f"YouTube video {video_id}"),
            creator_name=video.get("channel_name"),
            canonical_url=video["url"],
            approved_flag=True,  # From whitelist
            ingestion_status="completed",
            published_at=_parse_published_at(video.get("published_at", "")),
            ingested_at=datetime.now(timezone.utc),
        )
        session.add(source)
        session.flush()  # Get source_id

        # Create SourceDocument record
        document = SourceDocument(
            source_id=source.source_id,
            s3_key=s3_key,
            raw_text=plain_text,
            transcript_available=True,
            language="en",
            checksum=checksum,
        )
        session.add(document)
        session.commit()

        logger.info(
            "Indexed video %s — source_id=%s, document_id=%s",
            video_id, source.source_id, document.document_id,
        )

        return {
            "source_id": str(source.source_id),
            "document_id": str(document.document_id),
            "success": True,
            "error": None,
            "skipped": False,
        }

    except Exception as e:
        session.rollback()
        logger.exception("Failed to index video %s", video_id)
        raise
    finally:
        session.close()
