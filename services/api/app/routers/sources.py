import json
import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.analyst.face_clusters import analyse_clusters, cluster_source_detections
from app.analyst.face_runs import (
    compute_face_runs,
    compute_face_runs_from_detections,
    detections_exist,
)
from app.analyst.identify_voice import (
    EnrollmentError,
    enroll,
    enroll_span_with_context,
    enrollment_context,
)
from app.analyst.video_worker_client import VideoWorkerError, fetch_frame_to
from app.analyst.visual_id import VisualIdError, enroll_face_from_image
from jeromelu_shared.db import (
    Channel,
    Claim,
    ClaimAssociation,
    ClaimChunk,
    Person,
    PersonFaceEmbedding,
    Source,
    SourceChunk,
    SourceDocument,
    SourceFaceCluster,
    SourceFaceDetection,
    SourceSpeaker,
)
from sqlalchemy import update as sa_update
from jeromelu_shared.s3 import download_raw, presign_raw, presign_video

from ..deps import get_db

logger = logging.getLogger(__name__)


def _face_track_key_from_audio(audio_s3_key: str) -> str:
    if audio_s3_key.endswith(".m4a"):
        return audio_s3_key[: -len(".m4a")] + ".face_track.json"
    return audio_s3_key + ".face_track.json"


def _fetch_reassign_frame(source: Source, ts: float, dest: Path) -> None:
    """Pull one JPEG at ``ts`` for the reassign endpoint. Routes via the
    video-worker sidecar — the API container has no yt-dlp / ffmpeg.

    Strategy:
      - YouTube source with canonical_url → ask the worker to yt-dlp
        only a ~6s slice around ts (``prefer_section``). Fastest cold
        path; bypasses S3 entirely.
      - Otherwise → use ``video_s3_key`` against the worker's LRU disk
        cache. First click is the full mp4 download; repeats are
        ~instant.
    """
    try:
        if source.source_type == "youtube" and source.canonical_url:
            fetch_frame_to(
                dest,
                canonical_url=source.canonical_url,
                persistent_video_s3_key=source.video_s3_key,
                ts=ts,
                prefer_section=True,
            )
        elif source.video_s3_key:
            fetch_frame_to(
                dest,
                persistent_video_s3_key=source.video_s3_key,
                ts=ts,
            )
        else:
            fetch_frame_to(
                dest,
                canonical_url=source.canonical_url,
                ts=ts,
            )
    except VideoWorkerError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


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
    """List every row in the sources table, with claim counts.

    Includes sources with no transcript yet (queued, failed, or freshly
    discovered) so the wiki can surface ingestion state. Unprocessed
    sources have claim_count=0.

    Each row carries an optional ``voice`` block (channel slug / name /
    logo_url) so the wiki Sources index can render a voice chip that
    links through to the channel's wiki page.
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

    rows = (
        db.query(Source, claim_count_sq.c.claim_count)
        .options(joinedload(Source.channel))
        .outerjoin(claim_count_sq, claim_count_sq.c.source_id == Source.source_id)
        .order_by(Source.published_at.desc().nullslast())
        .all()
    )

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


# ---------------------------------------------------------------------------
# Faces gallery — Slice A of the cluster-manager work. Read-only triage view
# over the existing face-track JSON; no new schema. The endpoints here let
# the /wiki/source/{id}/faces page render face thumbnails grouped by who
# they were attributed to during visual ID, including a NULL bucket for the
# unassigned faces. Embeddings aren't persisted yet, so genuine clustering
# of unassigned faces (Slice B) lives behind a future schema change.
# ---------------------------------------------------------------------------

# Fewer samples per group than the JSON has, since each thumbnail is one
# worker round-trip + ffmpeg crop. 12 reads as "enough variety to spot a
# pattern" without making the page take 30 s to fully populate.
_FACE_GROUP_SAMPLE_LIMIT = 12


def _aggregate_face_groups(face_track: dict) -> list[dict]:
    """Walk every face detection, bucket by (matched) ``person_id`` with
    NULL going to a single 'unassigned' group, and pick representative
    samples evenly distributed across the source duration.

    Sampling strategy: divide the video into ``_FACE_GROUP_SAMPLE_LIMIT``
    equal-time bins; per bin pick the highest-``det_score`` face from
    that group. Skips empty bins, so short groups produce fewer
    thumbnails — that's fine, the gallery just shows what exists.
    """
    duration = max(0.001, float(face_track.get("duration_seconds") or 1.0))

    # First pass: collect every detection per group.
    by_group: dict[str | None, list[dict]] = {}
    for frame in face_track.get("frames", []):
        ts = float(frame.get("ts") or 0.0)
        for face in frame.get("faces", []):
            pid = face.get("person_id")
            entry = {
                "ts": ts,
                "bbox": face["bbox"],
                "det_score": float(face.get("det_score") or 0.0),
                "similarity": face.get("similarity"),
            }
            by_group.setdefault(pid, []).append(entry)

    # Second pass: sample + summarise. Sorted so the largest groups
    # render first in the UI.
    out: list[dict] = []
    for pid, entries in sorted(by_group.items(), key=lambda kv: -len(kv[1])):
        bin_count = _FACE_GROUP_SAMPLE_LIMIT
        bins: list[dict | None] = [None] * bin_count
        for e in entries:
            idx = min(bin_count - 1, int(bin_count * e["ts"] / duration))
            current = bins[idx]
            if current is None or e["det_score"] > current["det_score"]:
                bins[idx] = e
        samples = [b for b in bins if b is not None]

        sims = [e["similarity"] for e in entries if e["similarity"] is not None]
        scores = [e["det_score"] for e in entries]
        out.append({
            "person_id": pid,
            "detection_count": len(entries),
            "avg_det_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
            "avg_similarity": round(sum(sims) / len(sims), 3) if sims else None,
            "samples": samples,
        })
    return out


@router.get("/sources/{source_id}/face-groups")
def get_face_groups(source_id: uuid.UUID, db: Session = Depends(get_db)):
    """Aggregate the source's face-track JSON into per-Person groups for
    the gallery view. One group per matched ``person_id`` plus a
    ``person_id=null`` 'unassigned' bucket. Samples are JSON
    ``{ts, bbox, det_score}`` pointers — the actual thumbnail bytes are
    served on demand by ``/face-crop``.
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

    try:
        face_track = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"Face-track JSON malformed: {exc}")

    groups = _aggregate_face_groups(face_track)

    # Look up Person canonical names for the matched groups in one query
    # rather than N. The unassigned bucket has person_id=None.
    matched_ids = [uuid.UUID(g["person_id"]) for g in groups if g["person_id"]]
    name_by_id: dict[str, str] = {}
    if matched_ids:
        for p in db.query(Person).filter(Person.person_id.in_(matched_ids)).all():
            name_by_id[str(p.person_id)] = p.canonical_name

    enriched = []
    total = 0
    for g in groups:
        total += g["detection_count"]
        enriched.append({
            "person_id": g["person_id"],
            "person_name": name_by_id.get(g["person_id"]) if g["person_id"] else None,
            "detection_count": g["detection_count"],
            "avg_det_score": g["avg_det_score"],
            "avg_similarity": g["avg_similarity"],
            "samples": g["samples"],
        })

    return {
        "source_id": str(source_id),
        "duration_seconds": face_track.get("duration_seconds"),
        "frame_width": face_track.get("frame_width"),
        "frame_height": face_track.get("frame_height"),
        "total_faces": total,
        "groups": enriched,
    }


@router.get("/sources/{source_id}/face-crop")
def get_face_crop(
    source_id: uuid.UUID,
    ts: float,
    bbox: str,
    db: Session = Depends(get_db),
):
    """Return a JPEG cropped to ``bbox`` at ``ts``. ``bbox`` is the
    comma-separated ``x1,y1,x2,y2`` in source-frame pixels.

    Backed by the same worker plumbing as reassign — yt-dlp section
    path for YouTube sources, LRU-cached S3 mp4 otherwise. The crop
    happens in ffmpeg on the worker so the API container stays free of
    cv2 / PIL.
    """
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.video_s3_key and not (
        source.source_type == "youtube" and source.canonical_url
    ):
        raise HTTPException(
            status_code=400,
            detail="Source has no pixels available (no video_s3_key, not a YouTube source)",
        )

    parts = bbox.split(",")
    if len(parts) != 4:
        raise HTTPException(
            status_code=400,
            detail="bbox must be 'x1,y1,x2,y2'",
        )
    try:
        bbox_t = (float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]))
    except ValueError:
        raise HTTPException(status_code=400, detail="bbox values must be numeric")
    if bbox_t[2] <= bbox_t[0] or bbox_t[3] <= bbox_t[1]:
        raise HTTPException(status_code=400, detail="bbox must satisfy x2>x1, y2>y1")

    with tempfile.TemporaryDirectory(prefix="jeromelu-face-crop-") as tmp:
        crop_path = Path(tmp) / "crop.jpg"
        try:
            if source.source_type == "youtube" and source.canonical_url:
                fetch_frame_to(
                    crop_path,
                    canonical_url=source.canonical_url,
                    persistent_video_s3_key=source.video_s3_key,
                    ts=ts,
                    prefer_section=True,
                    bbox=bbox_t,
                )
            else:
                fetch_frame_to(
                    crop_path,
                    persistent_video_s3_key=source.video_s3_key,
                    ts=ts,
                    bbox=bbox_t,
                )
        except VideoWorkerError as exc:
            raise HTTPException(status_code=502, detail=str(exc))

        return Response(
            content=crop_path.read_bytes(),
            media_type="image/jpeg",
            # Crops are immutable for a given (source, ts, bbox) — the
            # face-track is versioned, so the bbox doesn't change. A long
            # browser cache means scrolling back to a group doesn't
            # re-hit the worker.
            headers={"Cache-Control": "public, max-age=86400"},
        )


@router.post("/sources/{source_id}/face-clusters/recompute")
def recompute_face_clusters(source_id: uuid.UUID, db: Session = Depends(get_db)):
    """Re-run per-source face clustering AND auto-tagging.

    Two-pass:
      1. ``cluster_source_detections`` — HDBSCAN over embeddings,
         writes ``source_face_detections.cluster_id``.
      2. ``analyse_clusters`` — per-cluster stats + heuristic
         ``detected_kind`` (person / portrait / noise), upserts
         ``source_face_clusters`` rows. Operator overrides in
         ``kind`` / ``label`` / ``notes`` are preserved across re-runs.

    Idempotent. Returns both summaries so the caller can sanity-check.
    """
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    stats = cluster_source_detections(db, source_id)
    analyses = analyse_clusters(db, source_id)
    kind_counts: dict[str, int] = {}
    for a in analyses:
        kind_counts[a.detected_kind] = kind_counts.get(a.detected_kind, 0) + 1
    return {
        "source_id": str(stats.source_id),
        "n_detections": stats.n_detections,
        "n_clusters": stats.n_clusters,
        "n_noise": stats.n_noise,
        "cluster_sizes": stats.cluster_sizes,
        "auto_tags": kind_counts,
    }


class MoveRunRequest(BaseModel):
    source_cluster_id: int = Field(
        ...,
        description="The cluster the run currently belongs to.",
    )
    target_cluster_id: int = Field(
        ...,
        description="Where to move the run's detections. Must already exist for this source.",
    )
    start_ts: float = Field(..., ge=0.0)
    end_ts: float = Field(..., gt=0.0)


@router.post("/sources/{source_id}/face-runs/move-run")
def move_run_between_clusters(
    source_id: uuid.UUID,
    body: MoveRunRequest,
    db: Session = Depends(get_db),
):
    """Move every detection in [start_ts, end_ts] from
    ``source_cluster_id`` into ``target_cluster_id``.

    Use case: HDBSCAN occasionally puts a short stretch of frames into
    the wrong cluster (a profile shot of host A grouped with host B
    because the angle made them look similar). The operator spots it
    in the runs view, picks the right target cluster, and one click
    moves the run.

    Both clusters must already exist for this source — we never
    invent a new cluster_id here. The detection_count on both
    source_face_clusters rows is updated so the runs view reflects
    the new sizes without a full re-analyse.
    """
    if body.end_ts <= body.start_ts:
        raise HTTPException(
            status_code=400, detail="end_ts must be greater than start_ts",
        )
    if body.source_cluster_id == body.target_cluster_id:
        raise HTTPException(
            status_code=400,
            detail="source and target cluster are the same — nothing to move",
        )

    src_meta = db.query(SourceFaceCluster).filter(
        SourceFaceCluster.source_id == source_id,
        SourceFaceCluster.cluster_id == body.source_cluster_id,
    ).first()
    tgt_meta = db.query(SourceFaceCluster).filter(
        SourceFaceCluster.source_id == source_id,
        SourceFaceCluster.cluster_id == body.target_cluster_id,
    ).first()
    if not src_meta:
        raise HTTPException(
            status_code=404,
            detail=f"source cluster {body.source_cluster_id} not found for this source",
        )
    if not tgt_meta:
        raise HTTPException(
            status_code=404,
            detail=f"target cluster {body.target_cluster_id} not found for this source",
        )

    moved = db.execute(
        sa_update(SourceFaceDetection)
        .where(
            SourceFaceDetection.source_id == source_id,
            SourceFaceDetection.cluster_id == body.source_cluster_id,
            SourceFaceDetection.frame_ts >= body.start_ts,
            SourceFaceDetection.frame_ts <= body.end_ts,
        )
        .values(cluster_id=body.target_cluster_id)
    ).rowcount or 0

    # Adjust the cached counts on both clusters so the next /face-runs
    # call shows the right sizes. The full stats (mouth_open_std, etc)
    # are stale until the next analyse — that's fine, they're advisory.
    if moved:
        src_meta.detection_count = max(0, (src_meta.detection_count or 0) - moved)
        tgt_meta.detection_count = (tgt_meta.detection_count or 0) + moved
        src_meta.updated_at = datetime.now(timezone.utc)
        tgt_meta.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "source_id": str(source_id),
        "source_cluster_id": body.source_cluster_id,
        "target_cluster_id": body.target_cluster_id,
        "moved_detections": moved,
    }


class ClusterOverrideRequest(BaseModel):
    kind: str | None = Field(
        default=None,
        description="Override the auto-detected kind. 'person' / 'portrait' / 'noise' or null to clear.",
    )
    label: str | None = Field(
        default=None,
        max_length=200,
        description="Friendly name override (e.g. 'Wall portrait — Brad Fittler'). Null to clear.",
    )
    excluded: bool | None = Field(
        default=None,
        description="Override the auto-excluded flag. Null = leave as-is.",
    )
    notes: str | None = Field(default=None, max_length=2000)


@router.post("/sources/{source_id}/face-clusters/{cluster_id}")
def override_face_cluster(
    source_id: uuid.UUID,
    cluster_id: int,
    body: ClusterOverrideRequest,
    db: Session = Depends(get_db),
):
    """Operator override on a cluster's metadata. Used to mark wall
    portraits as ``kind='portrait', excluded=true`` or to give a
    real-person cluster a friendly label before bulk-assign.

    Validates that the cluster exists for this source. Only the fields
    present in the request body are touched — null means "leave as-is",
    NOT "clear to null" (use an explicit empty-string label to clear).
    """
    row = db.query(SourceFaceCluster).filter(
        SourceFaceCluster.source_id == source_id,
        SourceFaceCluster.cluster_id == cluster_id,
    ).first()
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No cluster {cluster_id} for source {source_id}",
        )

    if body.kind is not None:
        if body.kind not in ("person", "portrait", "noise"):
            raise HTTPException(
                status_code=400,
                detail="kind must be 'person', 'portrait', or 'noise'",
            )
        row.kind = body.kind
    if body.label is not None:
        row.label = body.label or None  # empty string clears
    if body.excluded is not None:
        row.excluded = body.excluded
    if body.notes is not None:
        row.notes = body.notes or None

    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "source_id": str(row.source_id),
        "cluster_id": row.cluster_id,
        "kind": row.kind,
        "label": row.label,
        "excluded": row.excluded,
        "notes": row.notes,
        "detected_kind": row.detected_kind,
    }


@router.get("/sources/{source_id}/face-runs")
def get_face_runs(
    source_id: uuid.UUID,
    include_excluded: bool = False,
    db: Session = Depends(get_db),
):
    """Return per-position runs of contiguous attribution for the
    Faces tab. Each run is one row in the UI: a stretch of frames at
    the same on-screen position (or face cluster, post-Slice-B) with
    the same matched ``person_id``.

    Two code paths:

    - **Cluster-backed** (Slice B): when ``source_face_detections``
      has rows for this source, runs are grouped by ``cluster_id`` —
      each "position" in the response is one face cluster (visual
      identity). If detections exist but cluster_id is NULL on all of
      them (clustering hasn't run yet), the endpoint lazily kicks off
      clustering before returning.
    - **Spatial fallback** (Slice A.5): no detections persisted →
      legacy face-track JSON path that groups detections by bbox
      centre and breaks runs on matched_person_id change. Same wire
      shape, just less precise (two people in one chair = one row).

    Both paths join each run to the source_speakers turns whose
    [start_ts, end_ts] overlaps it, so bulk-assign knows which turns
    to rewrite. ``speaker_label`` per turn (e.g. 'Speaker 0') is
    included for diarisation context.

    See [speaker-identification.md § Per-detection embeddings](../system/speaker-identification.md).
    """
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.audio_s3_key:
        raise HTTPException(status_code=404, detail="No audio key for source")

    # Cluster-backed path is the new default. Falls back to the
    # face-track JSON for sources that haven't been backfilled.
    duration_seconds: float | None = None
    frame_width: int | None = None
    frame_height: int | None = None
    if detections_exist(db, source_id):
        # Lazy cluster: if no detection has a cluster_id yet, run the
        # clustering pass on-the-fly so the first /face-runs hit after
        # a fresh backfill doesn't return a flat unclustered blob.
        unclustered_count = (
            db.query(func.count(SourceFaceDetection.detection_id))
            .filter(
                SourceFaceDetection.source_id == source_id,
                SourceFaceDetection.cluster_id.is_(None),
            )
            .scalar() or 0
        )
        total_count = (
            db.query(func.count(SourceFaceDetection.detection_id))
            .filter(SourceFaceDetection.source_id == source_id)
            .scalar() or 0
        )
        # All detections unclustered → first run; trigger clustering.
        # Some unclustered but not all → noise from a prior pass; leave
        # them as Outliers rather than re-clustering on every request.
        if total_count > 0 and unclustered_count == total_count:
            logger.info(
                "Source %s has detections but no clusters — running on-demand clustering",
                source_id,
            )
            cluster_source_detections(db, source_id)
            analyse_clusters(db, source_id)
        else:
            # Clustering already done, but the analyser may not have
            # run yet (e.g. detections landed before mig 054). Run it
            # if source_face_clusters is empty for this source.
            cluster_meta_count = (
                db.query(func.count())
                .select_from(SourceFaceCluster)
                .filter(SourceFaceCluster.source_id == source_id)
                .scalar() or 0
            )
            if cluster_meta_count == 0:
                logger.info(
                    "Source %s has clustering but no metadata — analysing now",
                    source_id,
                )
                analyse_clusters(db, source_id)

        runs_payload = compute_face_runs_from_detections(
            db, source_id, include_excluded=include_excluded,
        )
        # Try to read frame dims from the cached face-track JSON for
        # the response — the detections table doesn't store them.
        # If the JSON isn't there it's fine; the UI tolerates null.
        key = _face_track_key_from_audio(source.audio_s3_key)
        try:
            face_track = json.loads(download_raw(key))
            duration_seconds = face_track.get("duration_seconds")
            frame_width = face_track.get("frame_width")
            frame_height = face_track.get("frame_height")
        except Exception:
            pass
    else:
        key = _face_track_key_from_audio(source.audio_s3_key)
        try:
            body = download_raw(key)
        except Exception as exc:
            logger.warning("Face-track fetch failed for %s: %s", source_id, exc)
            raise HTTPException(status_code=404, detail="Face-track not found")
        try:
            face_track = json.loads(body)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=502, detail=f"Face-track JSON malformed: {exc}",
            )
        runs_payload = compute_face_runs(face_track)
        duration_seconds = face_track.get("duration_seconds")
        frame_width = face_track.get("frame_width")
        frame_height = face_track.get("frame_height")

    # Look up the source's document so we can find overlapping turns.
    doc = (
        db.query(SourceDocument)
        .filter(SourceDocument.source_id == source_id)
        .first()
    )
    turns = []
    if doc:
        turns = (
            db.query(SourceSpeaker)
            .filter(SourceSpeaker.document_id == doc.document_id)
            .order_by(SourceSpeaker.start_ts)
            .all()
        )

    # Names for every Person referenced — face-run person_ids, cluster
    # dominant person_ids, and turn speaker_person_ids — gathered in one
    # query.
    person_ids: set[uuid.UUID] = set()
    for pos in runs_payload["positions"]:
        if pos.get("dominant_person_id"):
            person_ids.add(uuid.UUID(pos["dominant_person_id"]))
        for run in pos["runs"]:
            if run["person_id"]:
                person_ids.add(uuid.UUID(run["person_id"]))
    for t in turns:
        if t.speaker_person_id:
            person_ids.add(t.speaker_person_id)
    name_by_id: dict[str, str] = {}
    if person_ids:
        for p in db.query(Person).filter(Person.person_id.in_(person_ids)).all():
            name_by_id[str(p.person_id)] = p.canonical_name

    def turns_overlapping(start: float, end: float) -> list[dict]:
        out: list[dict] = []
        for t in turns:
            if t.start_ts >= end or t.end_ts <= start:
                continue
            out.append({
                "segment_id": str(t.segment_id),
                "start_ts": float(t.start_ts),
                "end_ts": float(t.end_ts),
                "speaker_label": t.speaker_label,
                "speaker_person_id": str(t.speaker_person_id) if t.speaker_person_id else None,
                "speaker_person_name": (
                    name_by_id.get(str(t.speaker_person_id))
                    if t.speaker_person_id else None
                ),
                "match_method": t.match_method,
            })
        return out

    # Decorate runs with person names + overlapping turns. Also resolve
    # the cluster's dominant person_name from the same lookup.
    for pos in runs_payload["positions"]:
        pos["dominant_person_name"] = (
            name_by_id.get(pos["dominant_person_id"])
            if pos.get("dominant_person_id") else None
        )
        for run in pos["runs"]:
            run["person_name"] = (
                name_by_id.get(run["person_id"]) if run["person_id"] else None
            )
            run["overlapping_turns"] = turns_overlapping(run["start_ts"], run["end_ts"])

    return {
        "source_id": str(source_id),
        "duration_seconds": duration_seconds,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "positions": runs_payload["positions"],
        "excluded_count": runs_payload.get("excluded_count", 0),
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
    person_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "UUID of an existing Person to attribute this turn to. "
            "Mutually exclusive with `new_person_name` — exactly one must "
            "be provided."
        ),
    )
    new_person_name: str | None = Field(
        default=None,
        description=(
            "Canonical name for a new Person. If a Person with this "
            "canonical_name already exists (case-insensitive match), that "
            "Person is reused; otherwise a new `people` row is created "
            "with `canonical_name` set and all other fields at their "
            "defaults. Mutually exclusive with `person_id`."
        ),
    )
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


def _ndjson(event: dict) -> bytes:
    """Encode one stream event. NDJSON = one JSON object per line. The
    frontend consumes this with a ReadableStream + line splitter."""
    return (json.dumps(event) + "\n").encode("utf-8")


@router.post("/sources/{source_id}/speakers/{segment_id}/reassign")
def reassign_speaker(
    source_id: uuid.UUID,
    segment_id: uuid.UUID,
    body: ReassignRequest,
    db: Session = Depends(get_db),
):
    """Operator override: a face on the video overlay was misidentified.

    Returns an **NDJSON stream** (``application/x-ndjson``) — one JSON
    object per line, emitted as each substep completes. Lets the modal
    render a checklist that ticks through 'person → frame → face →
    voice → commit' in real time, instead of staring at a single
    spinner while a 30s S3 download blocks the response.

    Sync prelude (still raises HTTPException 4xx if invalid):
      - Source / speaker / person-field validation.
      - Person resolve — ``body.person_id`` (existing) or
        ``body.new_person_name`` (lookup-or-create by canonical_name,
        case-insensitive). Exactly one must be provided.

    Streamed steps (one ``{"step", "status", "detail"?}`` event each
    on start / done / skip / error):
      1. ``frame``  — pull a JPEG from the video at ``frame_ts``. Goes
         via the video-worker sidecar (yt-dlp section path for YouTube
         sources, LRU-cached S3 mp4 otherwise).
      2. ``face``   — InsightFace enrollment from the frame. ``skip`` if
         no face detected; the turn is still attributed.
      3. ``voice``  — pyannote voiceprint from the turn's audio span.
         ``skip`` if the turn is shorter than the embedder's minimum.
      4. ``commit`` — write ``source_speakers.speaker_person_id`` +
         ``match_method='manual'`` + ``match_confidence=1.0`` and commit.

    A terminal ``{"step": "result", "status": "done", "detail": {...}}``
    carries the final response payload (same shape as the pre-streaming
    return). Any unhandled exception emits ``{"status": "error"}`` and
    closes the stream.

    Idempotent on the SourceSpeaker update; embeddings are append-only —
    repeated clicks add more rows. That's intentional: every correction
    grows the registry. Person creation is idempotent: a second click
    with the same ``new_person_name`` reuses the first run's Person row.

    See [speaker-identification.md § Manual reassign](../system/speaker-identification.md).
    """
    # ---- Sync prelude: validate + resolve Person (fast, DB-only) -----
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

    if (body.person_id is None) == (body.new_person_name is None):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one of `person_id` or `new_person_name`",
        )

    person_created = False
    if body.person_id is not None:
        person = db.query(Person).filter(Person.person_id == body.person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")
    else:
        new_name = (body.new_person_name or "").strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="`new_person_name` is empty")
        if len(new_name) > 200:
            raise HTTPException(
                status_code=400,
                detail="`new_person_name` is too long (max 200 chars)",
            )
        person = (
            db.query(Person)
            .filter(func.lower(Person.canonical_name) == new_name.lower())
            .first()
        )
        if not person:
            person = Person(canonical_name=new_name)
            db.add(person)
            db.flush()  # populate person.person_id without committing
            person_created = True

    target_person_id = person.person_id
    person_name = person.canonical_name

    # Frame timestamp defaults to the middle of the speaker turn — that's
    # where the host is most likely to be on screen if the format is
    # multi-cam.
    frame_ts = body.frame_ts
    if frame_ts is None:
        frame_ts = (speaker.start_ts + speaker.end_ts) / 2.0

    # ---- Streamed work: frame fetch, enroll, commit ------------------

    def stream() -> Iterator[bytes]:
        face_id_written: uuid.UUID | None = None
        voice_rows_written = 0
        try:
            # The Person resolution is already done; tell the client up
            # front so the checklist starts populated.
            yield _ndjson({
                "step": "person",
                "status": "done",
                "detail": {
                    "person_id": str(target_person_id),
                    "person_name": person_name,
                    "person_created": person_created,
                },
            })

            # Step: video-worker frame fetch. Slowest substep on cold
            # cache; ~3s on yt-dlp section path, ~instant on cache hit.
            yield _ndjson({"step": "frame", "status": "start"})
            with tempfile.TemporaryDirectory(prefix="jeromelu-reassign-frame-") as ftmp:
                frame_path = Path(ftmp) / "frame.jpg"
                try:
                    _fetch_reassign_frame(source, frame_ts, frame_path)
                except HTTPException as exc:
                    yield _ndjson({
                        "step": "frame",
                        "status": "error",
                        "detail": str(exc.detail),
                    })
                    return
                yield _ndjson({"step": "frame", "status": "done"})

                # Step: InsightFace enrollment. Skipped (not failed) when
                # no face is detected — the turn is still attributed.
                yield _ndjson({"step": "face", "status": "start"})
                try:
                    face_id_written, _det, _area = enroll_face_from_image(
                        db,
                        person_id=target_person_id,
                        source_id=source_id,
                        image_path=frame_path,
                        frame_ts=frame_ts,
                        created_by="manual",
                    )
                    yield _ndjson({
                        "step": "face",
                        "status": "done",
                        "detail": {"face_embedding_id": str(face_id_written)},
                    })
                except VisualIdError as exc:
                    logger.warning("Face enrollment skipped during reassign: %s", exc)
                    yield _ndjson({
                        "step": "face",
                        "status": "skip",
                        "detail": str(exc),
                    })

            # Step: voiceprint enrollment from the turn's audio span.
            # Skipped when the turn is shorter than the embedder's min.
            yield _ndjson({"step": "voice", "status": "start"})
            try:
                result = enroll(
                    db,
                    person_id=target_person_id,
                    source_id=source_id,
                    start_ts=float(speaker.start_ts),
                    end_ts=float(speaker.end_ts),
                    created_by="manual",
                )
                voice_rows_written = result.voiceprints_written
                yield _ndjson({
                    "step": "voice",
                    "status": "done",
                    "detail": {"voiceprints_written": voice_rows_written},
                })
            except EnrollmentError as exc:
                logger.warning("Voiceprint enrollment skipped during reassign: %s", exc)
                yield _ndjson({
                    "step": "voice",
                    "status": "skip",
                    "detail": str(exc),
                })

            # Step: mark the turn manually corrected and commit. This
            # also flushes the new Person row (if any) durably.
            yield _ndjson({"step": "commit", "status": "start"})
            speaker.speaker_person_id = target_person_id
            speaker.match_method = "manual"
            speaker.match_confidence = 1.0
            db.commit()
            yield _ndjson({"step": "commit", "status": "done"})

            # Terminal event with the same shape as the legacy response.
            yield _ndjson({
                "step": "result",
                "status": "done",
                "detail": {
                    "segment_id": str(segment_id),
                    "person_id": str(target_person_id),
                    "person_name": person_name,
                    "person_created": person_created,
                    "face_embedding_id": str(face_id_written) if face_id_written else None,
                    "voiceprints_written": voice_rows_written,
                    "match_method": "manual",
                },
            })
        except Exception as exc:
            # Anything that escapes a step's own handler ends up here.
            # Roll back the session so a partial write doesn't persist,
            # then let the client know which step blew up.
            logger.exception("reassign stream failed")
            try:
                db.rollback()
            except Exception:
                pass
            yield _ndjson({
                "step": "unknown",
                "status": "error",
                "detail": f"{type(exc).__name__}: {exc}",
            })

    return StreamingResponse(stream(), media_type="application/x-ndjson")


# ---------------------------------------------------------------------------
# Bulk reassign — Slice A.5. The Faces tab's runs view collapses dozens of
# face-track frames into one row per material attribution change. When the
# operator picks a Person for a run, every source_speakers turn that
# overlaps the run gets reassigned in a single transaction. Same per-turn
# face + voice enrollment as single reassign — just N times in a loop.
# ---------------------------------------------------------------------------


#: Top-N detections by det_score copied from a cluster into the
#: person_face_embeddings registry on bulk-assign. More exemplars =
#: better same-condition recall, but at >20 the registry starts
#: ballooning per click. 10 buys variety without bloat.
CLUSTER_EMBEDDING_SAMPLE_LIMIT = 10


class BulkAssignRequest(BaseModel):
    segment_ids: list[uuid.UUID] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="source_speakers.segment_id values to reassign in this batch",
    )
    cluster_id: int | None = Field(
        default=None,
        description=(
            "Optional. When supplied, the bulk-assign uses the cluster's "
            "persisted face embeddings as exemplars instead of fetching a "
            "frame per turn and re-running InsightFace — cheaper + uses "
            "richer evidence (multiple detections per cluster). The "
            "cluster's source_face_detections rows are also updated to "
            "attribute to the target Person."
        ),
    )
    person_id: uuid.UUID | None = Field(
        default=None,
        description="Existing Person to attribute every turn to.",
    )
    new_person_name: str | None = Field(
        default=None,
        max_length=200,
        description="Lookup-or-create a Person by canonical_name. Mutually exclusive with person_id.",
    )


@router.post("/sources/{source_id}/face-runs/assign")
def bulk_assign_face_run(
    source_id: uuid.UUID,
    body: BulkAssignRequest,
    db: Session = Depends(get_db),
):
    """Bulk reassign every source_speakers turn in ``body.segment_ids``
    to the same target Person. Used by the Faces tab when the operator
    confirms a face-position run belongs to a known speaker.

    Streams ``application/x-ndjson`` like the single reassign endpoint.
    Events:

      ``person`` done           — Person resolved (created if needed).
      ``turn`` start/done/error — one pair per segment_id, in order.
      ``commit`` start/done     — single end-of-batch commit so partial
                                  failures roll back ALL writes.
      ``result`` done           — totals across the batch.

    The whole batch is one transaction. If turn N fails mid-stream, the
    handler emits a ``turn`` error event, then rolls back — turns 1..N-1
    are not persisted. Idempotent retries are safe: the new-Person path
    reuses an existing row by canonical name, and SourceSpeaker updates
    are pure overwrites.
    """
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.video_s3_key and not (
        source.source_type == "youtube" and source.canonical_url
    ):
        raise HTTPException(
            status_code=400,
            detail="Source has no video_s3_key and no YouTube URL — face reassign needs pixels",
        )
    if (body.person_id is None) == (body.new_person_name is None):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one of `person_id` or `new_person_name`",
        )

    # Resolve Person (sync) — commit the new row up front rather than
    # relying on db.flush() to keep it visible. enroll_face_from_image
    # and enroll() each run their own session.commit() inside the
    # stream; across a multi-turn bulk those internal commits can
    # leave the session in a state where a flushed-only Person row
    # isn't visible to subsequent FK checks, producing
    # ForeignKeyViolation on person_face_embeddings. Committing here
    # decouples Person creation from the per-turn writes — a partial
    # bulk failure leaves an empty Person, which is harmless and
    # idempotent on re-run (lookup-by-name reuses the row).
    person_created = False
    if body.person_id is not None:
        person = db.query(Person).filter(Person.person_id == body.person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")
    else:
        new_name = (body.new_person_name or "").strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="`new_person_name` is empty")
        person = (
            db.query(Person)
            .filter(func.lower(Person.canonical_name) == new_name.lower())
            .first()
        )
        if not person:
            person = Person(canonical_name=new_name)
            db.add(person)
            db.commit()
            person_created = True
    target_person_id = person.person_id
    person_name = person.canonical_name

    # Validate every requested segment exists + belongs to this source.
    # Doing this up-front (before any worker calls) means malformed input
    # surfaces as 4xx instead of mid-stream.
    doc = db.query(SourceDocument).filter(SourceDocument.source_id == source_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Source has no document")
    speakers = (
        db.query(SourceSpeaker)
        .filter(
            SourceSpeaker.document_id == doc.document_id,
            SourceSpeaker.segment_id.in_(body.segment_ids),
        )
        .all()
    )
    seen = {sp.segment_id for sp in speakers}
    missing = [sid for sid in body.segment_ids if sid not in seen]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Speaker turn(s) not in this source: {missing[:5]}",
        )
    # Process in the request order so the client's progress UI lines up
    # with what it sent.
    speakers_by_id = {sp.segment_id: sp for sp in speakers}
    ordered = [speakers_by_id[sid] for sid in body.segment_ids]

    use_cluster = body.cluster_id is not None
    cluster_detections: list[SourceFaceDetection] = []
    if use_cluster:
        cluster_detections = (
            db.query(SourceFaceDetection)
            .filter(
                SourceFaceDetection.source_id == source_id,
                SourceFaceDetection.cluster_id == body.cluster_id,
            )
            .order_by(SourceFaceDetection.det_score.desc())
            .all()
        )
        if not cluster_detections:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No source_face_detections for cluster_id={body.cluster_id} "
                    f"in source {source_id}"
                ),
            )

    def stream() -> Iterator[bytes]:
        face_writes = 0
        voice_writes = 0
        try:
            yield _ndjson({
                "step": "person",
                "status": "done",
                "detail": {
                    "person_id": str(target_person_id),
                    "person_name": person_name,
                    "person_created": person_created,
                },
            })

            # Cluster mode (Slice B PR 2): the detections table already
            # holds high-quality embeddings for every face in this
            # cluster, so we copy the top-N as person_face_embeddings
            # exemplars instead of fetching frames + re-running
            # InsightFace per turn. Massive perf win (~3-5s saved per
            # turn) AND better evidence (multiple angles/lighting from
            # actual cluster members vs single midpoint frame).
            if use_cluster:
                yield _ndjson({
                    "step": "cluster_face",
                    "status": "start",
                    "detail": {
                        "cluster_id": body.cluster_id,
                        "available_detections": len(cluster_detections),
                    },
                })
                samples = cluster_detections[:CLUSTER_EMBEDDING_SAMPLE_LIMIT]
                exemplar_rows = [
                    PersonFaceEmbedding(
                        person_id=target_person_id,
                        source_id=source_id,
                        frame_ts=float(d.frame_ts),
                        embedding=list(d.embedding),
                        embedding_model=d.embedding_model,
                        created_by="manual",
                    )
                    for d in samples
                ]
                db.add_all(exemplar_rows)
                db.commit()
                face_writes += len(exemplar_rows)
                yield _ndjson({
                    "step": "cluster_face",
                    "status": "done",
                    "detail": {
                        "cluster_id": body.cluster_id,
                        "exemplars_written": len(exemplar_rows),
                    },
                })

            # Shared voice-enrollment setup. Without this every turn
            # would re-download the source's full m4a from S3 and
            # re-load the pyannote model — observed ~100s per turn,
            # roughly 25× the per-turn cost of the actual embedding.
            # The context tempdir holds the audio for the duration of
            # the bulk; each enroll_span_with_context only ffmpeg-crops
            # the turn's seconds and embeds the windows.
            with enrollment_context(db, source_id) as voice_ctx:
                for idx, sp in enumerate(ordered):
                    seg_id = str(sp.segment_id)
                    yield _ndjson({
                        "step": "turn",
                        "status": "start",
                        "detail": {
                            "index": idx,
                            "segment_id": seg_id,
                            "start_ts": float(sp.start_ts),
                            "end_ts": float(sp.end_ts),
                        },
                    })

                    # Per-turn face enrollment only when cluster mode is
                    # off — otherwise the cluster-face step above
                    # already wrote richer exemplars.
                    if use_cluster:
                        pass
                    else:
                        # Frame midpoint = where face is most likely to appear.
                        frame_ts = (float(sp.start_ts) + float(sp.end_ts)) / 2.0
                        with tempfile.TemporaryDirectory(prefix="jeromelu-bulk-frame-") as ftmp:
                            frame_path = Path(ftmp) / "frame.jpg"
                            try:
                                _fetch_reassign_frame(source, frame_ts, frame_path)
                            except HTTPException as exc:
                                yield _ndjson({
                                    "step": "turn",
                                    "status": "error",
                                    "detail": {
                                        "index": idx,
                                        "segment_id": seg_id,
                                        "stage": "frame",
                                        "error": str(exc.detail),
                                    },
                                })
                                db.rollback()
                                return

                            try:
                                face_id, _det, _area = enroll_face_from_image(
                                    db,
                                    person_id=target_person_id,
                                    source_id=source_id,
                                    image_path=frame_path,
                                    frame_ts=frame_ts,
                                    created_by="manual",
                                )
                                if face_id:
                                    face_writes += 1
                            except VisualIdError as exc:
                                # Same skip-not-fail policy as single reassign.
                                logger.warning(
                                    "Bulk face enrollment skipped for %s: %s", seg_id, exc
                                )

                    # Voiceprint enrollment from the turn's audio span,
                    # reusing the shared context (no audio re-download,
                    # no model re-load).
                    try:
                        result = enroll_span_with_context(
                            db,
                            voice_ctx,
                            person_id=target_person_id,
                            start_ts=float(sp.start_ts),
                            end_ts=float(sp.end_ts),
                            created_by="manual",
                        )
                        voice_writes += result.voiceprints_written
                    except EnrollmentError as exc:
                        logger.warning(
                            "Bulk voiceprint enrollment skipped for %s: %s", seg_id, exc
                        )

                # Mark the turn manually corrected. Commit per-turn so
                # the SourceSpeaker update is durable before we move on —
                # both enroll_face_from_image and enroll() internally
                # call session.commit() for their own writes, which in
                # this multi-turn loop was leaving the per-turn dirty
                # attribute change on `sp` unflushed even by subsequent
                # inner commits. The empirical result was a successful
                # batch that wrote 5 face embeddings + 27 voiceprints
                # but zero attributed turns — face/voice landed via the
                # inner commits while every sp update was lost. Per-turn
                # commit also means refreshing the Faces tab mid-bulk
                # reflects progress.
                sp.speaker_person_id = target_person_id
                sp.match_method = "manual"
                sp.match_confidence = 1.0
                db.commit()

                yield _ndjson({
                    "step": "turn",
                    "status": "done",
                    "detail": {
                        "index": idx,
                        "segment_id": seg_id,
                    },
                })

            # Cluster mode: re-attribute every detection in the cluster
            # so the next /face-runs call shows them as the new person
            # rather than the old (or NULL) one. Single bulk UPDATE.
            cluster_detections_updated = 0
            if use_cluster:
                cluster_detections_updated = db.execute(
                    sa_update(SourceFaceDetection)
                    .where(
                        SourceFaceDetection.source_id == source_id,
                        SourceFaceDetection.cluster_id == body.cluster_id,
                    )
                    .values(matched_person_id=target_person_id)
                ).rowcount or 0
                db.commit()

            yield _ndjson({"step": "commit", "status": "start"})
            # No-op safety commit — every turn already flushed. Kept so
            # the event sequence the frontend listens for stays stable
            # (commit start/done before result done).
            db.commit()
            yield _ndjson({"step": "commit", "status": "done"})

            yield _ndjson({
                "step": "result",
                "status": "done",
                "detail": {
                    "person_id": str(target_person_id),
                    "person_name": person_name,
                    "person_created": person_created,
                    "turns_updated": len(ordered),
                    "face_embeddings_written": face_writes,
                    "voiceprints_written": voice_writes,
                    "cluster_detections_updated": cluster_detections_updated,
                    "match_method": "manual",
                },
            })
        except Exception as exc:
            logger.exception("bulk reassign failed mid-stream")
            try:
                db.rollback()
            except Exception:
                pass
            yield _ndjson({
                "step": "unknown",
                "status": "error",
                "detail": f"{type(exc).__name__}: {exc}",
            })

    return StreamingResponse(stream(), media_type="application/x-ndjson")
