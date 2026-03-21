import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from jeromelu_shared.db import (
    Claim,
    ClaimChunk,
    Entity,
    Source,
    SourceChunk,
    SourceDocument,
)

from ..deps import get_db

router = APIRouter()


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Lightweight stats for the home page activity pulse."""
    source_count = db.query(func.count(Source.source_id)).scalar() or 0
    claim_count = db.query(func.count(Claim.claim_id)).scalar() or 0

    # Most recent source ingested
    latest_source = (
        db.query(Source)
        .order_by(Source.ingested_at.desc().nullslast())
        .first()
    )

    return {
        "sources_scanned": source_count,
        "claims_extracted": claim_count,
        "latest_source": {
            "title": latest_source.title,
            "creator_name": latest_source.creator_name,
            "ingested_at": latest_source.ingested_at.isoformat() if latest_source.ingested_at else None,
        } if latest_source else None,
    }


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)):
    """List sources that have chunks, with claim counts."""
    claim_count_sq = (
        db.query(
            SourceDocument.source_id,
            func.count(Claim.claim_id).label("claim_count"),
        )
        .join(Claim, Claim.document_id == SourceDocument.document_id)
        .group_by(SourceDocument.source_id)
        .subquery()
    )

    rows = (
        db.query(Source, SourceDocument.chunk_count, claim_count_sq.c.claim_count)
        .join(SourceDocument, SourceDocument.source_id == Source.source_id)
        .outerjoin(claim_count_sq, claim_count_sq.c.source_id == Source.source_id)
        .filter(SourceDocument.chunk_count > 0)
        .filter(SourceDocument.cleaned_text.isnot(None))
        .order_by(Source.published_at.desc().nullslast())
        .all()
    )

    return {
        "items": [
            {
                "source_id": str(src.source_id),
                "title": src.title,
                "canonical_url": src.canonical_url,
                "published_at": src.published_at.isoformat() if src.published_at else None,
                "creator_name": src.creator_name,
                "claim_count": claim_count or 0,
            }
            for src, _chunk_count, claim_count in rows
        ]
    }


@router.get("/sources/{source_id}")
def get_source(source_id: uuid.UUID, db: Session = Depends(get_db)):
    """Full detail for a single source: source info, claims with chunks, all chunks."""
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    doc = (
        db.query(SourceDocument)
        .filter(SourceDocument.source_id == source_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="No document for source")

    # Get all chunks ordered by start timestamp for contiguous display
    chunks = (
        db.query(SourceChunk)
        .filter(SourceChunk.document_id == doc.document_id)
        .order_by(SourceChunk.start_ts)
        .all()
    )

    # Get chunk IDs that have claims linked
    claim_chunk_ids = set(
        r[0]
        for r in db.query(ClaimChunk.chunk_id)
        .join(SourceChunk, SourceChunk.chunk_id == ClaimChunk.chunk_id)
        .filter(SourceChunk.document_id == doc.document_id)
        .all()
    )

    # Get claims with their linked chunks and subject entity
    claims = (
        db.query(Claim)
        .filter(Claim.document_id == doc.document_id)
        .options(joinedload(Claim.chunk_links).joinedload(ClaimChunk.chunk))
        .all()
    )

    # Batch-load subject entities
    entity_ids = {c.subject_entity_id for c in claims if c.subject_entity_id}
    entities = {}
    if entity_ids:
        for e in db.query(Entity).filter(Entity.entity_id.in_(entity_ids)).all():
            entities[e.entity_id] = e

    claims_data = []
    for claim in claims:
        entity = entities.get(claim.subject_entity_id)
        claim_chunks = sorted(claim.chunk_links, key=lambda cl: cl.ordinal)
        claims_data.append(
            {
                "claim_id": str(claim.claim_id),
                "claim_type": claim.claim_type,
                "claim_text": claim.claim_text,
                "polarity": claim.polarity,
                "strength": claim.strength,
                "effective_round": claim.effective_round,
                "season": claim.season,
                "start_ts": claim.start_ts,
                "end_ts": claim.end_ts,
                "player_name": entity.canonical_name if entity else None,
                "chunks": [
                    {
                        "chunk_id": str(cl.chunk.chunk_id),
                        "start_ts": cl.chunk.start_ts,
                        "end_ts": cl.chunk.end_ts,
                        "raw_text": cl.chunk.raw_text,
                        "clean_text": cl.chunk.clean_text,
                    }
                    for cl in claim_chunks
                    if cl.chunk
                ],
            }
        )

    # Sort claims by claim-level timestamp, falling back to chunk timestamp
    def sort_key(c):
        if c["start_ts"] is not None:
            return c["start_ts"]
        ts_list = [ch["start_ts"] for ch in c["chunks"] if ch["start_ts"] is not None]
        return min(ts_list) if ts_list else float("inf")

    claims_data.sort(key=sort_key)

    return {
        "source": {
            "source_id": str(source.source_id),
            "title": source.title,
            "canonical_url": source.canonical_url,
            "published_at": source.published_at.isoformat() if source.published_at else None,
            "creator_name": source.creator_name,
            "source_type": source.source_type,
        },
        "claims": claims_data,
        "chunks": [
            {
                "chunk_id": str(ch.chunk_id),
                "chunk_index": ch.chunk_index,
                "raw_text": ch.raw_text,
                "clean_text": ch.clean_text,
                "start_ts": ch.start_ts,
                "end_ts": ch.end_ts,
                "has_claims": ch.chunk_id in claim_chunk_ids,
            }
            for ch in chunks
        ],
    }
