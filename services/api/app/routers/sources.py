import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from jeromelu_shared.db import (
    Claim,
    ClaimChunk,
    Person,
    Source,
    SourceChunk,
    SourceDocument,
    SourceSpeaker,
)
from jeromelu_shared.s3 import presign_video

from ..deps import get_db

logger = logging.getLogger(__name__)


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
def list_sources(
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None),
    sort: str = Query("newest", pattern="^(newest|oldest|most_claims|alpha)$"),
):
    """Paginated list of sources with claim counts.

    Includes sources with no transcript yet (queued, failed, or freshly
    discovered) so the wiki can surface ingestion state. Unprocessed
    sources have claim_count=0.

    Each row carries an optional ``voice`` block (channel slug / name /
    logo_url) so the wiki Sources index can render a voice chip that
    links through to the channel's wiki page.

    The full sources table is ~100k+ rows; un-paginated reads ship tens
    of MB. Callers should pass a sensible ``limit`` and use ``total`` /
    ``has_more`` in the response to drive pagination UI.
    """
    claim_count_sq = (
        db.query(
            SourceDocument.source_id,
            func.count(Claim.claim_id).label("claim_count"),
        )
        .join(Claim, Claim.document_id == SourceDocument.document_id)
        .group_by(SourceDocument.source_id)
        .subquery()
    )

    search_filter = None
    if search:
        like = f"%{search}%"
        search_filter = func.lower(Source.title).like(func.lower(like)) | func.lower(
            Source.creator_name
        ).like(func.lower(like))

    count_query = db.query(func.count(Source.source_id))
    if search_filter is not None:
        count_query = count_query.filter(search_filter)
    total = count_query.scalar() or 0

    rows_query = (
        db.query(Source, claim_count_sq.c.claim_count)
        .options(joinedload(Source.channel))
        .outerjoin(claim_count_sq, claim_count_sq.c.source_id == Source.source_id)
    )
    if search_filter is not None:
        rows_query = rows_query.filter(search_filter)

    if sort == "newest":
        rows_query = rows_query.order_by(Source.published_at.desc().nullslast())
    elif sort == "oldest":
        rows_query = rows_query.order_by(Source.published_at.asc().nullslast())
    elif sort == "most_claims":
        rows_query = rows_query.order_by(claim_count_sq.c.claim_count.desc().nullslast())
    elif sort == "alpha":
        rows_query = rows_query.order_by(Source.title.asc())

    rows = rows_query.limit(limit).offset(offset).all()

    def _voice(src: Source) -> dict | None:
        ch = src.channel
        if ch is None:
            return None
        return {
            "slug": ch.slug,
            "name": ch.name,
            "logo_url": ch.logo_url,
        }

    return {
        "items": [
            {
                "source_id": str(src.source_id),
                "title": src.title,
                "canonical_url": src.canonical_url,
                "published_at": src.published_at.isoformat() if src.published_at else None,
                "creator_name": src.creator_name,
                "claim_count": claim_count or 0,
                "voice": _voice(src),
            }
            for src, claim_count in rows
        ],
        "total": total,
        "has_more": offset + len(rows) < total,
    }


@router.get("/sources/{source_id}")
def get_source(source_id: uuid.UUID, db: Session = Depends(get_db)):
    """Full detail for a single source: source info, claims with chunks, all chunks.

    The ``speakers`` block and ``face_track_url`` field are populated from
    Lineup's outputs (``source_speakers`` + the S3 face-track JSON). When
    Lineup moves to an external API, those tables/artefacts stay as the
    contract the external service writes into, so this endpoint's shape is
    unchanged. See ``routers/lineup.py`` and ``memory/project_lineup_external.md``.
    """
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    doc = (
        db.query(SourceDocument)
        .filter(SourceDocument.source_id == source_id)
        .first()
    )
    # No document yet (Scout hasn't ingested or GPU hasn't transcribed): the
    # viewer still renders — video plays, transcript/claims tabs show an
    # empty state — so the user can at least watch in-app instead of being
    # bounced to a 404.
    if not doc:
        video_url: str | None = None
        if source.video_s3_key:
            try:
                video_url = presign_video(source.video_s3_key)
            except Exception:
                logger.exception("Failed to presign video for source %s", source.source_id)
        return {
            "source": {
                "source_id": str(source.source_id),
                "title": source.title,
                "canonical_url": source.canonical_url,
                "published_at": source.published_at.isoformat() if source.published_at else None,
                "creator_name": source.creator_name,
                "source_type": source.source_type,
                "video_url": video_url,
                "face_track_url": None,
                "video_format": source.video_format,
                "ingestion_status": source.ingestion_status,
                "transcription_status": source.transcription_status,
            },
            "claims": [],
            "chunks": [],
            "speakers": [],
        }

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
            "ingestion_status": source.ingestion_status,
            "transcription_status": source.transcription_status,
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


@router.get("/people/search")
def people_search(q: str = "", limit: int = 30, db: Session = Depends(get_db)):
    """Prefix + alias search over the people roster.

    Used by the review-UI Person picker (Phase 4b-action) when an operator
    reassigns a misidentified face to a known Person. Returns the top
    ``limit`` matches by canonical_name prefix; alias matches are
    secondary. Empty ``q`` returns the first ``limit`` rows alphabetically
    (handy for browsing a small registry).
    """
    if limit < 1 or limit > 200:
        limit = 30
    query = db.query(Person)
    q = q.strip()
    if q:
        like = f"{q}%"
        contains = f"%{q}%"
        # Prefix match on canonical_name beats substring beats alias hit.
        query = query.filter(
            (Person.canonical_name.ilike(like))
            | (Person.canonical_name.ilike(contains))
            | (Person.aliases.any(q))
        )
    rows = query.order_by(Person.canonical_name).limit(limit).all()
    return {
        "items": [
            {
                "person_id": str(p.person_id),
                "canonical_name": p.canonical_name,
                "slug": p.slug,
                "aliases": list(p.aliases or []),
            }
            for p in rows
        ]
    }
