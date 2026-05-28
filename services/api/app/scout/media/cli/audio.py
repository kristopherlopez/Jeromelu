"""CLI driver for Scout's audio acquisition.

Usage:
    python -m app.scout.media.cli.audio <source_id>

Idempotent on the S3 object — re-running an already-collected source is a
no-op (just confirms the audio is in S3 and the source row is up to date).
"""

from __future__ import annotations

import argparse
import logging
import sys
from uuid import UUID

from sqlalchemy.orm import joinedload

from jeromelu_shared.db import SessionLocal, Source

from ..audio import AudioError, acquire_audio


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Acquire audio for a single Source via yt-dlp.",
    )
    parser.add_argument("source_id", type=str, help="UUID of the sources row")
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
        source = (
            session.query(Source)
            .options(joinedload(Source.channel))
            .filter(Source.source_id == source_id)
            .one_or_none()
        )
        if source is None:
            print(f"No source with id {source_id}", file=sys.stderr)
            return 2

        print(f"Acquiring audio for source {source.source_id}")
        print(f"  title:   {source.title}")
        print(f"  url:     {source.canonical_url}")
        print(f"  channel: {source.channel.name if source.channel else '<none>'}")
        print()

        try:
            result = acquire_audio(session, source)
        except AudioError as exc:
            print(f"FAILED: {exc}", file=sys.stderr)
            return 1

    print("OK")
    print(f"  audio_s3_key:    {result.audio_s3_key}")
    if result.bytes_uploaded is None:
        print("  bytes_uploaded:  (skipped — already in S3)")
    else:
        print(f"  bytes_uploaded:  {result.bytes_uploaded:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
