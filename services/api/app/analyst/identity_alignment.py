"""Cross-modal cluster alignment for the identity-review surface.

Face clusters (visual identity, via HDBSCAN over ArcFace embeddings)
and pyannote voice clusters (audio identity, via SPEAKER_NN labels)
are two independent clusterings of the same conversation. This module
aligns them: for every (face_cluster, voice_cluster) pair, count how
many face detections fall inside the voice cluster's turns, derive
per-modality shares, and propose a 1:1 dominant pairing.

The downstream wins are spelled out in
``docs/agents/system/speaker-identification.md`` (one-shot dual
assign, disagreement review, asymmetric error correction). This file
is the pure compute path; the read endpoint resolves Person names on
top of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from jeromelu_shared.db import (
    SourceDocument,
    SourceFaceDetection,
    SourceSpeaker,
)

#: Local mirror of ``visual_id.MIN_ACTIVE_MOUTH_OPENING`` so this module
#: doesn't pull the visual_id import chain (cv2, InsightFace, numpy)
#: into unit tests. Kept in sync with the source-of-truth threshold —
#: see speaker-identification.md § Per-turn vote with ASD.
MIN_ACTIVE_MOUTH_OPENING = 0.045

#: Minimum overlap_count for a (face_cluster, voice_cluster) pair to
#: appear in the alignment matrix. Pairs below this are statistical
#: noise from a one-frame appearance and clutter the UI without
#: contributing useful signal.
MIN_OVERLAP_COUNT = 5

#: Cap on per-turn disagreements returned to the caller. The
#: disagreement list is an operator worklist — the top-N most
#: airtime-significant cases is what matters; a 2000-item list is
#: not actionable. Sorted by turn duration descending.
DISAGREEMENT_LIMIT = 50


@dataclass(frozen=True)
class DetectionRow:
    """Minimal face detection projection consumed by :func:`compute_alignment`."""
    detection_id: UUID
    frame_ts: float
    cluster_id: int | None
    mouth_opening: float | None
    matched_person_id: UUID | None


@dataclass(frozen=True)
class TurnRow:
    """Minimal source_speakers projection consumed by :func:`compute_alignment`."""
    segment_id: UUID
    start_ts: float
    end_ts: float
    speaker_label: str | None
    speaker_person_id: UUID | None
    match_method: str | None


def compute_alignment(
    detections: list[DetectionRow],
    speakers: list[TurnRow],
) -> dict:
    """Cross-modal alignment between face clusters and voice clusters.

    Returns a payload of the shape::

        {
            "face_clusters": [{"cluster_id", "detection_count",
                               "dominant_person_id", "dominant_share"}, ...],
            "voice_clusters": [{"speaker_label", "turn_count", "total_seconds",
                                "dominant_person_id", "dominant_share"}, ...],
            "alignment": [{"face_cluster_id", "speaker_label",
                           "overlap_count", "active_overlap_count",
                           "face_cluster_share", "voice_cluster_share",
                           "confidence"}, ...],
            "dominant_pairings": [{"face_cluster_id", "speaker_label",
                                   "confidence", "overlap_count"}, ...],
            "disagreements": [{"segment_id", "start_ts", "end_ts",
                               "speaker_label",
                               "speaker_person_id",       # voice attribution
                               "face_cluster_id",         # cluster covering most frames in turn
                               "face_person_id",          # cluster's dominant_person_id
                               "active_overlap_count"}, ...],
        }

    Both NULL face cluster_ids (HDBSCAN outliers) and NULL speaker_labels
    are filtered out — they don't form a coherent identity. ``alignment``
    is filtered to pairs with ``overlap_count >= MIN_OVERLAP_COUNT`` so
    one-frame flukes don't crowd the matrix.
    """
    # Per-cluster face stats and per-speaker turn stats up-front. These
    # are also the denominators for the share computations.
    face_stats = _face_cluster_stats(detections)
    voice_stats = _voice_cluster_stats(speakers)

    # Bucket detections by (cluster_id, speaker_label) using an interval
    # walk: sort detections by frame_ts, sort turns by start_ts, then for
    # each detection find any turn covering its frame_ts. Many sources
    # are small enough that an O(n*m) check works, but the interval walk
    # is O((n+m) log n) and scales cleanly to bigger sources.
    overlap_counts: dict[tuple[int, str], int] = {}
    active_overlap_counts: dict[tuple[int, str], int] = {}
    # Per-turn: track which face_cluster contributed the most frames so
    # the disagreement list can flag turns where voice attribution ≠
    # dominant face cluster's identity.
    per_turn_cluster_counts: dict[UUID, dict[int, int]] = {}

    sorted_dets = sorted(detections, key=lambda d: d.frame_ts)
    sorted_turns = sorted(
        (t for t in speakers if t.speaker_label),
        key=lambda t: t.start_ts,
    )

    for det in sorted_dets:
        if det.cluster_id is None:
            continue
        # Linear scan from a moving lower-bound is fine at podcast scale.
        # Could be O(log n) with bisect — left as a future optimisation
        # if a 10-hour source ever needs it.
        for turn in sorted_turns:
            if turn.end_ts < det.frame_ts:
                continue
            if turn.start_ts > det.frame_ts:
                break
            label: str = turn.speaker_label  # type: ignore[assignment]
            key = (det.cluster_id, label)
            overlap_counts[key] = overlap_counts.get(key, 0) + 1
            if (
                det.mouth_opening is not None
                and det.mouth_opening >= MIN_ACTIVE_MOUTH_OPENING
            ):
                active_overlap_counts[key] = (
                    active_overlap_counts.get(key, 0) + 1
                )
            cluster_counts = per_turn_cluster_counts.setdefault(
                turn.segment_id, {},
            )
            cluster_counts[det.cluster_id] = (
                cluster_counts.get(det.cluster_id, 0) + 1
            )
            # A detection's frame_ts can only land in one turn (turns
            # don't overlap), so break early.
            break

    alignment = _build_alignment_rows(
        overlap_counts=overlap_counts,
        active_overlap_counts=active_overlap_counts,
        face_stats=face_stats,
        voice_stats=voice_stats,
    )
    dominant_pairings = _greedy_dominant_pairings(alignment)
    disagreements = _compute_disagreements(
        speakers=speakers,
        per_turn_cluster_counts=per_turn_cluster_counts,
        active_overlap_counts=active_overlap_counts,
        face_stats=face_stats,
    )

    return {
        "face_clusters": [
            {
                "cluster_id": cid,
                "detection_count": s["detection_count"],
                "dominant_person_id": s["dominant_person_id"],
                "dominant_share": s["dominant_share"],
            }
            for cid, s in sorted(
                face_stats.items(), key=lambda kv: -kv[1]["detection_count"],
            )
        ],
        "voice_clusters": [
            {
                "speaker_label": label,
                "turn_count": s["turn_count"],
                "total_seconds": s["total_seconds"],
                "dominant_person_id": s["dominant_person_id"],
                "dominant_share": s["dominant_share"],
            }
            for label, s in sorted(
                voice_stats.items(), key=lambda kv: -kv[1]["total_seconds"],
            )
        ],
        "alignment": alignment,
        "dominant_pairings": dominant_pairings,
        "disagreements": disagreements,
    }


def _face_cluster_stats(detections: list[DetectionRow]) -> dict[int, dict]:
    """Per-cluster detection_count + dominant matched_person_id."""
    stats: dict[int, dict] = {}
    person_counts: dict[int, dict[UUID, int]] = {}
    for det in detections:
        if det.cluster_id is None:
            continue
        s = stats.setdefault(
            det.cluster_id, {"detection_count": 0},
        )
        s["detection_count"] += 1
        if det.matched_person_id is not None:
            pc = person_counts.setdefault(det.cluster_id, {})
            pc[det.matched_person_id] = pc.get(det.matched_person_id, 0) + 1

    for cid, s in stats.items():
        pc = person_counts.get(cid, {})
        if pc:
            dom_pid, dom_count = max(pc.items(), key=lambda kv: kv[1])
            s["dominant_person_id"] = str(dom_pid)
            s["dominant_share"] = dom_count / s["detection_count"]
        else:
            s["dominant_person_id"] = None
            s["dominant_share"] = None
    return stats


def _voice_cluster_stats(speakers: list[TurnRow]) -> dict[str, dict]:
    """Per-label turn_count + total_seconds + dominant speaker_person_id."""
    stats: dict[str, dict] = {}
    person_counts: dict[str, dict[UUID, int]] = {}
    for turn in speakers:
        if not turn.speaker_label:
            continue
        s = stats.setdefault(
            turn.speaker_label, {"turn_count": 0, "total_seconds": 0.0},
        )
        s["turn_count"] += 1
        s["total_seconds"] += turn.end_ts - turn.start_ts
        if turn.speaker_person_id is not None:
            pc = person_counts.setdefault(turn.speaker_label, {})
            pc[turn.speaker_person_id] = (
                pc.get(turn.speaker_person_id, 0) + 1
            )

    for label, s in stats.items():
        pc = person_counts.get(label, {})
        if pc:
            dom_pid, dom_count = max(pc.items(), key=lambda kv: kv[1])
            s["dominant_person_id"] = str(dom_pid)
            s["dominant_share"] = dom_count / s["turn_count"]
        else:
            s["dominant_person_id"] = None
            s["dominant_share"] = None
    return stats


def _build_alignment_rows(
    *,
    overlap_counts: dict[tuple[int, str], int],
    active_overlap_counts: dict[tuple[int, str], int],
    face_stats: dict[int, dict],
    voice_stats: dict[str, dict],
) -> list[dict]:
    """Materialise per-pair alignment rows, filtered + sorted."""
    rows: list[dict] = []
    for (cid, label), count in overlap_counts.items():
        if count < MIN_OVERLAP_COUNT:
            continue
        face_total = face_stats[cid]["detection_count"]
        # Voice denominator uses total_seconds. At 1 fps detection
        # count ≈ seconds, so the shares are commensurable. Different
        # sample rates (e.g. 2 fps) would skew this — fine to revisit
        # once we run at non-1 fps.
        voice_total = voice_stats[label]["total_seconds"] or 1.0
        face_share = count / face_total if face_total else 0.0
        voice_share = count / voice_total
        rows.append({
            "face_cluster_id": cid,
            "speaker_label": label,
            "overlap_count": count,
            "active_overlap_count": active_overlap_counts.get((cid, label), 0),
            "face_cluster_share": face_share,
            "voice_cluster_share": voice_share,
            "confidence": min(face_share, voice_share),
        })
    rows.sort(key=lambda r: -r["confidence"])
    return rows


def _greedy_dominant_pairings(alignment: list[dict]) -> list[dict]:
    """Greedy 1:1 mapping — each face cluster and each voice cluster
    appears at most once. Walk ``alignment`` already sorted by
    confidence desc, take pairs whose face_cluster_id and
    speaker_label are still unclaimed.
    """
    claimed_face: set[int] = set()
    claimed_voice: set[str] = set()
    out: list[dict] = []
    for row in alignment:
        if (
            row["face_cluster_id"] in claimed_face
            or row["speaker_label"] in claimed_voice
        ):
            continue
        claimed_face.add(row["face_cluster_id"])
        claimed_voice.add(row["speaker_label"])
        out.append({
            "face_cluster_id": row["face_cluster_id"],
            "speaker_label": row["speaker_label"],
            "confidence": row["confidence"],
            "overlap_count": row["overlap_count"],
        })
    return out


def _compute_disagreements(
    *,
    speakers: list[TurnRow],
    per_turn_cluster_counts: dict[UUID, dict[int, int]],
    active_overlap_counts: dict[tuple[int, str], int],
    face_stats: dict[int, dict],
) -> list[dict]:
    """Turns where the dominant on-screen face cluster's identity
    disagrees with the turn's ``speaker_person_id``. Reaction-shot
    false positives the mouth-opening ASD let through fall here, as
    do mis-attributed clusters.

    Both sides must have an identity for the row to count — turns
    with NULL speaker_person_id, and clusters with NULL dominant
    person, can't disagree about anything.
    """
    out: list[dict] = []
    for turn in speakers:
        if turn.speaker_person_id is None:
            continue
        cluster_counts = per_turn_cluster_counts.get(turn.segment_id)
        if not cluster_counts:
            continue
        dom_cluster, dom_count = max(
            cluster_counts.items(), key=lambda kv: kv[1],
        )
        face_dom = face_stats[dom_cluster].get("dominant_person_id")
        if not face_dom:
            continue
        if face_dom == str(turn.speaker_person_id):
            continue
        out.append({
            "segment_id": str(turn.segment_id),
            "start_ts": float(turn.start_ts),
            "end_ts": float(turn.end_ts),
            "speaker_label": turn.speaker_label,
            "speaker_person_id": str(turn.speaker_person_id),
            "face_cluster_id": dom_cluster,
            "face_person_id": face_dom,
            "active_overlap_count": active_overlap_counts.get(
                (dom_cluster, turn.speaker_label or ""), 0,
            ),
        })
    # Sort by turn duration desc — biggest mismatches first.
    out.sort(key=lambda r: -(r["end_ts"] - r["start_ts"]))
    return out[:DISAGREEMENT_LIMIT]


def fetch_alignment(session: Session, source_id: UUID) -> dict:
    """Load detections + speakers for the source and run
    :func:`compute_alignment`. Returns the same payload shape, plus
    empty lists when either side has no data yet (no detections
    backfilled, or transcription hasn't run).
    """
    doc = (
        session.query(SourceDocument)
        .filter(SourceDocument.source_id == source_id)
        .first()
    )
    if not doc:
        return {
            "face_clusters": [],
            "voice_clusters": [],
            "alignment": [],
            "dominant_pairings": [],
            "disagreements": [],
        }

    det_rows = (
        session.query(
            SourceFaceDetection.detection_id,
            SourceFaceDetection.frame_ts,
            SourceFaceDetection.cluster_id,
            SourceFaceDetection.mouth_opening,
            SourceFaceDetection.matched_person_id,
        )
        .filter(SourceFaceDetection.source_id == source_id)
        .all()
    )
    detections = [
        DetectionRow(
            detection_id=r.detection_id,
            frame_ts=float(r.frame_ts),
            cluster_id=r.cluster_id,
            mouth_opening=(
                float(r.mouth_opening) if r.mouth_opening is not None else None
            ),
            matched_person_id=r.matched_person_id,
        )
        for r in det_rows
    ]

    speaker_rows = (
        session.query(
            SourceSpeaker.segment_id,
            SourceSpeaker.start_ts,
            SourceSpeaker.end_ts,
            SourceSpeaker.speaker_label,
            SourceSpeaker.speaker_person_id,
            SourceSpeaker.match_method,
        )
        .filter(SourceSpeaker.document_id == doc.document_id)
        .all()
    )
    speakers = [
        TurnRow(
            segment_id=r.segment_id,
            start_ts=float(r.start_ts),
            end_ts=float(r.end_ts),
            speaker_label=r.speaker_label,
            speaker_person_id=r.speaker_person_id,
            match_method=r.match_method,
        )
        for r in speaker_rows
    ]

    return compute_alignment(detections, speakers)
