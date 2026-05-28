"""HDBSCAN clustering over per-turn wespeaker medoids for the Voices tab.

Pyannote's per-source ``SPEAKER_NN`` labels are the raw output of its
segmentation + clustering pass. We treat them as one signal but not the
source of truth — empirically pyannote conflates two co-commentators
with similar pitch / pacing into a single cluster. Re-clustering the
per-turn medoid embeddings with HDBSCAN (the same algorithm used for
faces in :mod:`face_clusters`) gives tighter, density-based clusters
that the human-in-the-loop AssignVoice flow can confirm.

Output cluster labels use an ``H``-prefix (``H00``, ``H01``, …) so they
never collide with pyannote's ``SPEAKER_NN`` namespace when both
live side-by-side in the same column elsewhere. The DB layer writes
these to ``source_speakers.cluster_label`` and the Voices tab groups
by ``coalesce(cluster_label, speaker_label)``.

Pure helper — no DB session, no I/O. Takes a list of
:class:`TurnEmbedding` projections and returns
``(turn_id, cluster_label_or_None)`` pairs plus a stats summary. The DB
wrapper lives in :mod:`voice_cluster_runner`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

import numpy as np
from sklearn.cluster import HDBSCAN

#: Minimum number of turns to form a cluster. Voice has far fewer points
#: than faces (~hundreds of turns vs thousands of detections per source),
#: so the threshold is much lower — a guest commentator with only a few
#: speaking turns should still surface as their own cluster.
DEFAULT_MIN_CLUSTER_SIZE = 5

#: How tight a cluster needs to be before HDBSCAN declares it. Voice
#: embeddings are softer than ArcFace (more intra-speaker variation from
#: phonetic content / emotion / mic), so ``min_samples=2`` lets the
#: density-reachability metric extend further before tagging noise.
DEFAULT_MIN_SAMPLES = 2

#: Cosine similarity floor used by HDBSCAN's ``cluster_selection_epsilon``
#: equivalent. On L2-normalised vectors, Euclidean distance ``d`` and
#: cosine similarity ``s`` are tied by ``d² = 2(1 - s)``, so a cosine
#: floor of 0.25 corresponds to a Euclidean ceiling of ~1.225. We pass
#: this in as ``cluster_selection_epsilon`` so HDBSCAN treats anything
#: closer than that ceiling as worth merging, even if mutual-reachability
#: would otherwise split it. Tunable from the API/UI per source.
DEFAULT_NOISE_THRESHOLD = 0.25


@dataclass(frozen=True)
class TurnEmbedding:
    """Minimal turn projection consumed by :func:`cluster_voice_turns`.

    Kept as a tiny dataclass so the clustering helper is trivially
    unit-testable without a DB session — the DB wrapper builds these
    from ``source_speakers`` rows where ``embedding IS NOT NULL``.
    """

    turn_id: UUID
    embedding: Sequence[float]


@dataclass(frozen=True)
class VoiceClusterParams:
    """Tunable knobs surfaced to the API + UI."""

    min_cluster_size: int = DEFAULT_MIN_CLUSTER_SIZE
    min_samples: int = DEFAULT_MIN_SAMPLES
    noise_threshold: float = DEFAULT_NOISE_THRESHOLD


@dataclass
class VoiceClusterStats:
    """Return shape from :func:`cluster_voice_turns`."""

    n_turns: int  # rows fed to the clusterer (excludes None-embedding)
    n_clusters: int  # distinct real cluster labels emitted
    n_noise: int  # turns labelled NULL (HDBSCAN -1)
    cluster_sizes: list[int] = field(default_factory=list)


def _label_from_index(index: int) -> str:
    """``0 → 'H00'``, ``1 → 'H01'``, …, ``99 → 'H99'``, ``100 → 'H100'``."""
    return f"H{index:02d}"


def cluster_voice_turns(
    rows: Sequence[TurnEmbedding],
    *,
    params: VoiceClusterParams = VoiceClusterParams(),  # noqa: B008  # frozen dataclass — immutable, safely shareable across calls
) -> tuple[list[tuple[UUID, str | None]], VoiceClusterStats]:
    """Cluster per-turn medoid embeddings and return ``(turn_id, label)``.

    ``rows`` should contain only turns with a usable embedding. Turns
    with ``None`` medoids are filtered by the caller — they get
    ``cluster_label = NULL`` automatically and don't enter HDBSCAN.

    Implementation:
      1. L2-normalise all embeddings so Euclidean ↔ cosine carry the
         same ordering. Zero-norm vectors (shouldn't happen with
         wespeaker but defensively) are left as zero — HDBSCAN treats
         them as far from everything and they land in noise.
      2. Run HDBSCAN with ``cluster_selection_epsilon`` derived from the
         cosine noise threshold so the operator can dial it from the UI.
      3. Relabel cluster IDs so the biggest cluster is ``H00``, second
         biggest ``H01``, etc. Stable: same data → same labels.

    Returns a list aligned to ``rows`` (one entry per input) and a
    :class:`VoiceClusterStats` summary suitable for the API response.
    """
    n_in = len(rows)
    if n_in == 0:
        return [], VoiceClusterStats(n_turns=0, n_clusters=0, n_noise=0, cluster_sizes=[])

    embeddings = np.asarray([r.embedding for r in rows], dtype=np.float32)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    embeddings = embeddings / norms

    # Clamp params for tiny inputs — sklearn raises if min_cluster_size > n.
    cluster_min = max(2, min(params.min_cluster_size, n_in))
    sample_min = max(1, min(params.min_samples, cluster_min))

    # NOTE: we deliberately don't pass ``cluster_selection_epsilon`` to
    # HDBSCAN. The intuitive use (turn the cosine noise threshold into a
    # Euclidean epsilon for permissive merging) trips a known sklearn
    # traversal bug — ``epsilon_search`` raises
    # "only 0-dimensional arrays can be converted to Python scalars" on
    # specific tree shapes. We apply ``noise_threshold`` as a post-cluster
    # cosine filter against each cluster's centroid instead — matches the
    # semantics of ``face_clusters.CENTROID_NOISE_THRESHOLD`` and dodges
    # the sklearn bug.
    clusterer = HDBSCAN(
        metric="euclidean",
        min_cluster_size=cluster_min,
        min_samples=sample_min,
        algorithm="brute",
    )
    raw_labels = clusterer.fit_predict(embeddings)

    # Relabel by descending cluster size so H00 is always the biggest.
    sizes_per_label: dict[int, int] = {}
    for lbl in raw_labels:
        i = int(lbl)
        if i == -1:
            continue
        sizes_per_label[i] = sizes_per_label.get(i, 0) + 1
    ranked = sorted(sizes_per_label.items(), key=lambda kv: -kv[1])
    relabel: dict[int, int] = {old: new for new, (old, _) in enumerate(ranked)}

    # Per-cluster centroids on L2-normalised vectors. Used to post-filter:
    # turns whose own cluster's centroid is further than ``noise_threshold``
    # in cosine get ejected to noise (NULL label).
    n_real = len(ranked)
    if n_real > 0:
        centroids = np.zeros((n_real, embeddings.shape[1]), dtype=np.float32)
        for new_id, (old_lbl, _) in enumerate(ranked):
            mask = raw_labels == old_lbl
            c = embeddings[mask].mean(axis=0)
            cn = float(np.linalg.norm(c))
            centroids[new_id] = c / cn if cn > 0 else c
        # Cosine = dot product on L2-normalised vectors. Shape (N,).
        own_centroid_for = np.array([relabel[int(lbl)] if int(lbl) != -1 else -1 for lbl in raw_labels])
        cos_to_own = np.full(n_in, -1.0, dtype=np.float32)
        for i in range(n_in):
            cid = own_centroid_for[i]
            if cid >= 0:
                cos_to_own[i] = float(embeddings[i] @ centroids[cid])
    else:
        own_centroid_for = np.full(n_in, -1, dtype=np.int64)
        cos_to_own = np.full(n_in, -1.0, dtype=np.float32)

    per_turn: list[tuple[UUID, str | None]] = []
    final_sizes: dict[int, int] = {}
    n_noise = 0
    for i in range(n_in):
        cid = int(own_centroid_for[i])
        if cid < 0 or cos_to_own[i] < params.noise_threshold:
            per_turn.append((rows[i].turn_id, None))
            n_noise += 1
        else:
            per_turn.append((rows[i].turn_id, _label_from_index(cid)))
            final_sizes[cid] = final_sizes.get(cid, 0) + 1

    cluster_sizes = [final_sizes[k] for k in sorted(final_sizes.keys())]
    stats = VoiceClusterStats(
        n_turns=n_in,
        n_clusters=len(cluster_sizes),
        n_noise=n_noise,
        cluster_sizes=cluster_sizes,
    )
    return per_turn, stats
