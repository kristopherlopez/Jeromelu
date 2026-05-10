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
