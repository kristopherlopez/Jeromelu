"""CLI driver for draining pending Miner audio acquisition."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from jeromelu_shared.db import SessionLocal, Source
from sqlalchemy.orm import joinedload

from ..drain import (
    drain_source_ids,
    pending_audio_source_criteria,
    require_positive_limit,
    select_pending_audio_source_ids,
)

DEFAULT_LIMIT = 5


def _positive_int(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    try:
        return require_positive_limit(limit)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Drain pending approved YouTube sources through Miner audio acquisition.",
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=DEFAULT_LIMIT,
        help=f"Maximum sources to attempt (default {DEFAULT_LIMIT}).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )

    with SessionLocal() as session:
        source_ids = select_pending_audio_source_ids(session, limit=args.limit)

    # Delayed so --help/import checks do not require the optional yt-dlp stack.
    from ..audio import acquire_audio

    result = drain_source_ids(
        session_factory=SessionLocal,
        source_ids=source_ids,
        process_source=acquire_audio,
        load_options=(joinedload(Source.channel),),
        eligibility_criteria=pending_audio_source_criteria(),
    )

    print("Audio drain")
    print(f"  selected:   {result.selected}")
    print(f"  succeeded:  {result.succeeded}")
    print(f"  skipped:    {result.skipped}")
    print(f"  failed:     {result.failed}")
    for failure in result.failures:
        print(f"  failure:    {failure.source_id} :: {failure.error}", file=sys.stderr)

    return 1 if result.failed else 0


if __name__ == "__main__":
    sys.exit(main())
