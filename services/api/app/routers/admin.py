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

class IngestRawRequest(BaseModel):
    video_id: str
    channel_id: str


@router.post("/admin/ingest-raw", dependencies=[Depends(require_admin)])
def ingest_raw(req: IngestRawRequest, db: Session = Depends(get_db)):
    """Ingest a raw transcript from S3 into the database (no claims required).

    Creates Source + SourceDocument + SourceChunks from the raw transcript only.
    """
    video_id = req.video_id
    channel_id = req.channel_id
    canonical_url = f"https://youtube.com/watch?v={video_id}"

    existing = db.query(Source).filter(Source.canonical_url == canonical_url).first()
    if existing:
        return {"skipped": True, "source_id": str(existing.source_id)}

    prefix = f"youtube/{channel_id}/{video_id}.json"
    try:
        raw_data = _download_json(settings.s3_raw_bucket, prefix)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Raw transcript not found: {e}")

    raw_segments = raw_data.get("segments", [])
    stitched_text, deduped_raw = _stitch_segments(raw_segments)
    chunk_dicts = _chunk_segments(deduped_raw)

    pub_dt = None
    if raw_data.get("published_at"):
        try:
            pub_dt = datetime.fromisoformat(raw_data["published_at"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    try:
        source = Source(
            source_type="youtube",
            title=raw_data.get("title", f"YouTube video {video_id}"),
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
            s3_key=prefix,
            raw_text=stitched_text,
            transcript_available=True,
            language="en",
            checksum=_checksum(stitched_text),
            chunk_count=len(chunk_dicts),
        )
        db.add(doc)
        db.flush()

        for cd in chunk_dicts:
            db.add(SourceChunk(
                document_id=doc.document_id,
                chunk_index=cd["chunk_index"],
                raw_text=cd["raw_text"],
                start_offset=cd.get("start_offset"),
                end_offset=cd.get("end_offset"),
                start_ts=cd.get("start_ts"),
                end_ts=cd.get("end_ts"),
            ))
        db.commit()

        return {
            "source_id": str(source.source_id),
            "document_id": str(doc.document_id),
            "chunks_created": len(chunk_dicts),
        }
    except Exception:
        db.rollback()
        logger.exception("Failed to ingest-raw %s", video_id)
        raise


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


# ---------------------------------------------------------------------------
# Pipeline dashboard endpoints
# ---------------------------------------------------------------------------

@router.get("/admin/pipeline")
def pipeline_status(db: Session = Depends(get_db)):
    """Return pipeline stage for every source (DB-only, fast)."""
    # Subquery: claim count per source
    claim_count_sq = (
        db.query(
            SourceDocument.source_id,
            func.count(Claim.claim_id).label("claim_count"),
        )
        .join(Claim, Claim.document_id == SourceDocument.document_id)
        .group_by(SourceDocument.source_id)
        .subquery()
    )

    # Subquery: has any chunk with clean_text
    has_clean_sq = (
        db.query(
            SourceDocument.source_id,
            func.bool_or(SourceChunk.clean_text.isnot(None)).label("has_clean"),
        )
        .join(SourceChunk, SourceChunk.document_id == SourceDocument.document_id)
        .group_by(SourceDocument.source_id)
        .subquery()
    )

    rows = (
        db.query(
            Source,
            SourceDocument.s3_key,
            SourceDocument.chunk_count,
            claim_count_sq.c.claim_count,
            has_clean_sq.c.has_clean,
        )
        .outerjoin(SourceDocument, SourceDocument.source_id == Source.source_id)
        .outerjoin(claim_count_sq, claim_count_sq.c.source_id == Source.source_id)
        .outerjoin(has_clean_sq, has_clean_sq.c.source_id == Source.source_id)
        .order_by(Source.published_at.desc().nullslast())
        .all()
    )

    by_stage = {"discovered": 0, "collected": 0, "indexed": 0, "cleaned": 0, "extracted": 0}
    items = []

    for src, s3_key, chunk_count, claim_count, has_clean in rows:
        chunk_count = chunk_count or 0
        claim_count = claim_count or 0
        has_clean = bool(has_clean)

        stages = {
            "discovered": True,
            "collected": s3_key is not None or chunk_count > 0,
            "indexed": chunk_count > 0,
            "cleaned": has_clean,
            "extracted": claim_count > 0,
        }

        # Derive current stage (highest completed)
        current = "discovered"
        for stage in ("collected", "indexed", "cleaned", "extracted"):
            if stages[stage]:
                current = stage
        by_stage[current] += 1

        # Extract video_id from canonical_url
        video_id = None
        if src.canonical_url and "v=" in src.canonical_url:
            video_id = src.canonical_url.split("v=")[-1].split("&")[0]

        items.append({
            "source_id": str(src.source_id),
            "title": src.title,
            "video_id": video_id,
            "published_at": src.published_at.isoformat() if src.published_at else None,
            "stages": stages,
            "chunk_count": chunk_count,
            "claim_count": claim_count,
        })

    return {
        "summary": {"total": len(items), "by_stage": by_stage},
        "items": items,
    }


@router.get("/admin/sync-status")
def sync_status(db: Session = Depends(get_db)):
    """Cross-reference local files, MinIO, and DB to find mismatches."""
    import os
    import re

    # 1. Scan local transcript directories
    local_raw: set[str] = set()
    local_clean: set[str] = set()
    local_claims: set[str] = set()

    transcript_base = os.environ.get("TRANSCRIPT_DIR", "/data/transcripts")
    vid_pattern = re.compile(r"(?:.*_)?([A-Za-z0-9_-]{11})\.json$")

    for subdir, target_set in [
        ("raw", local_raw),
        ("clean", local_clean),
        ("processed", local_claims),
    ]:
        dirpath = os.path.join(transcript_base, subdir)
        if not os.path.isdir(dirpath):
            continue
        for fname in os.listdir(dirpath):
            m = vid_pattern.match(fname)
            if m:
                target_set.add(m.group(1))

    # 2. Scan MinIO buckets
    minio_raw: set[str] = set()
    minio_clean: set[str] = set()

    try:
        client = get_s3_client()
        for bucket, target_set in [
            (settings.s3_raw_bucket, minio_raw),
            (settings.s3_clean_bucket, minio_clean),
        ]:
            try:
                paginator = client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=bucket, Prefix="youtube/"):
                    for obj in page.get("Contents", []):
                        key = obj["Key"]
                        # youtube/{channel_id}/{video_id}.json
                        parts = key.rstrip("/").split("/")
                        if len(parts) >= 3 and parts[-1].endswith(".json"):
                            vid = parts[-1].replace(".json", "")
                            target_set.add(vid)
            except Exception:
                pass
    except Exception:
        pass

    # 3. DB video IDs from canonical_url
    db_urls = db.query(Source.canonical_url).filter(Source.canonical_url.isnot(None)).all()
    db_vids: set[str] = set()
    for (url,) in db_urls:
        if url and "v=" in url:
            db_vids.add(url.split("v=")[-1].split("&")[0])

    # 4. Build mismatch list
    all_vids = local_raw | local_clean | local_claims | minio_raw | minio_clean | db_vids
    mismatches = []
    for vid in sorted(all_vids):
        entry = {
            "video_id": vid,
            "local_raw": vid in local_raw,
            "local_clean": vid in local_clean,
            "local_claims": vid in local_claims,
            "minio_raw": vid in minio_raw,
            "minio_clean": vid in minio_clean,
            "in_db": vid in db_vids,
        }
        values = list(entry.values())[1:]  # skip video_id
        if not all(values):
            mismatches.append(entry)

    # Summary counts
    summary = {
        "total_videos": len(all_vids),
        "mismatches": len(mismatches),
        "local_not_in_minio": len((local_raw | local_clean) - (minio_raw | minio_clean)),
        "minio_not_in_db": len((minio_raw | minio_clean) - db_vids),
        "db_not_in_minio": len(db_vids - (minio_raw | minio_clean)),
    }

    return {"summary": summary, "items": mismatches}


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


# ---------------------------------------------------------------------------
# Transcript diff viewer (test files)
# ---------------------------------------------------------------------------

def _transcript_base() -> str:
    """Resolve transcript directory — works in Docker and local dev."""
    import os
    from_env = os.environ.get("TRANSCRIPT_DIR")
    if from_env and os.path.isdir(from_env):
        return from_env
    # Local dev: project root / data / transcripts
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    local = os.path.join(project_root, "data", "transcripts")
    if os.path.isdir(local):
        return local
    return from_env or "/data/transcripts"


@router.get("/admin/transcript-test-files")
def list_test_files():
    """List transcript files in the test directory with their raw counterparts."""
    import os
    import glob as globmod

    transcript_base = _transcript_base()
    test_dir = os.path.join(transcript_base, "test")
    raw_dir = os.path.join(transcript_base, "raw")
    archive_raw_dir = os.path.join(transcript_base, "archive", "raw")

    if not os.path.isdir(test_dir):
        return {"files": []}

    files = []
    for path in sorted(globmod.glob(os.path.join(test_dir, "*.json"))):
        fname = os.path.basename(path)
        has_raw = os.path.isfile(os.path.join(raw_dir, fname)) or os.path.isfile(
            os.path.join(archive_raw_dir, fname)
        )
        # Read title from test file
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            title = data.get("title", fname)
        except Exception:
            title = fname
        files.append({"filename": fname, "title": title, "has_raw": has_raw})

    return {"files": files}


@router.get("/admin/transcript-diff/{filename}")
def transcript_diff(filename: str):
    """Return raw vs test transcript segments for diffing."""
    import os

    if not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Must be a .json file")

    transcript_base = _transcript_base()
    test_path = os.path.join(transcript_base, "test", filename)
    raw_path = os.path.join(transcript_base, "raw", filename)
    archive_raw_path = os.path.join(transcript_base, "archive", "raw", filename)

    if not os.path.isfile(test_path):
        raise HTTPException(status_code=404, detail="Test file not found")

    # Find the raw file
    actual_raw = raw_path if os.path.isfile(raw_path) else archive_raw_path
    if not os.path.isfile(actual_raw):
        raise HTTPException(status_code=404, detail="Raw file not found")

    with open(actual_raw, encoding="utf-8") as f:
        raw_data = json.load(f)
    with open(test_path, encoding="utf-8") as f:
        test_data = json.load(f)

    raw_segs = raw_data.get("segments", [])
    test_segs = test_data.get("segments", [])

    # Build diff: only include segments where text differs
    diffs = []
    total = min(len(raw_segs), len(test_segs))
    for i in range(total):
        raw_text = raw_segs[i].get("text", "")
        test_text = test_segs[i].get("text", "")
        if raw_text != test_text:
            diffs.append({
                "index": i,
                "start": raw_segs[i].get("start", 0),
                "raw": raw_text,
                "test": test_text,
            })

    return {
        "title": raw_data.get("title", filename),
        "total_segments": total,
        "diff_count": len(diffs),
        "diffs": diffs,
    }
