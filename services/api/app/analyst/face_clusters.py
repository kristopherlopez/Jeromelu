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

#: HDBSCAN's mutual-reachability metric is O(N²) regardless of the
#: nominal algorithm — KD-tree and Ball-tree both degenerate at the
#: 512-dim embeddings ArcFace emits (curse of dimensionality). Above
#: this cutoff we cluster a random subsample, then assign every
#: remaining detection to the nearest cluster centroid by cosine.
#: 5,000 is empirically ~3-5 s on a typical laptop; 39k unsampled took
#: 10+ minutes and blocked the API thread.
CLUSTER_SAMPLE_MAX = 5000

#: Cosine similarity below this between a detection and its nearest
#: cluster centroid → label it noise (cluster_id NULL) rather than
#: forcing it into a cluster it doesn't really belong to. Same role
#: as HDBSCAN's -1 noise tag, applied to the post-hoc centroid
#: assignment step.
CENTROID_NOISE_THRESHOLD = 0.35


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
    # (N, 512) float32 array, then L2-normalise. With unit vectors the
    # cosine of two embeddings is just their dot product, which makes
    # the centroid-assignment step downstream a single matmul.
    embeddings = np.asarray([r.embedding for r in rows], dtype=np.float32)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    # Guard against any zero-norm vectors (would produce NaNs and
    # silently kill the cluster pass). ArcFace doesn't emit them in
    # practice, but defensive divide costs nothing.
    norms[norms == 0] = 1.0
    embeddings = embeddings / norms

    n_total = len(rows)
    # Subsample for large sources. HDBSCAN is O(N²) in mutual-reachability
    # regardless of the nominal ``algorithm`` (KD-tree degenerates at
    # 512 dims), so we cluster a representative sample and propagate
    # cluster_ids to the rest via nearest-centroid cosine.
    if n_total > CLUSTER_SAMPLE_MAX:
        rng = np.random.default_rng(42)
        sample_idx = rng.choice(n_total, size=CLUSTER_SAMPLE_MAX, replace=False)
        sample_idx.sort()
        sample_embeddings = embeddings[sample_idx]
        # Don't scale min_cluster_size down to "preserve" small clusters
        # — that just over-fragments the dominant hosts (HDBSCAN finds
        # density variations within a real cluster). Keep the threshold
        # absolute: a cluster must have ≥ min_cluster_size detections
        # in the *sample*, which corresponds to ≥ min_cluster_size/scale
        # detections in the original. For a 5k/39k sample with min=20,
        # that's ~156 original detections, ~2.5 min of cumulative screen
        # time — a sensible floor for "worth surfacing as a row".
        cluster_min = min_cluster_size
        sample_min = min_samples
        logger.info(
            "Clustering %d detections for source %s via %d-row sample "
            "(min_cluster=%d, min_samples=%d)",
            n_total, source_id, CLUSTER_SAMPLE_MAX, cluster_min, sample_min,
        )
    else:
        sample_idx = None
        sample_embeddings = embeddings
        # Original clamp logic — prevents min_cluster_size > n_samples
        # raising sklearn on early backfills or tiny sources.
        cluster_min = min(min_cluster_size, max(2, n_total // 4))
        sample_min = min(min_samples, cluster_min)
        logger.info(
            "Clustering %d detections for source %s (min_cluster=%d, min_samples=%d)",
            n_total, source_id, cluster_min, sample_min,
        )

    clusterer = HDBSCAN(
        metric="euclidean",
        min_cluster_size=cluster_min,
        min_samples=sample_min,
        # Brute is fine at ≤ CLUSTER_SAMPLE_MAX and gives deterministic
        # output; ``auto`` is no faster in 512-dim and adds variability.
        algorithm="brute",
    )
    sample_labels = clusterer.fit_predict(sample_embeddings)

    # Re-rank cluster labels so the biggest cluster is 0, second-biggest
    # is 1, etc. Stable: same data → same labels, useful for the UI's
    # "Cluster A / B / C" naming convention.
    real_labels = [int(lbl) for lbl in sample_labels if lbl != -1]
    sizes_per_label: dict[int, int] = {}
    for lbl in real_labels:
        sizes_per_label[lbl] = sizes_per_label.get(lbl, 0) + 1
    ranked = sorted(sizes_per_label.items(), key=lambda kv: -kv[1])
    relabel = {old: new for new, (old, _) in enumerate(ranked)}

    if sample_idx is None:
        # Direct path — every detection got a label from HDBSCAN.
        per_detection_cluster: list[int | None] = []
        for lbl in sample_labels:
            per_detection_cluster.append(None if lbl == -1 else relabel[int(lbl)])
    else:
        # Compute per-cluster centroids on the sample, then assign every
        # detection (sampled + unsampled) to the nearest centroid by
        # cosine. Detections with no centroid above the noise threshold
        # are labelled NULL, matching HDBSCAN's -1 semantics for the
        # downstream UI.
        cluster_count = len(ranked)
        if cluster_count == 0:
            # HDBSCAN found nothing on the sample — extremely rare in
            # practice but possible for very noisy sources. Mark
            # everything as noise; the operator can re-run later after
            # collecting more detections.
            per_detection_cluster = [None] * n_total
        else:
            centroids = np.zeros((cluster_count, embeddings.shape[1]), dtype=np.float32)
            for new_id, (old_lbl, _) in enumerate(ranked):
                mask = sample_labels == old_lbl
                c = sample_embeddings[mask].mean(axis=0)
                cn = float(np.linalg.norm(c))
                centroids[new_id] = c / cn if cn > 0 else c
            # Cosine similarity = dot product on L2-normalised vectors.
            # (N, D) @ (D, K) → (N, K). Memory: N*K floats — ~3 MB at
            # N=39k, K=20. Trivial.
            sims = embeddings @ centroids.T
            nearest = sims.argmax(axis=1)
            best_sim = sims.max(axis=1)
            per_detection_cluster = [
                int(nearest[i]) if best_sim[i] >= CENTROID_NOISE_THRESHOLD else None
                for i in range(n_total)
            ]

    # Group detection_ids by final cluster_id so we issue one UPDATE per
    # cluster (≤ ~20 statements) instead of one per detection (39k+ on
    # long sources). Same end state, orders-of-magnitude fewer
    # round-trips to Postgres.
    by_cluster: dict[int | None, list] = {}
    n_noise = 0
    for det_id, cid in zip(detection_ids, per_detection_cluster):
        if cid is None:
            n_noise += 1
        by_cluster.setdefault(cid, []).append(det_id)

    for cluster_id, ids in by_cluster.items():
        session.execute(
            update(SourceFaceDetection)
            .where(SourceFaceDetection.detection_id.in_(ids))
            .values(cluster_id=cluster_id),
        )
    session.commit()

    # Final cluster_sizes is *full-detection* counts, not sample counts.
    # The earlier `ranked` array reflects HDBSCAN's view of the sample,
    # which is misleading when the operator reads it as "size of cluster
    # in this source" — they want the count of detections actually
    # tagged with each cluster_id.
    cluster_sizes_final = sorted(
        [len(ids) for cid, ids in by_cluster.items() if cid is not None],
        reverse=True,
    )

    logger.info(
        "Clustered %d detections for source %s → %d cluster(s), %d noise. Sizes: %s",
        len(rows), source_id, len(cluster_sizes_final), n_noise,
        cluster_sizes_final[:10] + (["..."] if len(cluster_sizes_final) > 10 else []),
    )

    return ClusterStats(
        source_id=source_id,
        n_detections=len(rows),
        n_clusters=len(cluster_sizes_final),
        n_noise=n_noise,
        cluster_sizes=cluster_sizes_final,
    )


# ---------------------------------------------------------------------------
# Cluster auto-tagging — distinguish people from wall art / portraits / noise
# ---------------------------------------------------------------------------

#: Mouth-opening standard deviation below this is considered "frozen
#: face" — a portrait or framed photo. Real talkers sit at 0.013+;
#: 0.006 is the empirical ceiling on Round 9 Review confirmed wall-art
#: clusters (B=0.0044, C=0.0014, E=0.0054, F=0.0043, G=0.0026).
PORTRAIT_MOUTH_STD = 0.006

#: When mouth_std clears the portrait bar, ignore centroid jitter
#: entirely — multi-cam shows frame wall art at slightly different
#: positions per camera angle (~10-20 px centroid_std even for a
#: bolted-to-the-wall portrait), so centroid alone can't separate them
#: from a person who sits still. The detection-count gate is what
#: discriminates: wall art is always on screen in its camera's cuts and
#: accumulates thousands of detections; a real silent listener appears
#: only intermittently and stays below this floor (Cluster L on the
#: source above was 473 detections with mouth_std 0.0052 — not wall
#: art per operator review).
PORTRAIT_MIN_DETECTIONS = 1000

#: When centroid_std is essentially zero, it's a portrait regardless
#: of mouth_std. Lip landmarks can jitter on a frozen face producing
#: modest mouth_std up to ~0.01, but if the bbox itself has never
#: moved, it's wall art.
PORTRAIT_CENTROID_STRICT = 2.0

#: Bbox area as a fraction of frame area, below which a cluster is
#: classified as a background portrait — even when mouth_std exceeds
#: the portrait ceiling. Background-shelf portraits are typically tiny
#: in frame (low-resolution lip landmark detection on a small printed
#: face is noisy, pushing mouth_std into the 0.008-0.011 range), but
#: the bbox itself stays small. Real hosts even in long shots stay
#: above 0.25 % of the frame. Verified 2026-05-12 on Round 9 Review:
#: confirmed wall art (H, I) at 0.09-0.11 %; smallest real-host
#: clusters (L, N) at 0.29-0.42 %.
PORTRAIT_SMALL_BBOX_FRACTION = 0.002

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
    bbox_area_fraction_mean: float  # diagnostic; drives the small-bbox rule
    detected_kind: str  # 'person' | 'portrait' | 'noise'


def _classify_cluster(
    detection_count: int,
    mouth_open_std: float,
    centroid_std: float,
    temporal_density: float,
    bbox_area_fraction_mean: float,
) -> str:
    """Pure function so the heuristic is unit-testable and explainable.

    Three portrait paths, in priority order:

    - **Strict-centroid**: bbox is essentially static. Catches
      bolted-to-the-wall portraits seen in a single camera angle.
    - **Quiet-mouth**: mouth never moves AND there are enough
      detections to trust that statistically. Catches multi-cam wall
      art where the bbox jitter from per-camera framing differences
      pushes centroid_std out of strict range but the lips never
      actually move (real talkers sit at mouth_std ≥ 0.013, real
      silent listeners at ≥ 0.006).
    - **Small-bbox**: cluster is consistently tiny in frame AND has
      enough detections. Background-shelf portraits are low-resolution
      in the source, so their lip landmarks jitter (mouth_std lands in
      the 0.008-0.011 range — too high for the quiet-mouth rule) while
      the bbox itself stays small.

    Density is stored as a diagnostic only — turned out to be a red
    herring across both single- and multi-cam sources.
    """
    if detection_count < NOISE_MIN_DETECTIONS:
        return "noise"
    # Strong portrait signal: bbox is essentially static.
    if centroid_std < PORTRAIT_CENTROID_STRICT:
        return "portrait"
    # Below this detection-count floor the per-cluster stats are too
    # noisy to trust either of the next two rules; a short, sparse
    # cluster could spuriously look flat-mouthed or small.
    if detection_count < PORTRAIT_MIN_DETECTIONS:
        return "person"
    # Multi-cam wall art: mouth never moves.
    if mouth_open_std < PORTRAIT_MOUTH_STD:
        return "portrait"
    # Background portrait: too small to be a host even in a long shot.
    if bbox_area_fraction_mean < PORTRAIT_SMALL_BBOX_FRACTION:
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
    # Frame area is derived from the largest bbox extents across all
    # detections for this source — over a long video, faces appear
    # close to the frame edges, so max(bbox_x2) and max(bbox_y2)
    # approximate the source resolution. Using this instead of fetching
    # the cached face-track JSON avoids an S3 round-trip per analyse run.
    max_x2 = 1.0
    max_y2 = 1.0
    for r in rows:
        bucket = by_cluster.setdefault(r.cluster_id, {
            "ts": [], "cx": [], "cy": [], "mouth": [], "area": [],
        })
        bucket["ts"].append(float(r.frame_ts))
        bucket["cx"].append((float(r.bbox_x1) + float(r.bbox_x2)) / 2.0)
        bucket["cy"].append((float(r.bbox_y1) + float(r.bbox_y2)) / 2.0)
        bucket["area"].append(
            (float(r.bbox_x2) - float(r.bbox_x1))
            * (float(r.bbox_y2) - float(r.bbox_y1))
        )
        if r.mouth_opening is not None:
            bucket["mouth"].append(float(r.mouth_opening))
        if float(r.bbox_x2) > max_x2:
            max_x2 = float(r.bbox_x2)
        if float(r.bbox_y2) > max_y2:
            max_y2 = float(r.bbox_y2)
    frame_area = max_x2 * max_y2

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
                bbox_area_fraction_mean=0.0,
                detected_kind="noise",
            ))
            continue

        ts = np.asarray(data["ts"], dtype=np.float64)
        cx = np.asarray(data["cx"], dtype=np.float64)
        cy = np.asarray(data["cy"], dtype=np.float64)
        areas = np.asarray(data["area"], dtype=np.float64)
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
        area_fraction_mean = float(areas.mean()) / frame_area

        detected = _classify_cluster(
            detection_count=len(ts),
            mouth_open_std=mouth_std,
            centroid_std=centroid_std,
            temporal_density=density,
            bbox_area_fraction_mean=area_fraction_mean,
        )
        analyses.append(ClusterAnalysis(
            cluster_id=cluster_id,
            detection_count=len(ts),
            mouth_open_std=mouth_std,
            centroid_std=centroid_std,
            temporal_density=density,
            bbox_area_fraction_mean=area_fraction_mean,
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
