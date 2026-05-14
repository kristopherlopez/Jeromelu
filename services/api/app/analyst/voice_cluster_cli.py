"""CLI driver for the HDBSCAN voice re-clustering pass.

Usage:
    python -m app.analyst.voice_cluster_cli <source_id>
    python -m app.analyst.voice_cluster_cli <source_id> --min-cluster-size 8
    python -m app.analyst.voice_cluster_cli <source_id> --noise-threshold 0.30

Pure SQL + in-process HDBSCAN — no SageMaker, no GPU. Reads per-turn
medoid embeddings from ``source_speakers.embedding`` (already populated
by diarisation), runs the HDBSCAN clusterer, and writes labels back to
``source_speakers.cluster_label``. The Voices tab and AssignVoice flow
pick up the new labels via ``coalesce(cluster_label, speaker_label)``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from uuid import UUID

from jeromelu_shared.db import SessionLocal, Source

from app.analyst.voice_cluster_hdbscan import (
    DEFAULT_MIN_CLUSTER_SIZE,
    DEFAULT_MIN_SAMPLES,
    DEFAULT_NOISE_THRESHOLD,
    VoiceClusterParams,
)
from app.analyst.voice_cluster_runner import recluster_source_voice


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Re-cluster per-turn wespeaker medoids with HDBSCAN and write "
            "labels to source_speakers.cluster_label."
        ),
    )
    parser.add_argument("source_id", type=str, help="UUID of the sources row")
    parser.add_argument(
        "--min-cluster-size", type=int, default=DEFAULT_MIN_CLUSTER_SIZE,
        help=f"HDBSCAN min_cluster_size (default {DEFAULT_MIN_CLUSTER_SIZE})",
    )
    parser.add_argument(
        "--min-samples", type=int, default=DEFAULT_MIN_SAMPLES,
        help=f"HDBSCAN min_samples (default {DEFAULT_MIN_SAMPLES})",
    )
    parser.add_argument(
        "--noise-threshold", type=float, default=DEFAULT_NOISE_THRESHOLD,
        help=(
            "Cosine similarity floor for inclusion; below this the turn is "
            f"labelled noise (default {DEFAULT_NOISE_THRESHOLD})"
        ),
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )

    try:
        source_id = UUID(args.source_id)
    except ValueError:
        print(f"Invalid UUID: {args.source_id}", file=sys.stderr)
        return 2

    with SessionLocal() as session:
        source = (
            session.query(Source)
            .filter(Source.source_id == source_id)
            .one_or_none()
        )
        if source is None:
            print(f"No source with id {source_id}", file=sys.stderr)
            return 2

        params = VoiceClusterParams(
            min_cluster_size=args.min_cluster_size,
            min_samples=args.min_samples,
            noise_threshold=args.noise_threshold,
        )
        result = recluster_source_voice(session, source_id, params=params)

    print(f"Re-clustered source {source_id}")
    print(f"  turns_total:           {result.n_turns_total}")
    print(f"  turns_with_embedding:  {result.n_turns_with_embedding}")
    print(f"  n_clusters:            {result.n_clusters}")
    print(f"  n_noise:               {result.n_noise}")
    print(f"  cluster_sizes:         {result.cluster_sizes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
