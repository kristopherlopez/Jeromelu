"""Admin endpoints for server-side transcript ingestion.

Flow: local machine uploads clean transcript + claims to S3, then calls
POST /api/admin/ingest to write everything to the database.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from jeromelu_shared.config import settings
from jeromelu_shared.db import (
    Claim,
    ClaimChunk,
    Entity,
    Source,
    SourceChunk,
    SourceDocument,
)
from jeromelu_shared.s3 import get_s3_client
from jeromelu_shared.scraping.nrl import TEAM_CODE_MAP, normalize_name

from ..deps import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def require_admin(x_admin_key: str = Header(...)):
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")


# ---------------------------------------------------------------------------
# Helpers (inlined from scripts/extraction to avoid cross-package dependency)
# ---------------------------------------------------------------------------

def _stitch_segments(segments: list[dict]) -> tuple[str, list[dict]]:
    if not segments:
        return "", []
    sorted_segs = sorted(segments, key=lambda s: s["start"])
    deduped: list[dict] = []
    last_end = -1.0
    for seg in sorted_segs:
        start, end = seg["start"], seg["end"]
        text = seg["text"].strip()
        if not text:
            continue
        if start < last_end and end <= last_end:
            continue
        deduped.append({"start": start, "end": end, "text": text})
        last_end = max(last_end, end)
    full_text = " ".join(s["text"] for s in deduped)
    full_text = full_text.replace(">>", "").replace("  ", " ").strip()
    return full_text, deduped


def _chunk_segments(
    raw_segments: list[dict], clean_segments: list[dict] | None = None
) -> list[dict]:
    chunks: list[dict] = []
    offset = 0
    for i, seg in enumerate(raw_segments):
        raw = seg["text"]
        clean = clean_segments[i]["text"] if clean_segments and i < len(clean_segments) else None
        chunks.append({
            "chunk_index": i,
            "raw_text": raw,
            "clean_text": clean,
            "start_ts": seg["start"],
            "end_ts": seg["end"],
            "start_offset": offset,
            "end_offset": offset + len(raw),
        })
        offset += len(raw) + 1
    return chunks


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _normalize(word: str) -> str:
    w = word.strip(".,!?;:'\"()[]")
    for suffix in ("'s", "'t", "'re", "'ve", "'ll", "'d", "'m"):
        if w.endswith(suffix):
            w = w[: -len(suffix)]
            break
    return w


_TEAM_NAMES = {v.lower(): v for v in set(TEAM_CODE_MAP.values())}
_TEAM_NAMES.update({k.lower(): v for k, v in TEAM_CODE_MAP.items()})


def _resolve_entity(session: Session, name: str, entity_type: str) -> Entity:
    normalized = normalize_name(name).strip()
    entity = session.query(Entity).filter(
        Entity.entity_type == entity_type,
        func.lower(Entity.canonical_name) == normalized.lower(),
    ).first()
    if entity:
        return entity
    entity = session.query(Entity).filter(
        Entity.entity_type == entity_type,
        Entity.aliases.any(normalized),
    ).first()
    if entity:
        return entity
    if entity_type == "team":
        canonical_team = _TEAM_NAMES.get(normalized.lower())
        if canonical_team:
            entity = session.query(Entity).filter(
                Entity.entity_type == "team",
                func.lower(Entity.canonical_name) == canonical_team.lower(),
            ).first()
            if entity:
                return entity
            normalized = canonical_team
    entity = Entity(entity_type=entity_type, canonical_name=normalized, aliases=[])
    session.add(entity)
    session.flush()
    return entity


def _find_chunks_for_claim(claim_text: str, chunks: list[SourceChunk]) -> list[SourceChunk]:
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
    n = len(chunks)
    best_start, best_end, best_score = -1, -1, 0.0
    i = 0
    while i < n:
        if coverages[i] < COVERAGE_THRESHOLD:
            i += 1
            continue
        run_start = run_end = i
        gap = 0
        j = i + 1
        while j < n and gap <= 1:
            if coverages[j] >= COVERAGE_THRESHOLD:
                run_end = j
                gap = 0
            else:
                gap += 1
            j += 1
        matching = [coverages[k] for k in range(run_start, run_end + 1) if coverages[k] >= COVERAGE_THRESHOLD]
        composite = (sum(matching) / len(matching)) * len(matching) if matching else 0
        if composite > best_score:
            best_score, best_start, best_end = composite, run_start, run_end
        i = run_end + 1
    if best_start < 0 or best_score < 1.0:
        return []
    return chunks[best_start: best_end + 1]


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------

def _download_json(bucket: str, key: str) -> dict:
    client = get_s3_client()
    resp = client.get_object(Bucket=bucket, Key=key)
    return json.loads(resp["Body"].read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    video_id: str
    channel_id: str | None = None


@router.post("/admin/ingest", dependencies=[Depends(require_admin)])
def ingest(req: IngestRequest, db: Session = Depends(get_db)):
    """Ingest a transcript + claims from S3 into the database.

    Expects files at:
      - Raw:   s3://jeromelu-raw-transcripts/youtube/{channel_id}/{video_id}.json
      - Clean: s3://jeromelu-clean-documents/youtube/{channel_id}/{video_id}.json
      - Claims: s3://jeromelu-clean-documents/claims/{video_id}.json
    """
    video_id = req.video_id
    canonical_url = f"https://youtube.com/watch?v={video_id}"

    # Check idempotency
    existing = db.query(Source).filter(Source.canonical_url == canonical_url).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Source already exists: {existing.source_id}")

    # Resolve channel_id from request or by scanning S3
    channel_id = req.channel_id
    if not channel_id:
        raise HTTPException(status_code=400, detail="channel_id is required")

    prefix = f"youtube/{channel_id}/{video_id}.json"

    # Load raw transcript
    try:
        raw_data = _download_json(settings.s3_raw_bucket, prefix)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Raw transcript not found at s3://{settings.s3_raw_bucket}/{prefix}: {e}")

    # Load clean transcript
    try:
        clean_data = _download_json(settings.s3_clean_bucket, prefix)
    except Exception:
        clean_data = None

    # Load claims
    claims_key = f"claims/{video_id}.json"
    try:
        claims_json = _download_json(settings.s3_clean_bucket, claims_key)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Claims not found at s3://{settings.s3_clean_bucket}/{claims_key}: {e}")

    # Stitch segments
    raw_segments = raw_data.get("segments", [])
    _, deduped_raw = _stitch_segments(raw_segments)

    deduped_clean = None
    if clean_data:
        clean_segments = clean_data.get("segments", [])
        stitched_text, deduped_clean = _stitch_segments(clean_segments)
    else:
        stitched_text, _ = _stitch_segments(raw_segments)

    # Chunk
    chunk_dicts = _chunk_segments(deduped_raw, deduped_clean)

    # Parse published_at
    pub_dt = None
    source_data = clean_data or raw_data
    if source_data.get("published_at"):
        try:
            pub_dt = datetime.fromisoformat(source_data["published_at"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    # Write to DB
    try:
        source = Source(
            source_type="youtube",
            title=source_data.get("title", f"YouTube video {video_id}"),
            canonical_url=canonical_url,
            approved_flag=True,
            ingestion_status="completed",
            published_at=pub_dt,
            ingested_at=datetime.now(timezone.utc),
        )
        db.add(source)
        db.flush()

        doc = SourceDocument(
            source_id=source.source_id,
            raw_text=stitched_text,
            cleaned_text=stitched_text,
            transcript_available=True,
            language="en",
            checksum=_checksum(stitched_text),
            chunk_count=len(chunk_dicts),
        )
        db.add(doc)
        db.flush()

        db_chunks: list[SourceChunk] = []
        for cd in chunk_dicts:
            chunk = SourceChunk(
                document_id=doc.document_id,
                chunk_index=cd["chunk_index"],
                raw_text=cd["raw_text"],
                clean_text=cd.get("clean_text"),
                start_offset=cd.get("start_offset"),
                end_offset=cd.get("end_offset"),
                start_ts=cd.get("start_ts"),
                end_ts=cd.get("end_ts"),
            )
            db.add(chunk)
            db_chunks.append(chunk)
        db.flush()

        claims_created = 0
        for claim_data in claims_json:
            player_entity = None
            if claim_data.get("player_name"):
                player_entity = _resolve_entity(db, claim_data["player_name"], "player")
            if claim_data.get("team_name"):
                _resolve_entity(db, claim_data["team_name"], "team")

            matched_chunks: list[SourceChunk] = []
            if claim_data.get("claim_text") and db_chunks:
                matched_chunks = _find_chunks_for_claim(claim_data["claim_text"], db_chunks)

            start_ts = matched_chunks[0].start_ts if matched_chunks else None
            end_ts = matched_chunks[-1].end_ts if matched_chunks else None

            claim = Claim(
                document_id=doc.document_id,
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
            db.add(claim)
            db.flush()

            for ordinal, matched_chunk in enumerate(matched_chunks):
                db.add(ClaimChunk(
                    claim_id=claim.claim_id,
                    chunk_id=matched_chunk.chunk_id,
                    ordinal=ordinal,
                ))
            claims_created += 1

        db.commit()

        return {
            "source_id": str(source.source_id),
            "document_id": str(doc.document_id),
            "chunks_created": len(db_chunks),
            "claims_created": claims_created,
        }

    except Exception:
        db.rollback()
        logger.exception("Failed to ingest %s", video_id)
        raise


class UpdateCleanTextRequest(BaseModel):
    video_id: str
    channel_id: str


@router.post("/admin/update-clean-text", dependencies=[Depends(require_admin)])
def update_clean_text(req: UpdateCleanTextRequest, db: Session = Depends(get_db)):
    """Backfill clean_text on existing chunks from a clean transcript in S3."""
    canonical_url = f"https://youtube.com/watch?v={req.video_id}"

    source = db.query(Source).filter(Source.canonical_url == canonical_url).first()
    if not source:
        raise HTTPException(status_code=404, detail=f"No source found for {canonical_url}")

    doc = db.query(SourceDocument).filter(SourceDocument.source_id == source.source_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="No document found")

    key = f"youtube/{req.channel_id}/{req.video_id}.json"
    try:
        clean_data = _download_json(settings.s3_clean_bucket, key)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Clean transcript not found at s3://{settings.s3_clean_bucket}/{key}: {e}")

    _, deduped_clean = _stitch_segments(clean_data.get("segments", []))

    chunks = (
        db.query(SourceChunk)
        .filter(SourceChunk.document_id == doc.document_id)
        .order_by(SourceChunk.chunk_index)
        .all()
    )

    updated = 0
    for chunk in chunks:
        if chunk.chunk_index < len(deduped_clean):
            chunk.clean_text = deduped_clean[chunk.chunk_index]["text"]
            updated += 1

    db.commit()
    return {"source_id": str(source.source_id), "chunks_updated": updated}
