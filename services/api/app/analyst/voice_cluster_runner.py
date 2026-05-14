"""DB-side wrapper for HDBSCAN voice clustering.

Loads per-turn medoid embeddings from ``source_speakers`` for one
source, calls :func:`voice_cluster_hdbscan.cluster_voice_turns`, and
writes the resulting cluster labels back to ``source_speakers.cluster_label``
in a single batched UPDATE.

Idempotent at the column level: re-running with the same params produces
the same labels (HDBSCAN with ``algorithm='brute'`` is deterministic on
identical input). Re-running with different params overwrites the
cluster_label column without touching ``speaker_label`` — pyannote's
original assignment stays preserved as a fallback signal.

Companion to :mod:`face_clusters.cluster_source_detections` — same shape,
same UI loop, different embedding source.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from jeromelu_shared.db import SourceDocument, SourceSpeaker

from .voice_cluster_hdbscan import (
    TurnEmbedding,
    VoiceClusterParams,
    VoiceClusterStats,
    cluster_voice_turns,
)

logger = logging.getLogger(__name__)


@dataclass
class ReclusterResult:
    """Summary returned by :func:`recluster_source_voice`.

    ``n_turns_total`` includes turns with no usable medoid (sub-300ms
    spans, NaN windows) that were *not* fed to HDBSCAN. Their
    ``cluster_label`` stays NULL and the aggregator falls back to
    ``speaker_label`` for them — same behaviour as HDBSCAN noise.
    """
    source_id: UUID
    n_turns_total: int
    n_turns_with_embedding: int
    n_clusters: int
    n_noise: int
    cluster_sizes: list[int]


def recluster_source_voice(
    session: Session,
    source_id: UUID,
    *,
    params: VoiceClusterParams = VoiceClusterParams(),
) -> ReclusterResult:
    """Re-run HDBSCAN over per-turn medoids and update ``cluster_label``.

    Steps:
      1. Resolve ``document_id`` for the source (one row).
      2. Load all ``source_speakers`` for the document, projecting
         ``segment_id`` + ``embedding``.
      3. Filter to rows with a non-NULL medoid; pass to the pure helper.
      4. Issue one UPDATE per resulting cluster_label (≤ ~20 statements),
         setting ``cluster_label`` on the matching segment_ids. Turns
         not fed to HDBSCAN are reset to NULL so a re-cluster with
         different params doesn't leave stale labels behind.
      5. Commit once.

    Returns a :class:`ReclusterResult` summary suitable for the
    endpoint response payload.
    """
    doc = (
        session.query(SourceDocument)
        .filter(SourceDocument.source_id == source_id)
        .first()
    )
    if not doc:
        return ReclusterResult(
            source_id=source_id,
            n_turns_total=0,
            n_turns_with_embedding=0,
            n_clusters=0,
            n_noise=0,
            cluster_sizes=[],
        )

    rows = (
        session.query(SourceSpeaker.segment_id, SourceSpeaker.embedding)
        .filter(SourceSpeaker.document_id == doc.document_id)
        .order_by(SourceSpeaker.start_ts)
        .all()
    )
    n_total = len(rows)
    if n_total == 0:
        return ReclusterResult(
            source_id=source_id,
            n_turns_total=0,
            n_turns_with_embedding=0,
            n_clusters=0,
            n_noise=0,
            cluster_sizes=[],
        )

    clusterable = [
        TurnEmbedding(turn_id=r.segment_id, embedding=list(r.embedding))
        for r in rows
        if r.embedding is not None
    ]
    n_clusterable = len(clusterable)
    logger.info(
        "Re-clustering source %s — %d turns total, %d with embedding "
        "(min_cluster=%d, min_samples=%d, noise=%.2f)",
        source_id, n_total, n_clusterable,
        params.min_cluster_size, params.min_samples, params.noise_threshold,
    )

    assignments, stats = cluster_voice_turns(clusterable, params=params)

    # Reset every turn in the document first — re-runs with different
    # params must not leave stale H-labels around. The subsequent
    # per-cluster UPDATEs then re-apply the new labels.
    session.execute(
        update(SourceSpeaker)
        .where(SourceSpeaker.document_id == doc.document_id)
        .values(cluster_label=None),
    )

    by_label: dict[str, list[UUID]] = {}
    for turn_id, label in assignments:
        if label is None:
            continue
        by_label.setdefault(label, []).append(turn_id)
    for label, ids in by_label.items():
        session.execute(
            update(SourceSpeaker)
            .where(SourceSpeaker.segment_id.in_(ids))
            .values(cluster_label=label),
        )
    session.commit()

    logger.info(
        "Re-cluster done — %d clusters, %d noise turns",
        stats.n_clusters, stats.n_noise,
    )
    return ReclusterResult(
        source_id=source_id,
        n_turns_total=n_total,
        n_turns_with_embedding=n_clusterable,
        n_clusters=stats.n_clusters,
        n_noise=stats.n_noise,
        cluster_sizes=stats.cluster_sizes,
    )
