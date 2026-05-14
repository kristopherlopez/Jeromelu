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

from sqlalchemy import func
from sqlalchemy.orm import Session

from jeromelu_shared.db import (
    SourceChunk,
    SourceDocument,
    SourceFaceDetection,
    SourceSpeaker,
)

from app.analyst.voice_clusters import fetch_full_turn_text

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
    # Per-modality match columns (set during transcribe-time ID before
    # fusion). Optional so existing test fixtures still build — defaults
    # let callers ignore the fields when they only care about cluster
    # alignment, not per-turn modality breakdown.
    audio_match_person_id: UUID | None = None
    visual_match_person_id: UUID | None = None
    match_confidence: float | None = None


@dataclass(frozen=True)
class ChunkRow:
    """Minimal source_chunks projection consumed by face_transcript.

    Used in Phase 1 (face-driven transcript view). Chunks are the
    Deepgram utterance granularity — ~5× finer than pyannote turns —
    so they're the right unit for "what was said when face X was on
    screen?"
    """
    chunk_id: UUID
    start_ts: float
    end_ts: float
    text: str


def compute_alignment(
    detections: list[DetectionRow],
    speakers: list[TurnRow],
    preview_by_segment: dict[UUID, str] | None = None,
    chunks: list[ChunkRow] | None = None,
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
    # Per-turn rollups for the timeline view — total face frames and
    # the active subset (mouth_opening passed the ASD threshold) per
    # turn, regardless of which cluster contributed.
    per_turn_total_count: dict[UUID, int] = {}
    per_turn_active_count: dict[UUID, int] = {}

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
            is_active = (
                det.mouth_opening is not None
                and det.mouth_opening >= MIN_ACTIVE_MOUTH_OPENING
            )
            if is_active:
                active_overlap_counts[key] = (
                    active_overlap_counts.get(key, 0) + 1
                )
            cluster_counts = per_turn_cluster_counts.setdefault(
                turn.segment_id, {},
            )
            cluster_counts[det.cluster_id] = (
                cluster_counts.get(det.cluster_id, 0) + 1
            )
            per_turn_total_count[turn.segment_id] = (
                per_turn_total_count.get(turn.segment_id, 0) + 1
            )
            if is_active:
                per_turn_active_count[turn.segment_id] = (
                    per_turn_active_count.get(turn.segment_id, 0) + 1
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
    timeline = _compute_timeline(
        speakers=speakers,
        per_turn_cluster_counts=per_turn_cluster_counts,
        per_turn_total_count=per_turn_total_count,
        per_turn_active_count=per_turn_active_count,
        face_stats=face_stats,
        voice_stats=voice_stats,
        preview_by_segment=preview_by_segment or {},
    )
    face_transcript_result = _compute_face_transcript(
        chunks=chunks or [],
        detections=detections,
        speakers=speakers,
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
        "timeline": timeline,
        "face_transcript": face_transcript_result["face_runs"],
        "conflated_turn_ids": face_transcript_result["conflated_turn_ids"],
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


def _compute_timeline(
    *,
    speakers: list[TurnRow],
    per_turn_cluster_counts: dict[UUID, dict[int, int]],
    per_turn_total_count: dict[UUID, int],
    per_turn_active_count: dict[UUID, int],
    face_stats: dict[int, dict],
    voice_stats: dict[str, dict],
    preview_by_segment: dict[UUID, str],
) -> list[dict]:
    """Per-turn chronological timeline for the follow-along view.

    One row per ``source_speakers`` turn with a non-NULL ``speaker_label``,
    sorted by ``start_ts``. Each row carries both modalities' cluster
    dominants, per-turn face counts (total + active), per-modality match
    columns (independent of cluster dominance), the current attribution,
    and an ``agreement`` classification:

    - ``agree``     — both cluster dominants set, same Person.
    - ``disagree``  — both set, different Person.
    - ``partial``   — exactly one side set.
    - ``none``      — neither side has a dominant Person.

    The classification compares cluster dominants (the strong signal),
    not per-turn modality matches — single-turn matches are noisier and
    sit in the row as supplementary detail.
    """
    out: list[dict] = []
    for turn in sorted(speakers, key=lambda t: t.start_ts):
        if not turn.speaker_label:
            continue

        voice_dom = voice_stats.get(turn.speaker_label, {}).get(
            "dominant_person_id",
        )
        cluster_counts = per_turn_cluster_counts.get(turn.segment_id)
        face_cluster_id: int | None = None
        face_dom: str | None = None
        if cluster_counts:
            face_cluster_id = max(
                cluster_counts.items(), key=lambda kv: kv[1],
            )[0]
            face_dom = face_stats.get(face_cluster_id, {}).get(
                "dominant_person_id",
            )

        if voice_dom and face_dom:
            agreement = "agree" if voice_dom == face_dom else "disagree"
        elif voice_dom or face_dom:
            agreement = "partial"
        else:
            agreement = "none"

        out.append({
            "segment_id": str(turn.segment_id),
            "start_ts": float(turn.start_ts),
            "end_ts": float(turn.end_ts),
            "duration": float(turn.end_ts - turn.start_ts),

            "speaker_label": turn.speaker_label,
            "voice_cluster_person_id": voice_dom,

            "face_cluster_id": face_cluster_id,
            "face_cluster_person_id": face_dom,
            "total_face_count": per_turn_total_count.get(turn.segment_id, 0),
            "active_face_count": per_turn_active_count.get(turn.segment_id, 0),

            "audio_match_person_id": (
                str(turn.audio_match_person_id)
                if turn.audio_match_person_id else None
            ),
            "visual_match_person_id": (
                str(turn.visual_match_person_id)
                if turn.visual_match_person_id else None
            ),

            "speaker_person_id": (
                str(turn.speaker_person_id)
                if turn.speaker_person_id else None
            ),
            "match_method": turn.match_method,
            "match_confidence": turn.match_confidence,

            "agreement": agreement,
            "preview_text": preview_by_segment.get(turn.segment_id, ""),
        })
    return out


def _compute_face_transcript(
    *,
    chunks: list[ChunkRow],
    detections: list[DetectionRow],
    speakers: list[TurnRow],
    face_stats: dict[int, dict],
) -> dict:
    """Phase 1 of face-driven re-segmentation: a face-clustered view of
    the conversation, plus a list of pyannote turns where face evidence
    says the speaker changed mid-turn.

    Returns ``{face_runs, conflated_turn_ids}``:

    - ``face_runs``: chunks grouped into consecutive runs of the same
      dominant face cluster. Each run carries its time window, the
      concatenated text, the dominant face cluster id + person, and
      the pyannote turn ids it overlaps. This is the "transcript as
      determined by face".
    - ``conflated_turn_ids``: pyannote turn ids that contain more than
      one face run — pyannote merged across a face transition, which is
      almost always a real speaker boundary. The operator worklist for
      Phase 2 re-segmentation.

    The pure-Python work is the dominant-face-per-chunk pass plus the
    run-detection walk. Both are linear in input size at podcast scale.
    """
    if not chunks:
        return {"face_runs": [], "conflated_turn_ids": []}

    # Per-chunk dominant face cluster — most detections falling in the
    # chunk's [start_ts, end_ts] window. Ties broken by cluster_id asc.
    # NULL when no detection overlapped.
    sorted_dets = sorted(detections, key=lambda d: d.frame_ts)
    sorted_chunks = sorted(chunks, key=lambda c: c.start_ts)

    # Interval walk: assign each detection to the chunk(s) covering its
    # frame_ts. Frames between chunks (Deepgram pause) belong to no
    # chunk; we drop them.
    chunk_cluster_counts: dict[UUID, dict[int, int]] = {}
    chunk_idx = 0
    for det in sorted_dets:
        if det.cluster_id is None:
            continue
        # Advance chunk_idx to the first chunk whose end_ts >= frame_ts.
        while (
            chunk_idx < len(sorted_chunks)
            and sorted_chunks[chunk_idx].end_ts < det.frame_ts
        ):
            chunk_idx += 1
        if chunk_idx >= len(sorted_chunks):
            break
        chunk = sorted_chunks[chunk_idx]
        if chunk.start_ts > det.frame_ts:
            continue  # detection fell in a gap between chunks
        counts = chunk_cluster_counts.setdefault(chunk.chunk_id, {})
        counts[det.cluster_id] = counts.get(det.cluster_id, 0) + 1

    chunk_dominant_cluster: dict[UUID, int | None] = {}
    for chunk in sorted_chunks:
        counts = chunk_cluster_counts.get(chunk.chunk_id)
        if not counts:
            chunk_dominant_cluster[chunk.chunk_id] = None
            continue
        # Stable tiebreak on cluster_id asc keeps face_runs grouping
        # deterministic across runs.
        best = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        chunk_dominant_cluster[chunk.chunk_id] = best[0]

    # Group consecutive same-cluster chunks into face_runs. None breaks
    # the run as a distinct value — "no face on screen" is a meaningful
    # segment of its own.
    face_runs: list[dict] = []
    cur: list[ChunkRow] = []
    cur_cluster: int | None = -1  # sentinel: nothing yet
    for chunk in sorted_chunks:
        cluster = chunk_dominant_cluster[chunk.chunk_id]
        if cluster != cur_cluster and cur:
            face_runs.append(_face_run_from_chunks(
                cur, cur_cluster, speakers, face_stats,
            ))
            cur = []
        cur.append(chunk)
        cur_cluster = cluster
    if cur:
        face_runs.append(_face_run_from_chunks(
            cur, cur_cluster, speakers, face_stats,
        ))

    # Conflation: for each pyannote turn, walk the chunks whose
    # MIDPOINT falls inside the turn's window and collect their
    # dominant face clusters. A turn with more than one distinct
    # non-None cluster contains face transitions pyannote merged
    # across — the operator worklist for Phase 2 re-segmentation.
    #
    # Using chunk midpoints (not face_run boundaries) avoids false
    # positives at turn boundaries: a face_run ending exactly when
    # the next turn starts shouldn't get attributed to that next turn
    # just because the touching-boundary overlap rule says so.
    sorted_speakers = sorted(speakers, key=lambda t: t.start_ts)
    turn_clusters: dict[UUID, set[int]] = {}
    speaker_idx = 0
    for chunk in sorted_chunks:
        cluster = chunk_dominant_cluster.get(chunk.chunk_id)
        if cluster is None:
            continue
        midpoint = (chunk.start_ts + chunk.end_ts) / 2.0
        while (
            speaker_idx < len(sorted_speakers)
            and sorted_speakers[speaker_idx].end_ts < midpoint
        ):
            speaker_idx += 1
        for i in range(speaker_idx, len(sorted_speakers)):
            turn = sorted_speakers[i]
            if turn.start_ts > midpoint:
                break
            if turn.start_ts <= midpoint <= turn.end_ts:
                turn_clusters.setdefault(turn.segment_id, set()).add(cluster)
                break  # midpoint can only be in one turn
    conflated = [
        str(tid)
        for tid, clusters in turn_clusters.items()
        if len(clusters) > 1
    ]

    return {
        "face_runs": face_runs,
        "conflated_turn_ids": sorted(conflated),
    }


def _face_run_from_chunks(
    run_chunks: list[ChunkRow],
    cluster_id: int | None,
    speakers: list[TurnRow],
    face_stats: dict[int, dict],
) -> dict:
    """Materialise a single face_run from a list of consecutive chunks
    that share a dominant face cluster. Joins the chunks' text, picks
    the start/end ts from the boundary chunks, and finds every pyannote
    turn whose [start_ts, end_ts] overlaps the run."""
    start_ts = run_chunks[0].start_ts
    end_ts = run_chunks[-1].end_ts
    text = " ".join(c.text for c in run_chunks if c.text).strip()

    person_id: str | None = None
    if cluster_id is not None:
        person_id = face_stats.get(cluster_id, {}).get("dominant_person_id")

    # Pyannote turn ids this run overlaps in time. Touching boundaries
    # count, same as bucket_chunks_to_spans semantics.
    overlapping_turns = [
        str(t.segment_id)
        for t in speakers
        if t.end_ts >= start_ts and t.start_ts <= end_ts
    ]

    return {
        "face_cluster_id": cluster_id,
        "face_cluster_person_id": person_id,
        "start_ts": float(start_ts),
        "end_ts": float(end_ts),
        "duration": float(end_ts - start_ts),
        "chunk_count": len(run_chunks),
        "text": text,
        "pyannote_turn_ids": overlapping_turns,
    }


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
            "timeline": [],
            "face_transcript": [],
            "conflated_turn_ids": [],
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

    # Group by ``coalesce(cluster_label, speaker_label)`` so any custom
    # clustering pass (HDBSCAN, manual edits, face-driven re-segmentation)
    # takes precedence over pyannote's raw SPEAKER_NN — matches the
    # Voices tab and AssignVoice flow.
    effective_label = func.coalesce(
        SourceSpeaker.cluster_label, SourceSpeaker.speaker_label,
    ).label("speaker_label")
    speaker_rows = (
        session.query(
            SourceSpeaker.segment_id,
            SourceSpeaker.start_ts,
            SourceSpeaker.end_ts,
            effective_label,
            SourceSpeaker.speaker_person_id,
            SourceSpeaker.match_method,
            SourceSpeaker.audio_match_person_id,
            SourceSpeaker.visual_match_person_id,
            SourceSpeaker.match_confidence,
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
            audio_match_person_id=r.audio_match_person_id,
            visual_match_person_id=r.visual_match_person_id,
            match_confidence=(
                float(r.match_confidence)
                if r.match_confidence is not None else None
            ),
        )
        for r in speaker_rows
    ]

    preview_by_segment = fetch_full_turn_text(
        session,
        [(s.segment_id, s.start_ts, s.end_ts) for s in speakers],
        document_id=doc.document_id,
    )

    chunk_rows = (
        session.query(
            SourceChunk.chunk_id,
            SourceChunk.start_ts,
            SourceChunk.end_ts,
            SourceChunk.clean_text,
            SourceChunk.raw_text,
        )
        .filter(SourceChunk.document_id == doc.document_id)
        .filter(SourceChunk.start_ts.isnot(None))
        .filter(SourceChunk.end_ts.isnot(None))
        .order_by(SourceChunk.start_ts)
        .all()
    )
    chunks = [
        ChunkRow(
            chunk_id=r.chunk_id,
            start_ts=float(r.start_ts),
            end_ts=float(r.end_ts),
            text=(r.clean_text or r.raw_text or "").strip(),
        )
        for r in chunk_rows
    ]

    return compute_alignment(
        detections, speakers, preview_by_segment, chunks=chunks,
    )
