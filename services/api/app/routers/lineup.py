# ---------------------------------------------------------------------------
# LEGACY — speaker identification ("Lineup") is being moved out of this repo.
#
# Every endpoint below is part of the in-repo voice + face + fusion surface
# that will be replaced by an external Lineup API call. Keep this file
# functional (the live pipeline still depends on it) but do not invest in new
# features here. See `memory/project_lineup_external.md` and
# `docs/agents/system/speaker-identification.md`.
# ---------------------------------------------------------------------------

import bisect
import json
import logging
import tempfile
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, update as sa_update
from sqlalchemy.orm import Session

from app.analyst.face_clusters import analyse_clusters, cluster_source_detections
from app.analyst.face_runs import (
    compute_face_runs,
    compute_face_runs_from_detections,
    detections_exist,
)
from app.analyst.identify_voice import (
    EnrollmentError,
    enroll,
)
from app.analyst.identity_alignment import fetch_alignment
from app.analyst.face_segment_transcript_cli import (
    DEFAULT_MIN_SEGMENT_SECONDS as FACE_TX_DEFAULT_MIN_SEGMENT,
    DEFAULT_MOUTH_THRESHOLD as FACE_TX_DEFAULT_MOUTH,
    DEFAULT_SMOOTH_GAP_SECONDS as FACE_TX_DEFAULT_SMOOTH,
    segment_by_face,
)
from app.analyst.voice_cluster_hdbscan import VoiceClusterParams
from app.analyst.voice_cluster_runner import recluster_source_voice
from app.analyst.voice_clusters import (
    VOICEPRINT_SAMPLE_LIMIT,
    compute_voice_clusters,
)
from app.analyst.video_worker_client import VideoWorkerError, fetch_frame_to
from app.analyst.visual_id import (
    VisualIdError,
    enroll_face_from_image,
    regenerate_face_track_json_from_detections,
)
from jeromelu_shared.db import (
    Person,
    PersonFaceEmbedding,
    PersonVoiceprint,
    Source,
    SourceDocument,
    SourceFaceCluster,
    SourceFaceDetection,
    SourceSpeaker,
)
from jeromelu_shared.s3 import download_raw

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
    source_cluster_id: int | None = Field(
        ...,
        description=(
            "The cluster the run currently belongs to. `null` means the "
            "Outliers bucket (HDBSCAN noise — detections with cluster_id "
            "IS NULL), used when promoting a salvaged stretch out of "
            "noise into a real cluster."
        ),
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
    because the angle made them look similar), or drops them into noise
    when the embedding doesn't cleanly join any cluster. The operator
    spots either case in the runs view, picks the right target, and one
    click moves the run.

    Target cluster must already exist; source can be ``null`` to move
    from the Outliers bucket. ``source_face_clusters.detection_count``
    is updated on both sides so the runs view reflects the new sizes
    without a full re-analyse — the Outliers bucket has no row of its
    own, so only the target's count is incremented in that case.
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

    # source_cluster_id=None → Outliers bucket. No source_face_clusters
    # row exists for noise, so skip the lookup and the count-decrement.
    src_meta: SourceFaceCluster | None = None
    if body.source_cluster_id is not None:
        src_meta = db.query(SourceFaceCluster).filter(
            SourceFaceCluster.source_id == source_id,
            SourceFaceCluster.cluster_id == body.source_cluster_id,
        ).first()
        if not src_meta:
            raise HTTPException(
                status_code=404,
                detail=f"source cluster {body.source_cluster_id} not found for this source",
            )

    tgt_meta = db.query(SourceFaceCluster).filter(
        SourceFaceCluster.source_id == source_id,
        SourceFaceCluster.cluster_id == body.target_cluster_id,
    ).first()
    if not tgt_meta:
        raise HTTPException(
            status_code=404,
            detail=f"target cluster {body.target_cluster_id} not found for this source",
        )

    # SQLAlchemy's `column == None` would warn; use `.is_(None)` for the
    # Outliers (noise) bucket and direct equality otherwise.
    src_cluster_predicate = (
        SourceFaceDetection.cluster_id.is_(None)
        if body.source_cluster_id is None
        else SourceFaceDetection.cluster_id == body.source_cluster_id
    )
    moved = db.execute(
        sa_update(SourceFaceDetection)
        .where(
            SourceFaceDetection.source_id == source_id,
            src_cluster_predicate,
            SourceFaceDetection.frame_ts >= body.start_ts,
            SourceFaceDetection.frame_ts <= body.end_ts,
        )
        .values(cluster_id=body.target_cluster_id)
    ).rowcount or 0

    # Adjust the cached counts so the next /face-runs call shows the
    # right sizes. The full stats (mouth_open_std, etc) are stale until
    # the next analyse — that's fine, they're advisory.
    if moved:
        if src_meta is not None:
            src_meta.detection_count = max(0, (src_meta.detection_count or 0) - moved)
            src_meta.updated_at = datetime.now(timezone.utc)
        tgt_meta.detection_count = (tgt_meta.detection_count or 0) + moved
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
        # Cache-Control: no-cache → browser revalidates every fetch.
        # Necessary so the overlay picks up regenerated face-track JSON
        # immediately after a bulk-assign instead of waiting out a TTL.
        # The JSON is small (~5 MB) and only loaded once per page view,
        # so the always-revalidate cost is negligible. ETag-based
        # revalidation would be a future optimisation if this becomes hot.
        headers={"Cache-Control": "no-cache"},
    )


@router.post("/sources/{source_id}/face-track/regenerate")
def regenerate_face_track(source_id: uuid.UUID, db: Session = Depends(get_db)):
    """Rebuild the cached face-track JSON in S3 from the current
    ``source_face_detections`` state.

    Use cases:
      - Manual recovery when a bulk-assign's inline regen failed.
      - Retroactive fix for sources assigned before the inline regen
        was wired in (i.e. anything attributed before commit ade028a).

    Idempotent: re-running on a source already in sync is harmless;
    the JSON is byte-identical except for embedding-order ties.
    """
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.audio_s3_key:
        raise HTTPException(status_code=400, detail="Source has no audio_s3_key")

    try:
        key = regenerate_face_track_json_from_detections(db, source_id)
    except Exception as exc:
        logger.exception("Manual face-track regen failed for %s", source_id)
        raise HTTPException(
            status_code=500,
            detail=f"Regen failed: {type(exc).__name__}: {exc}",
        ) from exc
    if not key:
        # Helper returns None when there's no cached JSON to base
        # metadata off, or no detections to write. Both are operator-
        # actionable — surface as 404 rather than a confusing 200/null.
        raise HTTPException(
            status_code=404,
            detail=(
                "No face-track JSON or no detections to regenerate from. "
                "Run visual_identify first."
            ),
        )

    distinct_persons = (
        db.query(SourceFaceDetection.matched_person_id)
        .filter(
            SourceFaceDetection.source_id == source_id,
            SourceFaceDetection.matched_person_id.isnot(None),
        )
        .distinct()
        .count()
    )
    detection_count = (
        db.query(func.count(SourceFaceDetection.detection_id))
        .filter(SourceFaceDetection.source_id == source_id)
        .scalar() or 0
    )
    return {
        "source_id": str(source_id),
        "face_track_s3_key": key,
        "detections": detection_count,
        "distinct_persons": distinct_persons,
    }


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
        # Cluster-level assigns regularly hit hundreds of overlapping
        # turns when one person dominates a long source (e.g. a 50-min
        # podcast where the host speaks across 510 source_speakers
        # rows). 2000 covers real-world ceiling with plenty of headroom;
        # raise further only when we genuinely see clusters that big.
        max_length=2000,
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
    confirms a cluster belongs to a known speaker.

    SQL-only flow — no per-turn loop, no per-turn worker calls.

      ``person`` done             — Person resolved (created if needed).
      ``cluster_face`` start/done — Copy up to N detection embeddings
                                    into person_face_embeddings as
                                    exemplars (cluster mode only).
      ``attribute`` start/done    — One UPDATE on source_speakers for
                                    every segment_id in the batch.
      ``commit`` start/done       — Single transaction commit.
      ``result`` done             — Totals across the batch.

    The whole batch is one transaction. Idempotent retries are safe:
    the new-Person path reuses an existing row by canonical name, and
    SourceSpeaker updates are pure overwrites.

    Voice enrollment is intentionally **NOT** done here. Per-turn
    voice enrollment over a 510-segment cluster produces 3,000-8,000
    voiceprints — way over the kNN registry's useful scale — and was
    the dominant cost in earlier iterations. A separate voice-focused
    workflow will sample a handful of representative turns per
    cluster-assign in a future change.
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

            # ---- Face exemplars (cluster mode only) -----------------
            # The detections table already holds high-quality embeddings
            # for every face in the cluster. We copy the top-N by
            # det_score into person_face_embeddings as exemplars —
            # cheaper and richer evidence than running InsightFace at
            # each turn's midpoint (which often catches the wrong
            # person on screen anyway).
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
                face_writes = len(exemplar_rows)
                yield _ndjson({
                    "step": "cluster_face",
                    "status": "done",
                    "detail": {
                        "cluster_id": body.cluster_id,
                        "exemplars_written": face_writes,
                    },
                })

            # ---- Bulk SP attribution --------------------------------
            # Replaces the previous per-turn loop. One UPDATE statement,
            # all segment_ids at once. The earlier implementation
            # iterated turns and ran voice enrollment per turn — for a
            # 510-segment cluster that was ~5 minutes of pyannote work
            # to produce 3,000-8,000 voiceprints, way over the registry's
            # useful kNN scale. Voice enrollment from cluster assigns is
            # deferred to a dedicated voice-focused pass; see
            # speaker-identification.md § Bulk-assign.
            yield _ndjson({"step": "attribute", "status": "start"})
            turns_updated = db.execute(
                sa_update(SourceSpeaker)
                .where(
                    SourceSpeaker.segment_id.in_(body.segment_ids),
                )
                .values(
                    speaker_person_id=target_person_id,
                    match_method="manual",
                    match_confidence=1.0,
                )
            ).rowcount or 0
            yield _ndjson({
                "step": "attribute",
                "status": "done",
                "detail": {"turns_updated": turns_updated},
            })

            # ---- Cluster-wide detection attribution -----------------
            # Updates matched_person_id on every detection in the
            # cluster so the next /face-runs call shows them as the new
            # person. Cheap UPDATE; runs only in cluster mode.
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

            # Also stamp source_face_clusters.attributed_person_id so
            # the cluster table is consistent with the detections.
            if use_cluster:
                db.execute(
                    sa_update(SourceFaceCluster)
                    .where(
                        SourceFaceCluster.source_id == source_id,
                        SourceFaceCluster.cluster_id == body.cluster_id,
                    )
                    .values(
                        attributed_person_id=target_person_id,
                        updated_at=datetime.now(timezone.utc),
                    )
                )

            # ---- Commit ---------------------------------------------
            yield _ndjson({"step": "commit", "status": "start"})
            db.commit()
            yield _ndjson({"step": "commit", "status": "done"})

            # ---- Regenerate face-track JSON -------------------------
            # The DB is the source of truth for attribution, but the
            # YouTube overlay reads the cached face-track JSON in S3.
            # If this regen fails the operator must know — silently
            # logging a warning is what produced 2026-05-11's stale-JSON
            # incident where a manually-assigned cluster showed "?" in
            # the overlay even though the DB had it correctly attributed.
            #
            # Treated as a real stream step. On failure: surface the
            # error and stop emitting result — the assign succeeded in
            # the DB but the UI must trigger a retry via the standalone
            # /face-track/regenerate endpoint before the overlay is
            # consistent again.
            yield _ndjson({"step": "regen_face_track", "status": "start"})
            try:
                regenerate_face_track_json_from_detections(db, source_id)
            except Exception as exc:
                logger.exception(
                    "Face-track JSON regen failed for %s after bulk-assign",
                    source_id,
                )
                yield _ndjson({
                    "step": "regen_face_track",
                    "status": "error",
                    "detail": (
                        f"{type(exc).__name__}: {exc}. DB updated; retry via "
                        f"POST /api/sources/{source_id}/face-track/regenerate "
                        "to refresh the overlay."
                    ),
                })
                return
            yield _ndjson({"step": "regen_face_track", "status": "done"})

            yield _ndjson({
                "step": "result",
                "status": "done",
                "detail": {
                    "person_id": str(target_person_id),
                    "person_name": person_name,
                    "person_created": person_created,
                    "turns_updated": turns_updated,
                    "face_embeddings_written": face_writes,
                    "voiceprints_written": 0,  # voice enrollment deferred — see docstring
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


# ---------------------------------------------------------------------------
# Voice clusters — the speaker-label equivalent of the face-runs surface.
#
# Pyannote already tags every source_speakers row with a per-source cluster
# label (SPEAKER_00 / SPEAKER_01 / ...). The /voice-clusters endpoint is a
# pure aggregation over that — no clustering pass to run, no embedding-matrix
# load. The /voice-clusters/{label}/assign endpoint mirrors face-runs/assign:
# resolve/create a Person, copy a handful of representative medoid embeddings
# from source_speakers.embedding into person_voiceprints (so the registry
# grows from this assign too), then bulk-UPDATE source_speakers in one SQL
# statement.
# ---------------------------------------------------------------------------


@router.get("/sources/{source_id}/voice-clusters")
def get_voice_clusters(source_id: uuid.UUID, db: Session = Depends(get_db)):
    """List the pyannote voice clusters for this source, with per-cluster
    summary stats and the current dominant attribution.

    Resolves ``dominant_person_name`` for each cluster in a single Person
    query — same pattern as ``/face-runs``. Returns ``{speakers: [...]}``
    sorted by total airtime descending.
    """
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    payload = compute_voice_clusters(db, source_id)

    person_ids: set[uuid.UUID] = set()
    for sp in payload["speakers"]:
        if sp.get("dominant_person_id"):
            person_ids.add(uuid.UUID(sp["dominant_person_id"]))
    name_by_id: dict[str, str] = {}
    if person_ids:
        for p in db.query(Person).filter(Person.person_id.in_(person_ids)).all():
            name_by_id[str(p.person_id)] = p.canonical_name

    for sp in payload["speakers"]:
        sp["dominant_person_name"] = (
            name_by_id.get(sp["dominant_person_id"])
            if sp.get("dominant_person_id") else None
        )

    return {
        "source_id": str(source_id),
        "speakers": payload["speakers"],
    }


class VoiceClusterAssignRequest(BaseModel):
    person_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Existing Person to attribute every turn in the cluster to. "
            "Mutually exclusive with ``new_person_name``."
        ),
    )
    new_person_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description=(
            "Canonical name of a Person to create (or reuse, case-insensitive). "
            "Mutually exclusive with ``person_id``."
        ),
    )


@router.post("/sources/{source_id}/voice-clusters/{speaker_label}/assign")
def bulk_assign_voice_cluster(
    source_id: uuid.UUID,
    speaker_label: str,
    body: VoiceClusterAssignRequest,
    db: Session = Depends(get_db),
):
    """Bulk-attribute every ``source_speakers`` row with the given
    ``speaker_label`` to a single Person, and seed the voiceprint registry
    from a handful of representative turns in the cluster.

    SQL-only flow — no audio re-fetch, no per-turn pyannote pass.

      ``person`` done             — Person resolved (created if needed).
      ``voice_enrol`` start/done  — Copy up to ``VOICEPRINT_SAMPLE_LIMIT``
                                    medoid embeddings from
                                    ``source_speakers.embedding`` into
                                    ``person_voiceprints``. ``skip`` event
                                    when the cluster has no non-NULL
                                    embedding rows (all turns were
                                    sub-300ms).
      ``attribute`` start/done    — One UPDATE on source_speakers,
                                    WHERE document_id=… AND speaker_label=…
      ``commit`` start/done       — Single transaction commit.
      ``result`` done             — Totals across the batch.

    Voice enrolment from the per-turn medoid (vs the original sliding-window
    extraction in ``enroll_voice_cli``) is intentional: the medoid is already
    in the DB after diarisation, it's the same wespeaker model the matcher
    uses, and the per-window-vote machinery downstream is robust to medoid
    granularity. This keeps the assign action instant — the equivalent of
    face-runs/assign's "copy top-N detections into person_face_embeddings".
    """
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if (body.person_id is None) == (body.new_person_name is None):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one of `person_id` or `new_person_name`",
        )

    doc = (
        db.query(SourceDocument)
        .filter(SourceDocument.source_id == source_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Source has no document")

    # Pre-check: cluster must have at least one turn. Validate before the
    # stream starts so malformed input surfaces as 4xx, not mid-stream.
    # Match by ``coalesce(cluster_label, speaker_label)`` so the same
    # endpoint accepts HDBSCAN-emitted labels (``H00``, ``H01``, …) and
    # pyannote raw labels (``SPEAKER_NN``) without the frontend having
    # to know which one it's looking at.
    effective_label = func.coalesce(
        SourceSpeaker.cluster_label, SourceSpeaker.speaker_label,
    )
    cluster_turn_count = (
        db.query(func.count(SourceSpeaker.segment_id))
        .filter(
            SourceSpeaker.document_id == doc.document_id,
            effective_label == speaker_label,
        )
        .scalar() or 0
    )
    if cluster_turn_count == 0:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No source_speakers rows for label={speaker_label!r} in "
                f"source {source_id}"
            ),
        )

    # Resolve Person up-front and commit. enroll-voice-cli flushed-only
    # rows have hit FK violation in cross-session bulk paths before; the
    # face-runs/assign endpoint solved this by committing the new Person
    # before any per-turn writes. Mirror the same pattern.
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

    # Pick the medoid embeddings to promote — longest turns first, on the
    # assumption that longer spans give cleaner, less-overlapped acoustic
    # exemplars. Filtered to rows with non-NULL embedding so the
    # sub-300ms-turn NULLs (see speaker-identification.md § Quality gates)
    # never reach the registry.
    sample_rows = (
        db.query(SourceSpeaker)
        .filter(
            SourceSpeaker.document_id == doc.document_id,
            effective_label == speaker_label,
            SourceSpeaker.embedding.isnot(None),
            SourceSpeaker.embedding_model.isnot(None),
        )
        .order_by((SourceSpeaker.end_ts - SourceSpeaker.start_ts).desc())
        .limit(VOICEPRINT_SAMPLE_LIMIT)
        .all()
    )

    def stream() -> Iterator[bytes]:
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

            # ---- Voiceprint promotion -------------------------------
            voiceprints_written = 0
            if not sample_rows:
                yield _ndjson({
                    "step": "voice_enrol",
                    "status": "skip",
                    "detail": (
                        "No turns with non-NULL embedding in this cluster — "
                        "speaker_person_id will still be set, but no "
                        "voiceprints can be written. Re-run diarisation if "
                        "this is unexpected."
                    ),
                })
            else:
                yield _ndjson({
                    "step": "voice_enrol",
                    "status": "start",
                    "detail": {"sample_size": len(sample_rows)},
                })
                voiceprint_rows = [
                    PersonVoiceprint(
                        person_id=target_person_id,
                        source_id=source_id,
                        start_ts=float(sp.start_ts),
                        end_ts=float(sp.end_ts),
                        embedding=list(sp.embedding),
                        embedding_model=sp.embedding_model,
                        created_by="manual",
                    )
                    for sp in sample_rows
                ]
                db.add_all(voiceprint_rows)
                db.flush()
                voiceprints_written = len(voiceprint_rows)
                yield _ndjson({
                    "step": "voice_enrol",
                    "status": "done",
                    "detail": {"voiceprints_written": voiceprints_written},
                })

            # ---- Bulk SP attribution --------------------------------
            yield _ndjson({"step": "attribute", "status": "start"})
            turns_updated = db.execute(
                sa_update(SourceSpeaker)
                .where(
                    SourceSpeaker.document_id == doc.document_id,
                    effective_label == speaker_label,
                )
                .values(
                    speaker_person_id=target_person_id,
                    match_method="manual",
                    match_confidence=1.0,
                )
            ).rowcount or 0
            yield _ndjson({
                "step": "attribute",
                "status": "done",
                "detail": {"turns_updated": turns_updated},
            })

            # ---- Commit ---------------------------------------------
            yield _ndjson({"step": "commit", "status": "start"})
            db.commit()
            yield _ndjson({"step": "commit", "status": "done"})

            yield _ndjson({
                "step": "result",
                "status": "done",
                "detail": {
                    "person_id": str(target_person_id),
                    "person_name": person_name,
                    "person_created": person_created,
                    "speaker_label": speaker_label,
                    "turns_updated": turns_updated,
                    "voiceprints_written": voiceprints_written,
                    "match_method": "manual",
                },
            })
        except Exception as exc:
            logger.exception("voice-cluster assign failed mid-stream")
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


class VoiceTurnReassignRequest(BaseModel):
    """Reassign a single voice turn to a Person + grow the voiceprint
    registry by one labeled exemplar. Voice-only counterpart to the
    full ``/reassign`` endpoint that also enrols a face crop. No video
    worker, no S3 audio download — the turn's medoid embedding is
    already on the row.
    """
    person_id: uuid.UUID | None = Field(
        default=None,
        description="Existing Person to attribute this turn to.",
    )
    new_person_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description=(
            "Canonical name of a Person to create (or reuse, "
            "case-insensitive). Mutually exclusive with person_id."
        ),
    )


@router.post("/sources/{source_id}/speakers/{segment_id}/voice-reassign")
def voice_reassign_turn(
    source_id: uuid.UUID,
    segment_id: uuid.UUID,
    body: VoiceTurnReassignRequest,
    db: Session = Depends(get_db),
):
    """Per-turn voice label fix — improves both the per-turn attribution
    AND the voiceprint registry's labels in one SQL transaction.

    Updates ``source_speakers``:
      * ``speaker_person_id`` → target Person
      * ``match_method`` → 'manual'
      * ``match_confidence`` → 1.0

    Writes one ``person_voiceprints`` row from the turn's medoid
    (when ``embedding`` is non-null). The turn already has an
    embedding from the diarisation pass — no recompute, no audio
    fetch. If the turn lacks an embedding (sub-MIN_TURN_DURATION
    spans), only the attribution is updated; the voiceprint is
    skipped with ``voiceprint_written: false``.

    Used by the Review tab to fix outlier turns where the cluster
    is right overall but this single turn was mis-assigned. Each
    correction grows the registry by one correctly-labeled exemplar,
    which is exactly the bootstrap loop voice ID needs to sharpen.
    """
    if (body.person_id is None) == (body.new_person_name is None):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one of person_id or new_person_name",
        )

    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    turn = (
        db.query(SourceSpeaker)
        .filter(SourceSpeaker.segment_id == segment_id)
        .first()
    )
    if not turn:
        raise HTTPException(status_code=404, detail="Turn not found")
    # Confirm the segment belongs to this source — defends against
    # cross-source URL tampering.
    doc = (
        db.query(SourceDocument)
        .filter(SourceDocument.document_id == turn.document_id)
        .first()
    )
    if not doc or doc.source_id != source_id:
        raise HTTPException(
            status_code=404, detail="Turn does not belong to this source",
        )

    # Resolve / create Person. Commit the new person before the turn
    # update so a later UNIQUE collision can't leave a half-created
    # row (same pattern as ``bulk_assign_voice_cluster``).
    person_created = False
    if body.person_id is not None:
        person = db.query(Person).filter(Person.person_id == body.person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")
    else:
        new_name = (body.new_person_name or "").strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="new_person_name is empty")
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

    # Voiceprint from the turn's medoid. Skip when the row carries no
    # embedding (sub-300ms turns have NULL after diarisation).
    voiceprint_written = False
    if turn.embedding is not None and turn.embedding_model is not None:
        vp = PersonVoiceprint(
            person_id=person.person_id,
            source_id=source_id,
            start_ts=float(turn.start_ts),
            end_ts=float(turn.end_ts),
            embedding=list(turn.embedding),
            embedding_model=turn.embedding_model,
            created_by="manual",
        )
        db.add(vp)
        voiceprint_written = True

    turn.speaker_person_id = person.person_id
    turn.match_method = "manual"
    turn.match_confidence = 1.0
    db.commit()

    return {
        "person_id": str(person.person_id),
        "person_name": person.canonical_name,
        "person_created": person_created,
        "segment_id": str(turn.segment_id),
        "speaker_label": turn.speaker_label,
        "cluster_label": turn.cluster_label,
        "voiceprint_written": voiceprint_written,
    }


class VoiceReclusterRequest(BaseModel):
    """Tunable knobs for the HDBSCAN re-clustering pass.

    All optional — defaults mirror :class:`VoiceClusterParams` and are
    sensible for typical 30-60 min commentary podcasts. The UI exposes
    these as sliders so the operator can tighten / loosen the clustering
    per-source without redeploying.
    """
    min_cluster_size: int | None = Field(
        default=None, ge=2, le=200,
        description="HDBSCAN min_cluster_size. Lower → finds smaller clusters.",
    )
    min_samples: int | None = Field(
        default=None, ge=1, le=50,
        description="HDBSCAN min_samples. Lower → more permissive density.",
    )
    noise_threshold: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description=(
            "Cosine similarity floor (0..1). Higher → tighter clusters, "
            "more turns labelled noise."
        ),
    )


@router.post("/sources/{source_id}/voice-clusters/recluster")
def recluster_voice_clusters(
    source_id: uuid.UUID,
    body: VoiceReclusterRequest,
    db: Session = Depends(get_db),
):
    """Re-run HDBSCAN over per-turn wespeaker medoids and overwrite the
    ``cluster_label`` column for every turn in this source.

    Pyannote's ``speaker_label`` stays untouched as a fallback signal.
    The Voices tab and AssignVoice flow group/match by
    ``coalesce(cluster_label, speaker_label)`` so the new labels take
    precedence immediately, and re-running with different params is
    safe — every turn in the document is reset to ``cluster_label=NULL``
    before the new labels are written, so stale H-labels from previous
    runs don't leak through.

    Pure SQL + in-process HDBSCAN — no SageMaker, no GPU. The clustering
    step is O(N²) but N is ~hundreds of turns per source, so it runs in
    well under a second.
    """
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    defaults = VoiceClusterParams()
    params = VoiceClusterParams(
        min_cluster_size=body.min_cluster_size or defaults.min_cluster_size,
        min_samples=body.min_samples or defaults.min_samples,
        noise_threshold=(
            body.noise_threshold
            if body.noise_threshold is not None
            else defaults.noise_threshold
        ),
    )
    result = recluster_source_voice(db, source_id, params=params)
    return {
        "source_id": str(result.source_id),
        "n_turns_total": result.n_turns_total,
        "n_turns_with_embedding": result.n_turns_with_embedding,
        "n_clusters": result.n_clusters,
        "n_noise": result.n_noise,
        "cluster_sizes": result.cluster_sizes,
        "params_used": {
            "min_cluster_size": params.min_cluster_size,
            "min_samples": params.min_samples,
            "noise_threshold": params.noise_threshold,
        },
    }


# ---------------------------------------------------------------------------
# Review tab — playback-aligned working surface that fuses face, voice
# and word data so the operator can scrub the video and see the
# attribution at the playhead in one place. Two read-only endpoints
# back it; enrollment-from-window is a Phase 2 follow-up.
# ---------------------------------------------------------------------------


@router.get("/sources/{source_id}/voice-timeline")
def get_voice_timeline(source_id: uuid.UUID, db: Session = Depends(get_db)):
    """Per-turn voice timeline for the Review tab.

    One row per ``source_speakers`` entry with both labels exposed
    side-by-side (``speaker_label`` = pyannote raw, ``cluster_label``
    = HDBSCAN override) so the Review status pill can show both and
    you can see where they diverge. Sorted by start_ts.
    """
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    doc = (
        db.query(SourceDocument)
        .filter(SourceDocument.source_id == source_id)
        .first()
    )
    if not doc:
        return {"source_id": str(source_id), "turns": []}

    rows = (
        db.query(
            SourceSpeaker.segment_id,
            SourceSpeaker.start_ts,
            SourceSpeaker.end_ts,
            SourceSpeaker.speaker_label,
            SourceSpeaker.cluster_label,
            SourceSpeaker.speaker_person_id,
            SourceSpeaker.match_method,
            (SourceSpeaker.embedding.isnot(None)).label("has_embedding"),
        )
        .filter(SourceSpeaker.document_id == doc.document_id)
        .order_by(SourceSpeaker.start_ts)
        .all()
    )

    person_ids = {r.speaker_person_id for r in rows if r.speaker_person_id}
    names: dict[uuid.UUID, str] = {}
    if person_ids:
        for p in db.query(Person).filter(Person.person_id.in_(person_ids)).all():
            names[p.person_id] = p.canonical_name

    turns = [
        {
            "segment_id": str(r.segment_id),
            "start_ts": float(r.start_ts),
            "end_ts": float(r.end_ts),
            "duration": float(r.end_ts - r.start_ts),
            "speaker_label": r.speaker_label,
            "cluster_label": r.cluster_label,
            "person_id": str(r.speaker_person_id) if r.speaker_person_id else None,
            "person_name": names.get(r.speaker_person_id) if r.speaker_person_id else None,
            "match_method": r.match_method,
            "has_embedding": bool(r.has_embedding),
        }
        for r in rows
    ]
    return {"source_id": str(source_id), "turns": turns}


@router.get("/sources/{source_id}/word-attribution")
def get_word_attribution(source_id: uuid.UUID, db: Session = Depends(get_db)):
    """Deepgram words with per-word face-cluster attribution.

    For each Deepgram word, looks up the active face cluster at the
    word's start timestamp using the same mouth-opening ASD signal
    the face-transcript surface uses. Returns the word's text, time
    range, confidence, and the face cluster + attributed person that
    was on screen with mouth open at that moment. ``face_cluster_id``
    is null when no face was above the mouth-opening threshold at
    that instant (camera cutaway, reaction shot, off-screen speech).

    Heavy endpoint by row count (~11k words for a 50-min source) but
    the JSON is well under 5 MB, served gzipped, and front-end keeps
    it in memory for the duration of the Review session.
    """
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    doc = (
        db.query(SourceDocument)
        .filter(SourceDocument.source_id == source_id)
        .first()
    )
    if not doc or not doc.s3_key:
        return {"source_id": str(source_id), "words": []}

    try:
        dg = json.loads(download_raw(doc.s3_key))
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to load Deepgram JSON from S3: {exc}",
        )

    # Face frames sorted by ts, plus per-frame active speaker (cluster
    # with highest mouth_opening above threshold).
    det_rows = (
        db.query(
            SourceFaceDetection.frame_ts,
            SourceFaceDetection.cluster_id,
            SourceFaceDetection.mouth_opening,
            SourceFaceDetection.matched_person_id,
        )
        .filter(SourceFaceDetection.source_id == source_id)
        .order_by(SourceFaceDetection.frame_ts)
        .all()
    )
    by_frame: dict[float, list[tuple[int | None, float, uuid.UUID | None]]] = defaultdict(list)
    for r in det_rows:
        mo = float(r.mouth_opening) if r.mouth_opening is not None else 0.0
        by_frame[float(r.frame_ts)].append((r.cluster_id, mo, r.matched_person_id))
    sorted_frame_ts = sorted(by_frame.keys())

    cluster_meta = {
        c.cluster_id: c
        for c in db.query(SourceFaceCluster).filter(SourceFaceCluster.source_id == source_id).all()
    }
    person_ids: set[uuid.UUID] = {
        c.attributed_person_id for c in cluster_meta.values() if c.attributed_person_id
    }
    for r in det_rows:
        if r.matched_person_id:
            person_ids.add(r.matched_person_id)
    names: dict[uuid.UUID, str] = {}
    if person_ids:
        for p in db.query(Person).filter(Person.person_id.in_(person_ids)).all():
            names[p.person_id] = p.canonical_name

    # Use the live ASD threshold so this view stays consistent with
    # the face-transcript and visual_id paths.
    threshold = 0.045

    def _resolve_face(cid: int | None, matched_pid: uuid.UUID | None) -> dict:
        cmeta = cluster_meta.get(cid) if cid is not None else None
        attr_pid = cmeta.attributed_person_id if cmeta else None
        return {
            "face_cluster_id": cid,
            "cluster_attributed_person_id": str(attr_pid) if attr_pid else None,
            "cluster_attributed_person_name": names.get(attr_pid) if attr_pid else None,
            "per_detection_matched_person_id": str(matched_pid) if matched_pid else None,
            "per_detection_matched_person_name": names.get(matched_pid) if matched_pid else None,
        }

    excluded_cluster_ids = {
        cid for cid, c in cluster_meta.items() if c.excluded
    }

    def lookup_faces(word_start: float) -> tuple[list[dict], dict | None]:
        """Return (visible_faces, active_speaker).

        ``visible_faces`` is every face detected in the active frame,
        even those whose mouth_opening is below threshold and even
        those in excluded clusters — the overlay draws all of them,
        so Review must report all of them. Each carries a
        ``is_active_speaker`` flag and a ``is_excluded`` flag.

        ``active_speaker`` is the **non-excluded** face with the
        highest mouth_opening that crosses the ASD threshold. Excluded
        clusters are deliberately ignored here: the operator already
        decided those rows are noise/portraits/duplicates, so a 5%
        mouth-opening flicker on c1 shouldn't override the legitimate
        speaker on c0. Excluded faces still appear in
        ``visible_faces`` for visibility — they just can't win the
        speaker pick.

        Both are ``None`` / ``[]`` only when no face frame exists
        at-or-before ``word_start``.
        """
        idx = bisect.bisect_right(sorted_frame_ts, word_start) - 1
        if idx < 0:
            return [], None
        ts = sorted_frame_ts[idx]
        candidates = by_frame[ts]
        if not candidates:
            return [], None
        ranked = sorted(candidates, key=lambda c: -c[1])

        # Active speaker pick is restricted to non-excluded clusters.
        active = None
        for cid, mo, matched_pid in ranked:
            if cid is None or cid in excluded_cluster_ids:
                continue
            if mo < threshold:
                # Further candidates are sorted lower, so once we hit
                # the first non-excluded one that's below threshold,
                # no later non-excluded one will cross it either.
                break
            active = {
                **_resolve_face(cid, matched_pid),
                "mouth_opening": float(mo),
            }
            break

        visible = []
        for cid, mo, matched_pid in ranked:
            entry = _resolve_face(cid, matched_pid)
            entry["mouth_opening"] = float(mo)
            entry["is_excluded"] = (cid in excluded_cluster_ids) if cid is not None else False
            entry["is_active_speaker"] = (
                active is not None
                and cid == active["face_cluster_id"]
                and mo == active["mouth_opening"]
            )
            visible.append(entry)
        return visible, active

    alts = (dg.get("results") or {}).get("channels") or []
    raw_words: list[dict] = []
    if alts:
        first_alt = (alts[0].get("alternatives") or [{}])[0]
        raw_words = first_alt.get("words") or []

    out_words: list[dict] = []
    for w in raw_words:
        try:
            ws = float(w["start"])
            we = float(w["end"])
        except (KeyError, TypeError, ValueError):
            continue
        visible, active = lookup_faces(ws)
        out_words.append({
            "start": ws,
            "end": we,
            "word": str(w.get("punctuated_word") or w.get("word") or ""),
            "confidence": float(w.get("confidence") or 0.0),
            "visible_faces": visible,
            "active_speaker": active,
        })

    return {
        "source_id": str(source_id),
        "mouth_threshold": threshold,
        "word_count": len(out_words),
        "words": out_words,
    }


# ---------------------------------------------------------------------------
# Face-driven transcript — segment by face presence + mouth opening (ASD),
# bypassing pyannote. Each segment carries the active-speaker cluster
# (and attributed person if any) plus the Deepgram words whose start
# falls inside the segment window. Exploratory surface — answers "what
# does the transcript look like if face is the source of truth?".
# ---------------------------------------------------------------------------


@router.get("/sources/{source_id}/face-transcript")
def get_face_transcript(
    source_id: uuid.UUID,
    mouth_threshold: float | None = None,
    smooth_gap: float | None = None,
    min_segment: float | None = None,
    include_silence: bool = False,
    db: Session = Depends(get_db),
):
    """Return a face-driven chronological transcript for the source.

    Walks ``source_face_detections`` frame-by-frame, picks the active
    speaker per frame using the existing mouth-opening ASD signal,
    merges same-speaker windows across multi-cam camera cuts up to
    ``smooth_gap``, drops sub-``min_segment`` flickers, and attaches
    Deepgram word-level text to each segment.

    Bypasses ``source_speakers`` / pyannote entirely — the answer here
    is "who is on screen with mouth open at this moment". Useful as a
    diagnostic counterpart to the pyannote Voices view; the two should
    converge on single-cam recordings and disagree systematically on
    multi-cam edited content (camera flips while audio continues).
    """
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    segments = segment_by_face(
        db, source_id,
        mouth_threshold=(
            mouth_threshold if mouth_threshold is not None else FACE_TX_DEFAULT_MOUTH
        ),
        smooth_gap_seconds=(
            smooth_gap if smooth_gap is not None else FACE_TX_DEFAULT_SMOOTH
        ),
        min_segment_seconds=(
            min_segment if min_segment is not None else FACE_TX_DEFAULT_MIN_SEGMENT
        ),
    )

    if not include_silence:
        segments = [s for s in segments if s["speaker_cluster_id"] is not None]

    payload = [
        {
            "start": s["start"],
            "end": s["end"],
            "duration": s["end"] - s["start"],
            "face_cluster_id": s["speaker_cluster_id"],
            "speaker_label": s["speaker_label"],
            "person_name": s["person_name"],
            "text": s["text"],
        }
        for s in segments
    ]
    return {
        "source_id": str(source_id),
        "params_used": {
            "mouth_threshold": (
                mouth_threshold if mouth_threshold is not None else FACE_TX_DEFAULT_MOUTH
            ),
            "smooth_gap": (
                smooth_gap if smooth_gap is not None else FACE_TX_DEFAULT_SMOOTH
            ),
            "min_segment": (
                min_segment if min_segment is not None else FACE_TX_DEFAULT_MIN_SEGMENT
            ),
            "include_silence": include_silence,
        },
        "segments": payload,
    }


# ---------------------------------------------------------------------------
# Identity alignment — face_cluster × voice_cluster overlap matrix.
#
# Face and voice are two independent clusterings of the same conversation.
# This endpoint exposes their alignment: for every (face_cluster_id,
# speaker_label) pair, how many face detections fall inside the speaker's
# turns; greedy 1:1 best mapping; and a per-turn disagreement list where
# the dominant on-screen face cluster's identity ≠ the turn's
# speaker_person_id. See
# docs/agents/system/speaker-identification.md § Identity alignment.
# ---------------------------------------------------------------------------


@router.get("/sources/{source_id}/identity-alignment")
def get_identity_alignment(source_id: uuid.UUID, db: Session = Depends(get_db)):
    """Cross-modal alignment between face clusters and voice clusters
    for this source. Read-only — actions live on the per-modality tabs.

    Resolves dominant person names for every face cluster, voice
    cluster, and disagreement-list row in a single ``people`` query.
    """
    source = db.query(Source).filter(Source.source_id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    payload = fetch_alignment(db, source_id)

    # Collect every person_id referenced anywhere in the payload — one
    # Person query resolves all the names. Timeline rows reference up to
    # five different person columns per row, so the deduping matters.
    person_ids: set[uuid.UUID] = set()

    def _add(value: str | None) -> None:
        if value:
            person_ids.add(uuid.UUID(value))

    for c in payload["face_clusters"]:
        _add(c.get("dominant_person_id"))
    for v in payload["voice_clusters"]:
        _add(v.get("dominant_person_id"))
    for d in payload["disagreements"]:
        _add(d.get("speaker_person_id"))
        _add(d.get("face_person_id"))
    for t in payload["timeline"]:
        _add(t.get("voice_cluster_person_id"))
        _add(t.get("face_cluster_person_id"))
        _add(t.get("audio_match_person_id"))
        _add(t.get("visual_match_person_id"))
        _add(t.get("speaker_person_id"))
    for r in payload.get("face_transcript", []):
        _add(r.get("face_cluster_person_id"))

    name_by_id: dict[str, str] = {}
    if person_ids:
        for p in db.query(Person).filter(Person.person_id.in_(person_ids)).all():
            name_by_id[str(p.person_id)] = p.canonical_name

    def _name(value: str | None) -> str | None:
        return name_by_id.get(value) if value else None

    for c in payload["face_clusters"]:
        c["dominant_person_name"] = _name(c.get("dominant_person_id"))
    for v in payload["voice_clusters"]:
        v["dominant_person_name"] = _name(v.get("dominant_person_id"))
    for d in payload["disagreements"]:
        d["speaker_person_name"] = _name(d.get("speaker_person_id"))
        d["face_person_name"] = _name(d.get("face_person_id"))
    for t in payload["timeline"]:
        t["voice_cluster_person_name"] = _name(t.get("voice_cluster_person_id"))
        t["face_cluster_person_name"] = _name(t.get("face_cluster_person_id"))
        t["audio_match_person_name"] = _name(t.get("audio_match_person_id"))
        t["visual_match_person_name"] = _name(t.get("visual_match_person_id"))
        t["speaker_person_name"] = _name(t.get("speaker_person_id"))
    for r in payload.get("face_transcript", []):
        r["face_cluster_person_name"] = _name(r.get("face_cluster_person_id"))

    return {
        "source_id": str(source_id),
        **payload,
    }
