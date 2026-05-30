"""CLI for deterministic YouTube-native source discovery.

Examples:
  python -m app.scout.source_discovery.deterministic_youtube_cli --dry-run
  python -m app.scout.source_discovery.deterministic_youtube_cli --channel-query "NRL injury podcast"
  python -m app.scout.source_discovery.deterministic_youtube_cli --no-video-search --max-results 25
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from jeromelu_shared.agent_audit import make_run_id
from jeromelu_shared.db import SessionLocal

from .deterministic_youtube import (
    DEFAULT_MIN_SCORE,
    run_deterministic_youtube_discovery,
)


def _query_list(values: list[str] | None, disabled: bool) -> list[str] | None:
    if disabled:
        return []
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic YouTube source discovery")
    parser.add_argument(
        "--channel-query",
        action="append",
        dest="channel_queries",
        help="Override default channel-search queries. Repeat for multiple queries.",
    )
    parser.add_argument(
        "--video-query",
        action="append",
        dest="video_queries",
        help="Override default video-search queries. Repeat for multiple queries.",
    )
    parser.add_argument(
        "--harvest-query",
        action="append",
        dest="harvest_queries",
        help="Override default video-harvest channel queries. Repeat for multiple queries.",
    )
    parser.add_argument(
        "--related-channel-id",
        action="append",
        dest="related_channel_ids",
        help="Also inspect featured channels for this known YouTube channel ID. Repeatable.",
    )
    parser.add_argument("--no-channel-search", action="store_true")
    parser.add_argument("--no-video-search", action="store_true")
    parser.add_argument("--no-harvest-search", action="store_true")
    parser.add_argument("--max-results", type=int, default=10, help="Per channel-search query cap")
    parser.add_argument("--max-videos", type=int, default=25, help="Per video-search/harvest query cap")
    parser.add_argument("--published-after", help="RFC 3339 timestamp for video searches, e.g. 2026-04-01T00:00:00Z")
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--run-id", help="Optional run_id to stamp onto scout_candidates")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Call YouTube and score candidates but do not write scout_candidates",
    )
    parser.add_argument("--json", action="store_true", help="Print the full JSON result")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    run_id = args.run_id or make_run_id("scout")
    session = SessionLocal()
    try:
        result = run_deterministic_youtube_discovery(
            session,
            run_id=run_id,
            channel_queries=_query_list(args.channel_queries, args.no_channel_search),
            video_queries=_query_list(args.video_queries, args.no_video_search),
            harvest_queries=_query_list(args.harvest_queries, args.no_harvest_search),
            related_channel_ids=args.related_channel_ids,
            max_results_per_query=args.max_results,
            max_videos_per_query=args.max_videos,
            published_after=args.published_after,
            min_score=args.min_score,
            dry_run=args.dry_run,
        )
    finally:
        session.close()

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        verb = "would insert" if result.dry_run else "inserted"
        insert_count = result.candidates_selected if result.dry_run else result.candidates_inserted
        print(
            "Deterministic YouTube discovery "
            f"{result.run_id}: selected={result.candidates_selected}, "
            f"{verb}={insert_count}, duplicates={result.duplicates_skipped}, "
            f"below_threshold={result.candidates_below_threshold}, missing_metadata={result.candidates_missing_api_metadata}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
