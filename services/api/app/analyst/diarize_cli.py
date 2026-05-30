"""CLI driver for Phase 1 pyannote diarization (side-by-side experiment).

Usage:
    python -m app.analyst.diarize_cli <source_id>
    python -m app.analyst.diarize_cli <source_id> --force

Refuses to run if Miner hasn't collected the audio. Phase 1 makes no DB
writes — it persists the diarization JSON to S3 alongside the Deepgram
JSON. Use ``app.analyst.diarize_compare`` to inspect the result.
"""

from __future__ import annotations

import argparse
import logging
import sys
from uuid import UUID

from jeromelu_shared.db import SessionLocal, Source

from app.analyst.diarize import DiarizationError, diarize


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run pyannote on a Source's audio (Phase 1 side-by-side).",
    )
    parser.add_argument("source_id", type=str, help="UUID of the sources row")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run even if pyannote JSON already exists in S3.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
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
        source = session.query(Source).filter(Source.source_id == source_id).one_or_none()
        if source is None:
            print(f"No source with id {source_id}", file=sys.stderr)
            return 2
        if not source.audio_s3_key:
            print(
                f"Source {source.source_id} has no audio_s3_key — run `make collect-audio SOURCE_ID=...` first.",
                file=sys.stderr,
            )
            return 1

        audio_key = source.audio_s3_key
        title = source.title

    print(f"Diarizing source {source_id}")
    print(f"  title:        {title}")
    print(f"  audio_s3_key: {audio_key}")
    print()

    try:
        result = diarize(audio_key, force=args.force)
    except DiarizationError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    print("OK" + (" (skipped - JSON existed at current version)" if result.skipped else ""))
    print(f"  pyannote_s3_key:   {result.pyannote_s3_key}")
    print(f"  duration_seconds:  {result.duration_seconds}")
    print(f"  distinct_speakers: {result.distinct_speakers}")
    print(f"  turns_count:       {result.turns_count}")
    print(f"  pyannote_model:    {result.pyannote_model}")
    print(f"  embedding_model:   {result.embedding_model}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
