"""Unit tests for the pure HDBSCAN voice-clustering helper.

No DB session. Builds synthetic embedding sets that simulate per-source
turns from one, two, or three speakers and asserts the helper:
  * returns labels aligned to input order,
  * uses ``H``-prefix labels relabelled by descending cluster size,
  * tags isolated outliers as noise (NULL),
  * is deterministic on identical input.
"""

from __future__ import annotations

import uuid

import numpy as np
import pytest

from app.analyst.voice_cluster_hdbscan import (
    TurnEmbedding,
    VoiceClusterParams,
    cluster_voice_turns,
)


def _vec(seed: int, dim: int = 16, base: np.ndarray | None = None,
         jitter: float = 0.05) -> list[float]:
    """Produce a unit-ish vector either fresh from ``seed`` or as a
    small perturbation around ``base`` (same speaker, different turn)."""
    rng = np.random.default_rng(seed)
    if base is None:
        v = rng.normal(size=dim).astype(np.float32)
    else:
        v = base + jitter * rng.normal(size=dim).astype(np.float32)
    v = v / np.linalg.norm(v)
    return v.tolist()


def _row(emb: list[float]) -> TurnEmbedding:
    return TurnEmbedding(turn_id=uuid.uuid4(), embedding=emb)


def test_empty_input_returns_empty_result():
    out, stats = cluster_voice_turns([])
    assert out == []
    assert stats.n_turns == 0
    assert stats.n_clusters == 0
    assert stats.n_noise == 0
    assert stats.cluster_sizes == []


def test_two_well_separated_clusters_get_h00_h01():
    rng = np.random.default_rng(0)
    base_a = rng.normal(size=16).astype(np.float32)
    base_a = base_a / np.linalg.norm(base_a)
    base_b = rng.normal(size=16).astype(np.float32)
    base_b = base_b / np.linalg.norm(base_b)

    # 12 turns for speaker A, 6 for speaker B — A should win H00.
    rows = []
    for i in range(12):
        rows.append(_row(_vec(seed=100 + i, base=base_a, jitter=0.02)))
    for i in range(6):
        rows.append(_row(_vec(seed=500 + i, base=base_b, jitter=0.02)))

    out, stats = cluster_voice_turns(
        rows,
        params=VoiceClusterParams(min_cluster_size=3, min_samples=2, noise_threshold=0.0),
    )

    assert len(out) == len(rows)
    labels = [lbl for _, lbl in out]

    # The first 12 should all be the same label, and the last 6 should
    # all be a different same label.
    assert len(set(labels[:12])) == 1
    assert len(set(labels[12:])) == 1
    assert labels[0] != labels[12]

    # And the larger cluster gets H00 (smaller index).
    assert labels[0] == "H00"
    assert labels[12] == "H01"

    assert stats.n_clusters == 2
    assert stats.cluster_sizes == [12, 6]
    assert stats.n_noise == 0


def test_isolated_outlier_becomes_noise():
    rng = np.random.default_rng(1)
    base_a = rng.normal(size=16).astype(np.float32)
    base_a = base_a / np.linalg.norm(base_a)

    # Looser jitter (0.08) — HDBSCAN with very tight points finds density
    # variations and splits them. Real wespeaker turn medoids vary at
    # roughly this scale within one speaker.
    rows = [_row(_vec(seed=200 + i, base=base_a, jitter=0.08)) for i in range(12)]
    # One faraway vector — should fall to noise via either HDBSCAN's -1
    # or the centroid-cosine post-filter at noise_threshold=0.5.
    rows.append(_row(_vec(seed=999)))

    out, stats = cluster_voice_turns(
        rows,
        params=VoiceClusterParams(min_cluster_size=3, min_samples=2, noise_threshold=0.5),
    )
    # The outlier (last row) must be noise.
    assert out[-1][1] is None
    # The in-cluster rows should mostly land in clusters (not all noise).
    in_cluster_labels = [lbl for _, lbl in out[:12] if lbl is not None]
    assert len(in_cluster_labels) >= 10
    # And at least one real cluster found.
    assert stats.n_clusters >= 1


def test_outlier_caught_by_noise_threshold_filter():
    """The centroid post-filter ejects a point that HDBSCAN merged.

    HDBSCAN may accept a loose point as part of a cluster if it's
    within the density tree. The cosine post-filter is the second line
    of defence: anything below ``noise_threshold`` cosine to its own
    cluster's centroid gets ejected to NULL.
    """
    rng = np.random.default_rng(11)
    base_a = rng.normal(size=16).astype(np.float32)
    base_a = base_a / np.linalg.norm(base_a)

    rows = [_row(_vec(seed=2200 + i, base=base_a, jitter=0.05)) for i in range(12)]
    # Loose point along the same axis but with large perturbation —
    # HDBSCAN may keep it in the cluster but it'll be far from centroid.
    rows.append(_row(_vec(seed=2999, base=base_a, jitter=0.40)))

    out, stats = cluster_voice_turns(
        rows,
        params=VoiceClusterParams(
            min_cluster_size=3, min_samples=2, noise_threshold=0.85,
        ),
    )
    # The loose tail point should be ejected by the centroid filter.
    assert out[-1][1] is None
    assert stats.n_noise >= 1


def test_zero_noise_threshold_disables_centroid_filter():
    """With ``noise_threshold=0.0`` the centroid post-filter never rejects
    (every cosine ≥ 0). So the only source of noise labels is HDBSCAN's
    own ``-1`` — we can't predict it on synthetic data, but raising the
    threshold should weakly increase the noise count.
    """
    rng = np.random.default_rng(2)
    base_a = rng.normal(size=16).astype(np.float32)
    base_a = base_a / np.linalg.norm(base_a)

    rows = [_row(_vec(seed=10 + i, base=base_a, jitter=0.06)) for i in range(15)]

    _out_low, stats_low = cluster_voice_turns(
        rows,
        params=VoiceClusterParams(min_cluster_size=3, min_samples=2, noise_threshold=0.0),
    )
    _out_high, stats_high = cluster_voice_turns(
        rows,
        params=VoiceClusterParams(min_cluster_size=3, min_samples=2, noise_threshold=0.99),
    )
    # Raising the threshold can only equal or increase n_noise.
    assert stats_high.n_noise >= stats_low.n_noise


def test_deterministic_on_identical_input():
    rng = np.random.default_rng(3)
    base = rng.normal(size=16).astype(np.float32)
    base = base / np.linalg.norm(base)

    rows = [_row(_vec(seed=400 + i, base=base, jitter=0.02)) for i in range(15)]

    a_out, a_stats = cluster_voice_turns(rows)
    b_out, b_stats = cluster_voice_turns(rows)
    assert [lbl for _, lbl in a_out] == [lbl for _, lbl in b_out]
    assert a_stats.cluster_sizes == b_stats.cluster_sizes
    assert a_stats.n_clusters == b_stats.n_clusters


def test_params_clamped_for_tiny_inputs():
    # 4 rows, min_cluster_size=20 — should clamp to 4 and still run
    # without sklearn raising. May or may not find a cluster depending
    # on density; just assert it doesn't crash and returns a row per
    # input.
    rng = np.random.default_rng(4)
    base = rng.normal(size=16).astype(np.float32)
    base = base / np.linalg.norm(base)
    rows = [_row(_vec(seed=700 + i, base=base, jitter=0.01)) for i in range(4)]

    out, _stats = cluster_voice_turns(
        rows,
        params=VoiceClusterParams(min_cluster_size=20, min_samples=10),
    )
    assert len(out) == 4


def test_label_format_two_digits():
    """H-prefix labels pad to two digits up to H99; safe past that."""
    from app.analyst.voice_cluster_hdbscan import _label_from_index
    assert _label_from_index(0) == "H00"
    assert _label_from_index(1) == "H01"
    assert _label_from_index(9) == "H09"
    assert _label_from_index(10) == "H10"
    assert _label_from_index(99) == "H99"
    assert _label_from_index(100) == "H100"
