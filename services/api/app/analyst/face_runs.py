"""Face-runs derivation over a face-track JSON.

Slice A.5 of the cluster-manager work. Given the existing face-track
JSON (no embeddings, just bboxes + matched person_id per detection),
group detections into **face positions** by spatial clustering and then
emit per-position **runs** of contiguous (person_id, ts).

The runs view answers the question "where does the attribution change?"
which is where operator effort actually pays off — much higher signal
than the gallery's evenly-spaced thumbnails.

Spatial clustering is greedy online: each detection joins the nearest
existing position whose centroid is within ``CENTROID_EPS`` pixels, or
seeds a new position. Robust enough for static-camera podcast formats
like Bloke In A Bar. Once Slice B persists per-detection embeddings,
swap this for kNN clustering on the 512-dim ArcFace.

Run detection walks each position's detections in time order and emits
a run boundary when (a) ``person_id`` changes, or (b) the gap between
consecutive detections exceeds ``RUN_GAP_SECONDS``. Single-frame
flickers aren't smoothed at this layer — easier to see the raw signal
during operator review.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from jeromelu_shared.db import SourceFaceCluster, SourceFaceDetection

# Distance in source-frame pixels — two detections within this much of
# each other's centre are "the same position". 120px is appropriate for
# 360p (640×360) static-camera podcasts where the host's bbox can wander
# 50-100px frame-to-frame without actually being a different position.
CENTROID_EPS = 120.0

# Cluster centroids within this much are merged in the consolidation
# pass. Catches the case where greedy assignment seeds two adjacent
# positions because the very first detections happened to land on
# opposite sides of the eventual centroid.
CONSOLIDATE_EPS = 100.0

# Positions with fewer detections than this are dropped — they're almost
# always single-frame noise from bumper shots / cutaways / partial faces
# at the frame edge.
MIN_POSITION_DETECTIONS = 5

# Maximum gap between consecutive detections in a position before the
# current run is sealed and a new one starts. Cuts at scene boundaries
# without erasing brief "look-down" pauses.
RUN_GAP_SECONDS = 5.0

# Runs shorter than this many frames AND surrounded by same-person runs
# are absorbed into their neighbours. At 1fps, 5 frames = 5 seconds —
# typical brief look-down / cutaway / graphic-overlay duration during
# which the visual matcher (correctly) emits no match. Surfacing each as
# its own row drowns the genuine transitions in noise.
SMOOTH_FLICKER_FRAMES = 5


def _bbox_centre(bbox: list[float]) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _assign_positions(detections: list[dict]) -> list[int]:
    """Greedy online cluster. Returns a parallel list of position-ids
    (one per input detection). Position centroids drift to the running
    mean of their members so a slowly panning camera still tracks."""
    positions: list[dict[str, Any]] = []
    out: list[int] = []
    for det in detections:
        cx, cy = _bbox_centre(det["bbox"])
        best_idx = -1
        best_d = CENTROID_EPS
        for pi, pos in enumerate(positions):
            d = ((pos["cx"] - cx) ** 2 + (pos["cy"] - cy) ** 2) ** 0.5
            if d < best_d:
                best_d, best_idx = d, pi
        if best_idx < 0:
            positions.append({"cx": cx, "cy": cy, "n": 1})
            out.append(len(positions) - 1)
        else:
            pos = positions[best_idx]
            n = pos["n"]
            pos["cx"] = (pos["cx"] * n + cx) / (n + 1)
            pos["cy"] = (pos["cy"] * n + cy) / (n + 1)
            pos["n"] = n + 1
            out.append(best_idx)
    return out


def _consolidate_positions(buckets: list[list[dict]]) -> list[list[dict]]:
    """Merge near-twin clusters and drop noise clusters.

    Step 1: repeatedly merge the closest pair of positions whose
    centroids are within ``CONSOLIDATE_EPS``. The biggest cluster
    absorbs the smaller one.

    Step 2: drop clusters with fewer than ``MIN_POSITION_DETECTIONS``
    members. These are almost always edge-case detections from bumper
    shots / cutaways.
    """
    def centroid(bucket: list[dict]) -> tuple[float, float]:
        n = max(1, len(bucket))
        sx = sum(_bbox_centre(d["bbox"])[0] for d in bucket) / n
        sy = sum(_bbox_centre(d["bbox"])[1] for d in bucket) / n
        return sx, sy

    buckets = [b for b in buckets if b]  # drop empties

    while True:
        if len(buckets) < 2:
            break
        cents = [centroid(b) for b in buckets]
        best_pair = None
        best_d = CONSOLIDATE_EPS
        for i in range(len(buckets)):
            for j in range(i + 1, len(buckets)):
                d = (
                    (cents[i][0] - cents[j][0]) ** 2
                    + (cents[i][1] - cents[j][1]) ** 2
                ) ** 0.5
                if d < best_d:
                    best_d, best_pair = d, (i, j)
        if best_pair is None:
            break
        i, j = best_pair
        # Bigger absorbs smaller.
        if len(buckets[i]) >= len(buckets[j]):
            buckets[i].extend(buckets[j])
            del buckets[j]
        else:
            buckets[j].extend(buckets[i])
            del buckets[i]

    return [b for b in buckets if len(b) >= MIN_POSITION_DETECTIONS]


def _label_positions(centroids: list[tuple[float, float]]) -> list[str]:
    """Sort positions by x-centroid and label them by relative location.
    Two positions → Left/Right; three → Left/Centre/Right; one → Centre;
    four+ → Position N (numbered by left-to-right order)."""
    n = len(centroids)
    if n == 0:
        return []
    indexed = sorted(range(n), key=lambda i: centroids[i][0])
    labels = [""] * n
    if n == 1:
        labels[indexed[0]] = "Centre"
    elif n == 2:
        labels[indexed[0]] = "Left"
        labels[indexed[1]] = "Right"
    elif n == 3:
        labels[indexed[0]] = "Left"
        labels[indexed[1]] = "Centre"
        labels[indexed[2]] = "Right"
    else:
        for rank, i in enumerate(indexed):
            labels[i] = f"Position {rank + 1}"
    return labels


def _detect_runs_for_position(detections: list[dict]) -> list[dict]:
    """Detections must already be filtered to one position and sorted
    by ``ts``. Emits one run per contiguous (person_id, time-range).
    Runs include start/end samples so the UI can render two thumbnails
    bracketing the segment.

    Single-frame flickers between same-person runs are smoothed out
    after raw detection — see ``_smooth_flickers``.
    """
    if not detections:
        return []
    raw: list[tuple[int, int]] = []  # (start_idx, end_idx) per raw run
    cur_pid = detections[0].get("person_id")
    cur_start_idx = 0
    last_ts = detections[0]["ts"]
    for i in range(1, len(detections)):
        det = detections[i]
        same_pid = det.get("person_id") == cur_pid
        gap = det["ts"] - last_ts
        if same_pid and gap <= RUN_GAP_SECONDS:
            last_ts = det["ts"]
            continue
        raw.append((cur_start_idx, i - 1))
        cur_pid = det.get("person_id")
        cur_start_idx = i
        last_ts = det["ts"]
    raw.append((cur_start_idx, len(detections) - 1))

    smoothed = _smooth_flickers(detections, raw)
    return [_run_from_slice(detections, s, e) for s, e in smoothed]


def _smooth_flickers(
    detections: list[dict],
    runs: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Absorb a short run into its neighbours when both neighbours
    agree on a different ``person_id``. One-frame None-flicker between
    two Denan runs becomes a single Denan run.

    Repeated until no merges happen — handles consecutive flickers
    correctly without a separate two-pass pass.
    """
    while True:
        merged = False
        out: list[tuple[int, int]] = []
        i = 0
        while i < len(runs):
            s, e = runs[i]
            length = e - s + 1
            if (
                0 < i < len(runs) - 1
                and length < SMOOTH_FLICKER_FRAMES
                and detections[runs[i - 1][0]].get("person_id")
                == detections[runs[i + 1][0]].get("person_id")
                and detections[s].get("person_id")
                != detections[runs[i - 1][0]].get("person_id")
            ):
                # Merge runs[i-1], runs[i], runs[i+1] into one.
                prev_s, _ = out.pop()
                _, next_e = runs[i + 1]
                out.append((prev_s, next_e))
                merged = True
                i += 2  # skip the next run since we just absorbed it
            else:
                out.append((s, e))
                i += 1
        runs = out
        if not merged:
            return runs


def _run_from_slice(detections: list[dict], start_idx: int, end_idx: int) -> dict:
    start = detections[start_idx]
    end = detections[end_idx]
    sims = [
        d["similarity"]
        for d in detections[start_idx : end_idx + 1]
        if d.get("similarity") is not None
    ]
    return {
        "person_id": start.get("person_id"),
        "start_ts": start["ts"],
        "end_ts": end["ts"],
        "frame_count": end_idx - start_idx + 1,
        "avg_similarity": (sum(sims) / len(sims)) if sims else None,
        "start_sample": {
            "ts": start["ts"],
            "bbox": start["bbox"],
        },
        "end_sample": {
            "ts": end["ts"],
            "bbox": end["bbox"],
        },
    }


def compute_face_runs(face_track: dict) -> dict:
    """Top-level: turn a face-track JSON into the runs payload.

    Output:
      {
        positions: [
          {
            position_id: int,
            label: "Left" | "Centre" | "Right" | "Position N",
            centroid: [cx, cy],
            detection_count: int,
            runs: [run, ...],
          },
          ...
        ]
      }

    Positions are sorted by detection count (busiest first) so the most
    important positions render at the top.
    """
    flat: list[dict] = []
    for frame in face_track.get("frames", []):
        ts = float(frame.get("ts") or 0.0)
        for face in frame.get("faces", []):
            flat.append(
                {
                    "ts": ts,
                    "bbox": face["bbox"],
                    "person_id": face.get("person_id"),
                    "similarity": face.get("similarity"),
                }
            )

    if not flat:
        return {"positions": []}

    pos_ids = _assign_positions(flat)
    n_positions = max(pos_ids) + 1

    by_position: list[list[dict]] = [[] for _ in range(n_positions)]
    for det, pid in zip(flat, pos_ids):
        by_position[pid].append(det)

    # Consolidation: merge positions whose centroids are within
    # CONSOLIDATE_EPS, then drop positions whose detection count is
    # under MIN_POSITION_DETECTIONS. Greedy clustering on the previous
    # pass can produce two adjacent clusters whose drift never closes
    # the gap — this fixes that.
    by_position = _consolidate_positions(by_position)

    for bucket in by_position:
        bucket.sort(key=lambda d: d["ts"])

    centroids = [
        (
            sum(_bbox_centre(d["bbox"])[0] for d in bucket) / max(1, len(bucket)),
            sum(_bbox_centre(d["bbox"])[1] for d in bucket) / max(1, len(bucket)),
        )
        for bucket in by_position
    ]
    labels = _label_positions(centroids)

    positions = []
    for pid, bucket in enumerate(by_position):
        runs = _detect_runs_for_position(bucket)
        positions.append(
            {
                "position_id": pid,
                "label": labels[pid],
                "centroid": list(centroids[pid]),
                "detection_count": len(bucket),
                "runs": runs,
            }
        )
    positions.sort(key=lambda p: -p["detection_count"])
    return {"positions": positions}


# ---------------------------------------------------------------------------
# Slice B PR 2 — runs from persisted source_face_detections + clusters
# ---------------------------------------------------------------------------

#: Letters used to label clusters for the operator. After 26 we fall
#: back to ``Cluster 27`` numerics, which won't happen at podcast scale
#: but keeps the helper safe.
_CLUSTER_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _cluster_label(cluster_id: int | None) -> str:
    """Stable, human-friendly identifier per cluster within a source.

    cluster_id 0 → "Cluster A", 1 → "Cluster B", ... 25 → "Cluster Z",
    then "Cluster 27" onwards. ``None`` (HDBSCAN noise) → "Outliers".
    The clustering pass already re-ranks labels by size descending, so
    "Cluster A" is always the most-detected face in the video.
    """
    if cluster_id is None:
        return "Outliers"
    if 0 <= cluster_id < len(_CLUSTER_LETTERS):
        return f"Cluster {_CLUSTER_LETTERS[cluster_id]}"
    return f"Cluster {cluster_id + 1}"


def _detect_runs_for_cluster(detections: list[dict]) -> list[dict]:
    """Same break rules as the spatial path: ``matched_person_id``
    change or >RUN_GAP_SECONDS gap. Detections must already be sorted
    by ``ts``. Smoothing same as the spatial detector.
    """
    if not detections:
        return []
    raw: list[tuple[int, int]] = []
    cur_pid = detections[0].get("person_id")
    cur_start_idx = 0
    last_ts = detections[0]["ts"]
    for i in range(1, len(detections)):
        det = detections[i]
        same_pid = det.get("person_id") == cur_pid
        gap = det["ts"] - last_ts
        if same_pid and gap <= RUN_GAP_SECONDS:
            last_ts = det["ts"]
            continue
        raw.append((cur_start_idx, i - 1))
        cur_pid = det.get("person_id")
        cur_start_idx = i
        last_ts = det["ts"]
    raw.append((cur_start_idx, len(detections) - 1))

    smoothed = _smooth_flickers(detections, raw)
    return [_run_from_slice(detections, s, e) for s, e in smoothed]


def detections_exist(session: Session, source_id: UUID) -> bool:
    """Cheap check the endpoint uses to decide whether to take the
    detection-backed runs path or fall through to the legacy face-track
    JSON path."""
    count = session.query(sa_func.count(SourceFaceDetection.detection_id)).filter(
        SourceFaceDetection.source_id == source_id,
    ).scalar() or 0
    return count > 0


def compute_face_runs_from_detections(
    session: Session,
    source_id: UUID,
    *,
    include_excluded: bool = False,
) -> dict:
    """Slice B PR 2 — build runs grouped by ``cluster_id`` instead of by
    spatial bbox position.

    Each top-level entry in the returned ``positions`` list represents
    one face cluster (visual identity) rather than a screen position.
    The wire shape matches :func:`compute_face_runs` so the existing
    frontend keeps working; new ``cluster_id`` fields appear per
    position and per run so the UI can show "Cluster A" alongside the
    matched-person attribution.

    Unclustered detections (HDBSCAN noise) are grouped into a single
    "Outliers" entry so they're still visible — they're often partial
    faces / scene transitions, but occasionally a one-shot guest who
    just didn't pass the min-cluster-size gate.
    """
    rows = (
        session.query(SourceFaceDetection)
        .filter(SourceFaceDetection.source_id == source_id)
        .order_by(SourceFaceDetection.frame_ts)
        .all()
    )

    # Pull per-cluster metadata in one query — labels, kinds, exclusion
    # flags. NULL cluster_id (HDBSCAN noise) has no row here; treated as
    # the implicit Outliers bucket.
    cluster_meta_rows = (
        session.query(SourceFaceCluster)
        .filter(SourceFaceCluster.source_id == source_id)
        .all()
    )
    meta_by_cluster: dict[int, SourceFaceCluster] = {
        m.cluster_id: m for m in cluster_meta_rows
    }

    by_cluster: dict[int | None, list[dict]] = {}
    for r in rows:
        det = {
            "ts": float(r.frame_ts),
            "bbox": [r.bbox_x1, r.bbox_y1, r.bbox_x2, r.bbox_y2],
            "person_id": str(r.matched_person_id) if r.matched_person_id else None,
            "similarity": (
                float(r.match_score) if r.match_score is not None else None
            ),
        }
        by_cluster.setdefault(r.cluster_id, []).append(det)

    # Sort: real clusters by size desc (matches the relabel order from
    # the clustering pass; with cluster_id 0 being the biggest), then
    # the Outliers bucket last so it doesn't crowd the top of the UI.
    items = sorted(
        [(cid, dets) for cid, dets in by_cluster.items() if cid is not None],
        key=lambda kv: -len(kv[1]),
    )
    if None in by_cluster:
        items.append((None, by_cluster[None]))

    positions: list[dict] = []
    excluded_count = 0
    # position_id starts from 0 for the response — independent of
    # cluster_id since clusters may include None and we want stable
    # per-source integer IDs for the UI.
    for pid, (cluster_id, bucket) in enumerate(items):
        meta = meta_by_cluster.get(cluster_id) if cluster_id is not None else None

        # Default-excluded clusters (portraits, noise) skip the UI
        # unless explicitly requested. We still count them so the UI
        # can show "N more clusters hidden — show all?".
        if meta is not None and meta.excluded and not include_excluded:
            excluded_count += 1
            continue

        bucket.sort(key=lambda d: d["ts"])
        runs = _detect_runs_for_cluster(bucket)
        # Attach cluster_id to each run so the bulk-assign action can
        # send it back to the API (saves a round-trip).
        for run in runs:
            run["cluster_id"] = cluster_id
        centroid = (
            sum(_bbox_centre(d["bbox"])[0] for d in bucket) / max(1, len(bucket)),
            sum(_bbox_centre(d["bbox"])[1] for d in bucket) / max(1, len(bucket)),
        )

        # Label precedence: operator override > auto-generated.
        label = (
            meta.label if meta is not None and meta.label
            else _cluster_label(cluster_id)
        )

        # Dominant person across the cluster's detections. Most clusters
        # are one identity, so the UI can drop per-row name labels and
        # just show the dominant one in the cluster header. Runs whose
        # person_id differs from the dominant get a small visual tag.
        person_counts: dict[str, int] = {}
        for det in bucket:
            pid_str = det.get("person_id")
            if pid_str:
                person_counts[pid_str] = person_counts.get(pid_str, 0) + 1
        dominant_person_id: str | None = None
        dominant_share: float | None = None
        if person_counts:
            dom_pid, dom_count = max(
                person_counts.items(), key=lambda kv: kv[1],
            )
            dominant_person_id = dom_pid
            dominant_share = dom_count / len(bucket)

        positions.append({
            "position_id": pid,
            "label": label,
            "cluster_id": cluster_id,
            "centroid": list(centroid),
            "detection_count": len(bucket),
            "runs": runs,
            # Cluster-level attribution — UI uses this so each row doesn't
            # have to repeat the Person name when the whole cluster is
            # one identity. dominant_person_name resolved in the caller
            # alongside the run-level person names.
            "dominant_person_id": dominant_person_id,
            "dominant_share": dominant_share,
            # Slice B PR 2.5 — surface cluster metadata so the UI can
            # render the kind tag + override controls. ``kind`` is the
            # operator override (NULL if unreviewed); ``detected_kind``
            # is the auto-tag the heuristic landed.
            "kind": meta.kind if meta else None,
            "detected_kind": meta.detected_kind if meta else None,
            "excluded": bool(meta.excluded) if meta else False,
            "label_override": meta.label if meta else None,
            "notes": meta.notes if meta else None,
            "stats": {
                "mouth_open_std": meta.mouth_open_std if meta else None,
                "centroid_std": meta.centroid_std if meta else None,
                "temporal_density": meta.temporal_density if meta else None,
            } if meta else None,
        })

    return {"positions": positions, "excluded_count": excluded_count}
