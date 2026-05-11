"""Per-source face clustering — Slice B PR 2.

Loads every ``source_face_detections`` embedding for one source, runs
HDBSCAN with cosine distance, and writes the cluster assignment back to
the table. Idempotent: re-running re-clusters from the current detection
set (useful after the registry grows or new detections land).

Why HDBSCAN: ArcFace embeddings of the same face cluster naturally and
the count of "people in this video" isn't known a priori, so we want a
density-based algorithm that figures out N for us and handles outliers
(motion-blurred frames, partial faces, side profiles drifting) without
forcing them into the nearest neighbour's cluster.

Why NOT pre-specify K with k-means: misses one-shot guests entirely
(they'd merge into the nearest host), and produces inflated counts when
two camera angles of the same person look slightly different — HDBSCAN
merges those via its mutual-reachability metric.

Scope: single-source clustering. Cross-source linking is the next slice
(PR 3) and runs over the HNSW index without re-clustering anything.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import numpy as np
from sklearn.cluster import HDBSCAN
from sqlalchemy import update
from sqlalchemy.orm import Session

from jeromelu_shared.db import SourceFaceCluster, SourceFaceDetection

logger = logging.getLogger(__name__)


#: Minimum number of detections to call something a cluster. At 1 fps
#: that's 20 seconds of cumulative screen time — enough to be worth
#: surfacing as its own row in the runs view.
DEFAULT_MIN_CLUSTER_SIZE = 20

#: Lower = fewer points labelled as noise. With ArcFace's tight
#: same-person clusters, 5 keeps real clusters intact while still
#: tagging genuinely-anomalous detections (heavy motion blur, partial
#: faces clipped at frame edges) as outliers.
DEFAULT_MIN_SAMPLES = 5


@dataclass
class ClusterStats:
    """Return shape from :func:`cluster_source_detections`."""
    source_id: UUID
    n_detections: int
    n_clusters: int
    n_noise: int       # detections labelled cluster_id = NULL (HDBSCAN's -1)
    cluster_sizes: list[int]  # sorted descending, one entry per real cluster


def cluster_source_detections(
    session: Session,
    source_id: UUID,
    *,
    min_cluster_size: int = DEFAULT_MIN_CLUSTER_SIZE,
    min_samples: int = DEFAULT_MIN_SAMPLES,
) -> ClusterStats:
    """Cluster every detection for ``source_id`` and write back
    ``cluster_id``.

    Loads embeddings into memory (one numpy stack), runs HDBSCAN with
    cosine distance, then UPDATEs cluster_id per detection in a single
    batched query. Detections labelled noise by HDBSCAN get
    ``cluster_id = NULL``.
    """
    rows = (
        session.query(SourceFaceDetection.detection_id, SourceFaceDetection.embedding)
        .filter(SourceFaceDetection.source_id == source_id)
        .order_by(SourceFaceDetection.frame_ts)
        .all()
    )
    if not rows:
        logger.info("Nothing to cluster for source %s — no detections", source_id)
        return ClusterStats(
            source_id=source_id,
            n_detections=0,
            n_clusters=0,
            n_noise=0,
            cluster_sizes=[],
        )

    detection_ids = [r.detection_id for r in rows]
    # pgvector returns lists when accessed via the ORM — stack into a
    # (N, 512) float32 array. ArcFace embeddings aren't L2-normalised
    # by default; HDBSCAN with metric='cosine' handles that for us
    # (cosine distance is scale-invariant).
    embeddings = np.asarray([r.embedding for r in rows], dtype=np.float32)
    logger.info(
        "Clustering %d detections for source %s (min_cluster=%d, min_samples=%d)",
        len(rows), source_id, min_cluster_size, min_samples,
    )

    # Adjust thresholds for very small sources — clamping prevents the
    # "min_cluster_size > n_samples" sklearn raise on early backfills
    # or short clips that produced fewer detections than the default.
    effective_min_cluster = min(min_cluster_size, max(2, len(rows) // 4))
    effective_min_samples = min(min_samples, effective_min_cluster)
    clusterer = HDBSCAN(
        metric="cosine",
        min_cluster_size=effective_min_cluster,
        min_samples=effective_min_samples,
        # `excluded` algorithm names like prims_balltree don't accept
        # cosine; brute-force pairwise is fine at single-digit thousands.
        algorithm="brute",
    )
    labels = clusterer.fit_predict(embeddings)

    # Re-rank cluster labels so the biggest cluster is 0, second-biggest
    # is 1, etc. Stable: same data → same labels, useful for the UI's
    # "Cluster A / B / C" naming convention.
    real_labels = [int(lbl) for lbl in labels if lbl != -1]
    sizes_per_label: dict[int, int] = {}
    for lbl in real_labels:
        sizes_per_label[lbl] = sizes_per_label.get(lbl, 0) + 1
    ranked = sorted(sizes_per_label.items(), key=lambda kv: -kv[1])
    relabel = {old: new for new, (old, _) in enumerate(ranked)}

    n_noise = 0
    per_detection_cluster: list[int | None] = []
    for lbl in labels:
        if lbl == -1:
            per_detection_cluster.append(None)
            n_noise += 1
        else:
            per_detection_cluster.append(relabel[int(lbl)])

    # Write back. One UPDATE per detection — clean, predictable, and at
    # ~2700 rows still single-digit seconds. If this becomes a bottleneck
    # at higher scale, batch into per-cluster updates using
    # detection_id IN (...).
    for det_id, cluster_id in zip(detection_ids, per_detection_cluster):
        session.execute(
            update(SourceFaceDetection)
            .where(SourceFaceDetection.detection_id == det_id)
            .values(cluster_id=cluster_id),
        )
    session.commit()

    cluster_sizes = [size for _, size in ranked]
    logger.info(
        "Clustered %d detections for source %s → %d cluster(s), %d noise. Sizes: %s",
        len(rows), source_id, len(cluster_sizes), n_noise,
        cluster_sizes[:10] + (["..."] if len(cluster_sizes) > 10 else []),
    )

    return ClusterStats(
        source_id=source_id,
        n_detections=len(rows),
        n_clusters=len(cluster_sizes),
        n_noise=n_noise,
        cluster_sizes=cluster_sizes,
    )


# ---------------------------------------------------------------------------
# Cluster auto-tagging — distinguish people from wall art / portraits / noise
# ---------------------------------------------------------------------------

#: Mouth-opening standard deviation below this is considered "frozen
#: face" — a portrait or framed photo. Real people talking sit at
#: 0.05-0.15; even silent listening shifts produce > 0.01 over a span
#: of frames. 0.005 is well below detector jitter.
PORTRAIT_MOUTH_STD = 0.005

#: Bbox-centroid standard deviation in source-frame pixels below this
#: combined with low mouth_std indicates a portrait. Detector jitter
#: on a real bbox is ~1-2 pixels; 5 keeps room for real people who
#: barely move (rare but possible for a guest reading from a script).
PORTRAIT_CENTROID_STD = 5.0

#: When centroid_std is essentially zero, it's a portrait regardless
#: of mouth_std. Lip landmarks can jitter on a frozen face producing
#: modest mouth_std up to ~0.01, but if the bbox itself has never
#: moved, it's wall art. Verified 2026-05-12: 4 clusters with
#: centroid_std in 0.1-0.3 range and mouth_std 0.005-0.009 were all
#: confirmed portraits the original AND-gate missed. Real hosts in
#: the same source had centroid_std > 12 px — large gap with no
#: ambiguity in between.
PORTRAIT_CENTROID_STRICT = 2.0

#: Diagnostic only — not gated. Initially thought a portrait would
#: appear in 90%+ of in-span frames, but multi-cam shows cut between
#: camera angles, so wall art is only on screen ~50-60% of the time
#: (same density as a host). Real signal is mouth + centroid stability.
#: Kept as a stored stat so a future model can re-evaluate.
PORTRAIT_TEMPORAL_DENSITY_HINT = 0.9

#: Clusters smaller than this are tagged 'noise' — usually one-off
#: misdetections at frame edges or partial faces. Excluded from the
#: default runs view.
NOISE_MIN_DETECTIONS = 10


@dataclass
class ClusterAnalysis:
    cluster_id: int
    detection_count: int
    mouth_open_std: float
    centroid_std: float
    temporal_density: float
    detected_kind: str  # 'person' | 'portrait' | 'noise'


def _classify_cluster(
    detection_count: int,
    mouth_open_std: float,
    centroid_std: float,
    temporal_density: float,
) -> str:
    """Pure function so the heuristic is unit-testable and explainable.

    Verified on multi-cam Bloke In A Bar source 2026-05-12: three known
    wall-portrait clusters all landed at mouth_std ~0.003 + centroid_std
    < 1 px; real hosts at mouth_std > 0.018 + centroid_std > 14 px.
    Density was a red herring — multi-cam puts portraits and hosts at
    the same density (~0.57) since each is only visible on certain
    camera angles. Kept ``temporal_density`` as a stored diagnostic.
    """
    if detection_count < NOISE_MIN_DETECTIONS:
        return "noise"
    # Strong portrait signal: bbox is essentially static. Don't gate on
    # mouth_std here — landmark jitter on a frozen face can push it as
    # high as 0.01 even though nothing's actually moving.
    if centroid_std < PORTRAIT_CENTROID_STRICT:
        return "portrait"
    # Moderate portrait signal: both mouth and centroid are flat. Kept
    # so a face with mild centroid drift but no mouth activity (e.g.
    # poster catching a breeze, or a less-static framed photo) still
    # auto-tags correctly.
    if (
        mouth_open_std < PORTRAIT_MOUTH_STD
        and centroid_std < PORTRAIT_CENTROID_STD
    ):
        return "portrait"
    return "person"


def analyse_clusters(session: Session, source_id: UUID) -> list[ClusterAnalysis]:
    """Compute per-cluster stats over already-clustered detections and
    upsert ``source_face_clusters`` rows. Auto-tags ``detected_kind``
    via the heuristic above; operator overrides in ``kind`` are
    preserved (the analyser never touches the operator-facing fields).

    Idempotent: re-runs replace the stats / detected_kind on the
    existing rows. Returns the list of per-cluster analyses.
    """
    rows = (
        session.query(
            SourceFaceDetection.cluster_id,
            SourceFaceDetection.frame_ts,
            SourceFaceDetection.bbox_x1,
            SourceFaceDetection.bbox_y1,
            SourceFaceDetection.bbox_x2,
            SourceFaceDetection.bbox_y2,
            SourceFaceDetection.mouth_opening,
        )
        .filter(SourceFaceDetection.source_id == source_id)
        .all()
    )
    if not rows:
        return []

    # Bucket detections per cluster_id, including the noise bucket
    # (cluster_id=NULL) so we can emit its row too.
    by_cluster: dict[int | None, dict[str, list[float]]] = {}
    for r in rows:
        bucket = by_cluster.setdefault(r.cluster_id, {
            "ts": [], "cx": [], "cy": [], "mouth": [],
        })
        bucket["ts"].append(float(r.frame_ts))
        bucket["cx"].append((float(r.bbox_x1) + float(r.bbox_x2)) / 2.0)
        bucket["cy"].append((float(r.bbox_y1) + float(r.bbox_y2)) / 2.0)
        if r.mouth_opening is not None:
            bucket["mouth"].append(float(r.mouth_opening))

    analyses: list[ClusterAnalysis] = []
    for cluster_id, data in by_cluster.items():
        if cluster_id is None:
            # The NULL bucket is HDBSCAN noise — always 'noise' kind by
            # definition. Skip the heuristic to avoid divide-by-zero on
            # tiny spans.
            cnt = len(data["ts"])
            analyses.append(ClusterAnalysis(
                cluster_id=-1,  # use -1 sentinel; not stored — see below
                detection_count=cnt,
                mouth_open_std=0.0,
                centroid_std=0.0,
                temporal_density=0.0,
                detected_kind="noise",
            ))
            continue

        ts = np.asarray(data["ts"], dtype=np.float64)
        cx = np.asarray(data["cx"], dtype=np.float64)
        cy = np.asarray(data["cy"], dtype=np.float64)
        mouth = (
            np.asarray(data["mouth"], dtype=np.float64)
            if data["mouth"] else np.zeros(1)
        )

        # std() on a single-element array is 0 by default — fine here,
        # those clusters land in the 'noise' branch via count.
        centroid_std = float(
            np.sqrt(np.var(cx) + np.var(cy))
        )
        mouth_std = float(np.std(mouth))
        span = float(ts.max() - ts.min())
        # density = detections per second over the cluster's lifespan
        # divided by the sampling rate (assumed 1 fps from visual_id).
        # Cap at 1.0 so a cluster denser than the sampling rate (which
        # shouldn't happen at 1 fps but might at higher rates) doesn't
        # confuse the threshold.
        density = min(1.0, len(ts) / max(1.0, span)) if span > 0 else 1.0

        detected = _classify_cluster(
            detection_count=len(ts),
            mouth_open_std=mouth_std,
            centroid_std=centroid_std,
            temporal_density=density,
        )
        analyses.append(ClusterAnalysis(
            cluster_id=cluster_id,
            detection_count=len(ts),
            mouth_open_std=mouth_std,
            centroid_std=centroid_std,
            temporal_density=density,
            detected_kind=detected,
        ))

    # Upsert source_face_clusters rows. We never touch operator-set
    # fields (kind, label, notes, attributed_person_id) — those persist
    # across re-runs. The analyser writes detected_kind, stats, count,
    # and sets `excluded=true` for first-time portrait/noise unless an
    # operator override already exists.
    now = datetime.now(timezone.utc)
    for a in analyses:
        # NULL cluster bucket is observability-only; skip persistence
        # since the table's PK is (source_id, cluster_id) and we don't
        # want a -1 sentinel row leaking into the runs view.
        if a.cluster_id < 0:
            continue
        existing = session.query(SourceFaceCluster).filter(
            SourceFaceCluster.source_id == source_id,
            SourceFaceCluster.cluster_id == a.cluster_id,
        ).first()
        if existing is None:
            session.add(SourceFaceCluster(
                source_id=source_id,
                cluster_id=a.cluster_id,
                kind=None,  # operator-facing, unreviewed
                excluded=(a.detected_kind in ("portrait", "noise")),
                detection_count=a.detection_count,
                mouth_open_std=a.mouth_open_std,
                centroid_std=a.centroid_std,
                temporal_density=a.temporal_density,
                detected_kind=a.detected_kind,
                created_at=now,
                updated_at=now,
            ))
        else:
            # Update stats + detected_kind but leave operator overrides
            # alone. Re-set excluded only if the operator hasn't been
            # here yet — heuristically: if `kind` is still NULL the
            # operator hasn't reviewed, so the analyser's exclude
            # decision is allowed to flip. Once kind is set, we trust
            # the operator's intent.
            existing.detection_count = a.detection_count
            existing.mouth_open_std = a.mouth_open_std
            existing.centroid_std = a.centroid_std
            existing.temporal_density = a.temporal_density
            existing.detected_kind = a.detected_kind
            if existing.kind is None:
                existing.excluded = (a.detected_kind in ("portrait", "noise"))
            existing.updated_at = now
    session.commit()

    logger.info(
        "Analysed %d clusters for source %s: %s",
        len(analyses), source_id,
        {a.detected_kind: sum(1 for x in analyses if x.detected_kind == a.detected_kind) for a in analyses},
    )
    return analyses
