import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from jeromelu_shared.db import (
    Claim,
    ClaimAssociation,
    ClaimChunk,
    Person,
    Source,
    SourceChunk,
    SourceDocument,
    SourceSpeaker,
)
from jeromelu_shared.s3 import download_raw, presign_raw, presign_video

from ..deps import get_db

logger = logging.getLogger(__name__)


def _face_track_key_from_audio(audio_s3_key: str) -> str:
    if audio_s3_key.endswith(".m4a"):
        return audio_s3_key[: -len(".m4a")] + ".face_track.json"
    return audio_s3_key + ".face_track.json"

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

    # Speaker turns (one row per contiguous turn after mig 045/046)
    speakers = (
        db.query(SourceSpeaker)
        .filter(SourceSpeaker.document_id == doc.document_id)
        .order_by(SourceSpeaker.start_ts)
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

    # Get claims with their linked chunks and subject associations
    claims = (
        db.query(Claim)
        .filter(Claim.document_id == doc.document_id)
        .options(
            joinedload(Claim.chunk_links).joinedload(ClaimChunk.chunk),
            joinedload(Claim.associations),
        )
        .all()
    )

    # Phase 2: claim subject lives on claim_associations (one row, role='subject').
    # For source-document claim views the subject is almost always a player —
    # only person_id is dispatched here. team/match/venue/round subjects render
    # without a name today; extend if needed.
    person_ids: set[uuid.UUID] = set()
    for c in claims:
        for a in c.associations:
            if a.role == "subject" and a.person_id:
                person_ids.add(a.person_id)
    # Phase 4: pull every Person referenced by the speaker provenance
    # columns (final, audio-only, visual-only) so the renderer can show
    # names alongside the colour-coded match_method.
    for sp in speakers:
        for pid in (sp.speaker_person_id, sp.audio_match_person_id, sp.visual_match_person_id):
            if pid:
                person_ids.add(pid)
    people = {}
    if person_ids:
        for p in db.query(Person).filter(Person.person_id.in_(person_ids)).all():
            people[p.person_id] = p

    claims_data = []
    for claim in claims:
        subject_assoc = next((a for a in claim.associations if a.role == "subject"), None)
        entity = (
            people.get(subject_assoc.person_id)
            if subject_assoc and subject_assoc.person_id
            else None
        )
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

    # Phase 4 visual identification: presign the local-mp4 video and the
    # face-track JSON so the browser overlay can fetch them directly from
    # S3 without proxying. Both have a 1h TTL; review sessions are
    # rarely longer than that.
    video_url: str | None = None
    face_track_url: str | None = None
    if source.video_s3_key:
        try:
            video_url = presign_video(source.video_s3_key)
        except Exception:
            logger.exception("Failed to presign video for source %s", source.source_id)
    if source.audio_s3_key:
        # The face-track JSON is served via the API proxy below
        # (`/api/sources/{id}/face-track`) rather than a presigned S3 URL,
        # because S3 buckets have no CORS policy and the browser blocks
        # direct cross-origin fetches. The proxy reuses the API's CORS
        # config (which already allows the dev origin).
        face_track_url = f"/api/sources/{source.source_id}/face-track"

    def _person_name(pid: uuid.UUID | None) -> str | None:
        return people[pid].canonical_name if pid and pid in people else None

    return {
        "source": {
            "source_id": str(source.source_id),
            "title": source.title,
            "canonical_url": source.canonical_url,
            "published_at": source.published_at.isoformat() if source.published_at else None,
            "creator_name": source.creator_name,
            "source_type": source.source_type,
            "video_url": video_url,
            "face_track_url": face_track_url,
            "video_format": source.video_format,
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
                "speaker_segment_id": (
                    str(ch.speaker_segment_id) if ch.speaker_segment_id else None
                ),
                "paragraph_break": ch.paragraph_break,
            }
            for ch in chunks
        ],
        "speakers": [
            {
                "segment_id": str(sp.segment_id),
                "speaker_label": sp.speaker_label,
                "speaker_person_id": (
                    str(sp.speaker_person_id) if sp.speaker_person_id else None
                ),
                "speaker_person_name": _person_name(sp.speaker_person_id),
                "start_ts": sp.start_ts,
                "end_ts": sp.end_ts,
                "match_method": sp.match_method,
                "match_confidence": sp.match_confidence,
                "audio_match_person_id": (
                    str(sp.audio_match_person_id) if sp.audio_match_person_id else None
                ),
                "audio_match_person_name": _person_name(sp.audio_match_person_id),
                "audio_match_score": sp.audio_match_score,
                "visual_match_person_id": (
                    str(sp.visual_match_person_id) if sp.visual_match_person_id else None
                ),
                "visual_match_person_name": _person_name(sp.visual_match_person_id),
                "visual_match_score": sp.visual_match_score,
            }
            for sp in speakers
        ],
    }


@router.get("/sources/{source_id}/face-track")
def get_face_track(source_id: uuid.UUID, db: Session = Depends(get_db)):
    """Proxy the face-track JSON from S3 to the browser.

    S3 buckets in this project have no CORS policy, so the review-UI
    overlay can't fetch presigned S3 URLs directly — the API serves the
    artefact instead. The JSON is small (under 1 MB for a 45-min source)
    so this isn't a meaningful bandwidth concern.
    """
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.audio_s3_key:
        raise HTTPException(status_code=404, detail="No audio key for source")

    key = _face_track_key_from_audio(source.audio_s3_key)
    try:
        body = download_raw(key)
    except Exception as exc:
        logger.warning("Face-track fetch failed for %s: %s", source_id, exc)
        raise HTTPException(status_code=404, detail="Face-track not found")

    return Response(
        content=body,
        media_type="application/json",
        # Browser caches the JSON aggressively — face-track is immutable
        # for a given (source, JSON_VERSION). Bumping FACE_TRACK_JSON_VERSION
        # produces a new artefact, but the API path stays the same; clients
        # that need a fresh copy should hard-refresh.
        headers={"Cache-Control": "public, max-age=300"},
    )


class SpeakerRenameRequest(BaseModel):
    speaker_label: str = Field(min_length=1, max_length=200)


@router.patch("/sources/speakers/{segment_id}")
def rename_speaker(
    segment_id: uuid.UUID,
    body: SpeakerRenameRequest,
    db: Session = Depends(get_db),
):
    """Rename a SourceSpeaker turn — sets `speaker_label` to a human-readable
    name (e.g. "Aaron Woods"). Person-resolution (`speaker_person_id`) is a
    separate Transform pass; this endpoint only touches the label.

    All turn rows for the same speaker (i.e. all rows whose current label
    matches the target row's current label) are renamed together so the
    rename feels like "Speaker 0 → Aaron Woods" across the whole document.
    """
    target = db.query(SourceSpeaker).filter(SourceSpeaker.segment_id == segment_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Speaker segment not found")

    # Rename every turn in the same document that shares the current label.
    new_label = body.speaker_label.strip()
    if not new_label:
        raise HTTPException(status_code=400, detail="speaker_label must not be blank")

    updated = (
        db.query(SourceSpeaker)
        .filter(
            SourceSpeaker.document_id == target.document_id,
            SourceSpeaker.speaker_label == target.speaker_label,
        )
        .all()
    )
    for sp in updated:
        sp.speaker_label = new_label
    db.commit()

    return {
        "renamed": len(updated),
        "speaker_label": new_label,
        "document_id": str(target.document_id),
    }
