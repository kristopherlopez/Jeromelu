"""CLI driver for persistent Miner video acquisition.

Usage:
    python -m app.miner.media.cli.persistent_video <source_id> [--quality 240|360|...]

Idempotent on the S3 object. Sets ``sources.video_s3_key``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from uuid import UUID

from jeromelu_shared.db import SessionLocal, Source
from sqlalchemy.orm import joinedload

from ..persistent_video import (
    DEFAULT_QUALITY,
    PersistentVideoError,
    acquire_persistent_video,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Acquire persistent low-res video for a single Source.",
    )
    parser.add_argument("source_id", type=str, help="UUID of the sources row")
    parser.add_argument(
        "--quality",
        default=DEFAULT_QUALITY,
        choices=("240", "360", "480", "720"),
        help=f"Max video height (default {DEFAULT_QUALITY}). 240/360/480/720.",
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
        source = (
            session.query(Source)
            .options(joinedload(Source.channel))
            .filter(Source.source_id == source_id)
            .one_or_none()
        )
        if source is None:
            print(f"No source with id {source_id}", file=sys.stderr)
            return 2

        print(f"Acquiring video for source {source.source_id}")
        print(f"  title:        {source.title}")
        print(f"  url:          {source.canonical_url}")
        print(f"  quality:      {args.quality}")
        print()

        try:
            result = acquire_persistent_video(session, source, quality=args.quality)
        except PersistentVideoError as exc:
            print(f"FAILED: {exc}", file=sys.stderr)
            return 1

    print("OK")
    print(f"  video_s3_key:    {result.video_s3_key}")
    if result.bytes_uploaded is not None:
        print(f"  bytes_uploaded:  {result.bytes_uploaded:,}")
    else:
        print("  bytes_uploaded:  (existing object — skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
