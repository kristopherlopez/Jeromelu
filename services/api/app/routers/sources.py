import logging
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.analyst.identify_voice import EnrollmentError, enroll
from app.analyst.video_staging import (
    VideoStagingError,
    download_persistent_video,
    extract_frame,
    staged_video_local,
)
from app.analyst.visual_id import VisualIdError, enroll_face_from_image
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


@contextmanager
def _acquire_video_for_reassign(source: Source):
    """Yield a local video Path the reassign endpoint can ffmpeg against.

    Picks persistent-S3 fast-path when ``source.video_s3_key`` is set,
    falls back to on-demand yt-dlp via ``staged_video_local``. Cleans up
    its temp dir on exit.
    """
    if source.video_s3_key:
        with tempfile.TemporaryDirectory(prefix="jeromelu-reassign-") as tmp:
            video_path = Path(tmp) / "video.mp4"
            download_persistent_video(source.video_s3_key, video_path)
            yield video_path
    else:
        try:
            with staged_video_local(source.canonical_url) as video_path:
                yield video_path
        except VideoStagingError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"yt-dlp acquisition failed: {exc}",
            )


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


# ---------------------------------------------------------------------------
# People search (Phase 4b-action) — for the review-UI Person picker
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Face reassign (Phase 4b-action) — operator overrides a misidentified turn
# ---------------------------------------------------------------------------

class ReassignRequest(BaseModel):
    person_id: uuid.UUID
    frame_ts: float | None = Field(
        default=None,
        description=(
            "Timestamp (seconds) of the video frame that contained the "
            "clicked face. Used to extract the face crop for an enrollment "
            "embedding. If null, the speaker turn's mid-point is used."
        ),
    )
    bbox: list[float] | None = Field(
        default=None,
        description=(
            "Optional [x1,y1,x2,y2] hint to disambiguate when multiple "
            "faces are visible in the frame. If null, the largest detected "
            "face wins."
        ),
    )


@router.post("/sources/{source_id}/speakers/{segment_id}/reassign")
def reassign_speaker(
    source_id: uuid.UUID,
    segment_id: uuid.UUID,
    body: ReassignRequest,
    db: Session = Depends(get_db),
):
    """Operator override: a face on the video overlay was misidentified.

    On save:
      1. Set ``source_speakers.speaker_person_id = body.person_id`` for the
         clicked turn (and ``match_method='manual'``, ``match_confidence=1.0``).
      2. Extract the face from the video frame at ``frame_ts`` and write a
         new ``person_face_embeddings`` row (``created_by='manual'``).
      3. Extract a voiceprint from the speaker turn's audio span and write
         ``person_voiceprints`` rows (``created_by='manual'``). Skipped if
         the turn is shorter than the embedder's minimum.

    Idempotent on the SourceSpeaker update; embeddings are append-only —
    repeated clicks add more rows. That's intentional: every correction
    grows the registry.

    See [identification.md § Manual reassign](../system/identification.md).
    """
    # 1. Validate inputs
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    # Either a persisted video (legacy) or a YouTube canonical_url we can
    # re-fetch ephemerally — without one of those, there's no pixels to
    # crop a face out of.
    if not source.video_s3_key and not (
        source.source_type == "youtube" and source.canonical_url
    ):
        raise HTTPException(
            status_code=400,
            detail="Source has no video_s3_key and no YouTube URL — face reassign needs pixels",
        )

    speaker = (
        db.query(SourceSpeaker)
        .filter(SourceSpeaker.segment_id == segment_id)
        .first()
    )
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker segment not found")

    person = db.query(Person).filter(Person.person_id == body.person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # 2. Compute the frame timestamp to extract a face from. Default to the
    #    middle of the speaker turn — that's where the host is most likely
    #    to be on screen if the format is multi-cam.
    frame_ts = body.frame_ts
    if frame_ts is None:
        frame_ts = (speaker.start_ts + speaker.end_ts) / 2.0

    # 3. Extract face crop from video and enroll. Two acquisition paths
    #    in `_acquire_video_for_reassign`: persisted S3 mp4 (legacy) or
    #    on-demand yt-dlp via staged_video_local.
    face_id_written: uuid.UUID | None = None
    with _acquire_video_for_reassign(source) as video_path:
        with tempfile.TemporaryDirectory(prefix="jeromelu-reassign-frame-") as ftmp:
            frame_path = Path(ftmp) / "frame.jpg"
            try:
                extract_frame(video_path, frame_ts, frame_path)
            except VideoStagingError as exc:
                raise HTTPException(status_code=500, detail=str(exc))
            try:
                face_id_written, det_score, _area = enroll_face_from_image(
                    db,
                    person_id=body.person_id,
                    source_id=source_id,
                    image_path=frame_path,
                    frame_ts=frame_ts,
                    created_by="manual",
                )
            except VisualIdError as exc:
                logger.warning("Face enrollment skipped during reassign: %s", exc)

    # 4. Voiceprint write-back from the speaker turn's audio span. Same
    #    pattern as `enroll_voice_cli.py`. Skip silently when the turn is
    #    too short for the embedder.
    voice_rows_written = 0
    try:
        result = enroll(
            db,
            person_id=body.person_id,
            source_id=source_id,
            start_ts=float(speaker.start_ts),
            end_ts=float(speaker.end_ts),
            created_by="manual",
        )
        voice_rows_written = result.voiceprints_written
    except EnrollmentError as exc:
        logger.warning("Voiceprint enrollment skipped during reassign: %s", exc)

    # 5. Mark the speaker turn as manually corrected.
    speaker.speaker_person_id = body.person_id
    speaker.match_method = "manual"
    speaker.match_confidence = 1.0
    db.commit()

    return {
        "segment_id": str(segment_id),
        "person_id": str(body.person_id),
        "person_name": person.canonical_name,
        "face_embedding_id": str(face_id_written) if face_id_written else None,
        "voiceprints_written": voice_rows_written,
        "match_method": "manual",
    }
