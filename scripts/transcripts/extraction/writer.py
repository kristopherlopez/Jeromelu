"""DB persistence for processed transcripts — Source, SourceDocument, SourceChunks, Claims."""

import hashlib
import json
import logging
from datetime import datetime, timezone

from jeromelu_shared.db import (
    Claim,
    ClaimChunk,
    SessionLocal,
    Source,
    SourceChunk,
    SourceDocument,
)
from scripts.extraction.resolver import resolve_entity

logger = logging.getLogger(__name__)


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _normalize(word: str) -> str:
    """Strip punctuation and common suffixes for fuzzy matching."""
    w = word.strip(".,!?;:'\"()[]")
    for suffix in ("'s", "'t", "'re", "'ve", "'ll", "'d", "'m"):
        if w.endswith(suffix):
            w = w[: -len(suffix)]
            break
    return w


def _find_chunks_for_claim(claim_text: str, chunks: list[SourceChunk]) -> list[SourceChunk]:
    """Find the contiguous run of segment-chunks that best match a claim.

    Each chunk is now a single transcript segment (5-6 words). We compute
    what fraction of each chunk's words appear in the claim text, then find
    the best contiguous run of high-coverage chunks (allowing 1-segment gaps
    for filler segments between substantive ones).

    Returns chunks sorted by chunk_index.
    """
    if not claim_text or not chunks:
        return []

    claim_lower = claim_text.lower()
    claim_word_set = set(
        _normalize(w)
        for w in claim_lower.replace("...", " ").replace("\u2014", " ").split()
        if len(_normalize(w)) >= 3
    )

    if not claim_word_set:
        return []

    # Score each chunk by coverage: fraction of its words found in the claim
    COVERAGE_THRESHOLD = 0.4
    coverages: list[float] = []
    for chunk in chunks:
        chunk_text = chunk.clean_text or chunk.raw_text
        words = [_normalize(w) for w in chunk_text.lower().split() if len(_normalize(w)) >= 3]
        if not words:
            coverages.append(0.0)
            continue
        hits = sum(1 for w in words if w in claim_word_set)
        coverages.append(hits / len(words))

    # Find the best contiguous run of high-coverage chunks, allowing 1-gap
    n = len(chunks)
    best_start = -1
    best_end = -1
    best_score = 0.0

    i = 0
    while i < n:
        if coverages[i] < COVERAGE_THRESHOLD:
            i += 1
            continue

        run_start = i
        run_end = i
        gap = 0

        j = i + 1
        while j < n and gap <= 1:
            if coverages[j] >= COVERAGE_THRESHOLD:
                run_end = j
                gap = 0
            else:
                gap += 1
            j += 1

        matching_covs = [coverages[k] for k in range(run_start, run_end + 1)
                         if coverages[k] >= COVERAGE_THRESHOLD]
        run_count = len(matching_covs)
        run_avg = sum(matching_covs) / run_count if run_count else 0
        composite = run_avg * run_count

        if composite > best_score:
            best_score = composite
            best_start = run_start
            best_end = run_end

        i = run_end + 1

    if best_start < 0 or best_score < 1.0:
        return []

    return chunks[best_start: best_end + 1]


def source_exists(canonical_url: str) -> bool:
    """Check if a Source with this canonical_url already exists."""
    session = SessionLocal()
    try:
        exists = session.query(Source.source_id).filter(
            Source.canonical_url == canonical_url
        ).first() is not None
        return exists
    finally:
        session.close()


def write_transcript(
    video_id: str,
    title: str,
    channel_id: str,
    published_at: str | None,
    stitched_text: str,
    chunk_dicts: list[dict],
    claims_json: list[dict],
) -> dict:
    """Persist everything in a single transaction.

    Returns summary dict with counts and IDs.
    """
    canonical_url = f"https://youtube.com/watch?v={video_id}"

    session = SessionLocal()
    try:
        # Idempotency check
        existing = session.query(Source).filter(
            Source.canonical_url == canonical_url
        ).first()
        if existing:
            return {
                "already_processed": True,
                "source_id": str(existing.source_id),
            }

        # Parse published_at
        pub_dt = None
        if published_at:
            try:
                pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        # Create Source
        source = Source(
            source_type="youtube",
            title=title,
            canonical_url=canonical_url,
            approved_flag=True,
            ingestion_status="completed",
            published_at=pub_dt,
            ingested_at=datetime.now(timezone.utc),
        )
        session.add(source)
        session.flush()

        # Create SourceDocument
        doc_checksum = _checksum(stitched_text)
        document = SourceDocument(
            source_id=source.source_id,
            raw_text=stitched_text,
            cleaned_text=stitched_text,
            transcript_available=True,
            language="en",
            checksum=doc_checksum,
            chunk_count=len(chunk_dicts),
        )
        session.add(document)
        session.flush()

        # Create SourceChunks
        db_chunks: list[SourceChunk] = []
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
            db_chunks.append(chunk)
        session.flush()

        # Create Claims with Entities and ClaimChunks
        claims_created = 0
        for claim_data in claims_json:
            # Resolve player entity
            player_entity = None
            if claim_data.get("player_name"):
                player_entity = resolve_entity(
                    session, claim_data["player_name"], "player"
                )

            # Resolve team entity (if provided)
            if claim_data.get("team_name"):
                resolve_entity(session, claim_data["team_name"], "team")

            # Find matching segment-chunks for this claim
            matched_chunks: list[SourceChunk] = []
            if claim_data.get("claim_text") and db_chunks:
                matched_chunks = _find_chunks_for_claim(claim_data["claim_text"], db_chunks)

            # Derive timestamps from matched chunks
            start_ts = matched_chunks[0].start_ts if matched_chunks else None
            end_ts = matched_chunks[-1].end_ts if matched_chunks else None

            claim = Claim(
                document_id=document.document_id,
                subject_entity_id=player_entity.entity_id if player_entity else None,
                claim_type=claim_data["claim_type"],
                claim_text=claim_data.get("claim_text"),
                polarity=claim_data.get("polarity"),
                strength=claim_data.get("strength"),
                effective_round=claim_data.get("effective_round"),
                season=claim_data.get("season"),
                start_ts=start_ts,
                end_ts=end_ts,
            )
            session.add(claim)
            session.flush()

            # Link claim to its segment-chunks
            for ordinal, matched_chunk in enumerate(matched_chunks):
                claim_chunk = ClaimChunk(
                    claim_id=claim.claim_id,
                    chunk_id=matched_chunk.chunk_id,
                    ordinal=ordinal,
                )
                session.add(claim_chunk)

            claims_created += 1

        session.commit()

        return {
            "already_processed": False,
            "source_id": str(source.source_id),
            "document_id": str(document.document_id),
            "chunks_created": len(db_chunks),
            "claims_created": claims_created,
        }

    except Exception:
        session.rollback()
        logger.exception("Failed to write transcript %s", video_id)
        raise
    finally:
        session.close()
