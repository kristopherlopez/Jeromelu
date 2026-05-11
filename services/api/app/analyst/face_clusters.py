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
from uuid import UUID

import numpy as np
from sklearn.cluster import HDBSCAN
from sqlalchemy import update
from sqlalchemy.orm import Session

from jeromelu_shared.db import SourceFaceDetection

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
