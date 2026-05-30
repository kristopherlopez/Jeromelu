r"""Generic Miner backfill driver.

Iterates over (season, round) pairs and hits the appropriate admin endpoint
for the named pipeline. Rate-limited at 1 req/sec by default to be polite
to upstream.

Two Phase 5 additions vs the original sketch:

  --archive-only
      Append `archive_only=true` to every POST. Routes capture S3 but skip
      D8 strict-parse (and, for supercoach-stats, the inline DB upsert).
      Use for historical seasons whose shape diverges from modern.

  --resume
      Before each POST, HEAD the expected S3 key; skip if present. Lets a
      multi-hour backfill resume from a mid-run abort without redoing the
      thousands of (season, round) pairs already in S3. For match-centre
      (multi-key per round), resume operates at round-level via a LIST
      against the round prefix. SC siblings (roster/teams/settings)
      don't have a deterministic key derivable from CLI args; --resume is
      a no-op for them (logged once at startup).

  --force
      Override --resume; re-POST every (season, round) even if S3 already
      has the key. Useful for re-fetching after upstream revisions.

Usage (Phase 5 historical backfill on prod via loopback):
  docker exec -it jeromelu-api bash -c "
    cd /runtmp && python -m scripts.data.miner_backfill \\
      --source nrlcom-draw \\
      --season-from 1908 --season-to 2026 \\
      --competition 111 \\
      --api https://api.jeromelu.ai \\
      --admin-key \$ADMIN_KEY \\
      --archive-only --resume \\
      --rate-limit 1.0
  "

Usage (daily cron — same script, no new flags):
  python scripts/data/miner_backfill.py \\
      --source nrlcom-draw \\
      --season-from 2026 --season-to 2026 \\
      --competition 111 \\
      --api http://localhost:8000 --admin-key local-dev-admin-key

Per-pipeline iteration logic:
  - nrlcom-draw, nrlcom-ladder: per (season, round)
  - nrlcom-match-centre: per (season, round) — walks fixtures internally
  - nrlcom-stats, nrlcom-casualty-ward: per season (no round dimension)
  - nrlcom-players-roster: per (competition, team) — operator supplies team list
  - supercoach-stats: per (season, round) where round 0 = Totals
  - supercoach-roster, supercoach-teams, supercoach-settings: per season
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Callable
from typing import Any

import httpx

# Per-pipeline iteration: True if the pipeline takes a round param.
TAKES_ROUND: dict[str, bool] = {
    "nrlcom-draw": True,
    "nrlcom-ladder": True,
    "nrlcom-match-centre": True,  # round is required
    "nrlcom-casualty-ward": False,
    "nrlcom-stats": False,
    "nrlcom-players-roster": False,  # iterate teams, not rounds
    "supercoach-roster": False,
    "supercoach-teams": False,
    "supercoach-settings": False,
    "supercoach-stats": True,  # round 0 = Totals, 1-30 = rounds
}

# Per-pipeline: does it take a competition param?
TAKES_COMPETITION: dict[str, bool] = {
    "nrlcom-draw": True,
    "nrlcom-ladder": True,
    "nrlcom-match-centre": True,
    "nrlcom-casualty-ward": True,
    "nrlcom-stats": True,
    "nrlcom-players-roster": True,
    "supercoach-roster": False,
    "supercoach-teams": False,
    "supercoach-settings": False,
    "supercoach-stats": False,
}


# S3 key derivation for --resume HEAD checks. Maps source → callable
# that returns the expected S3 key for (competition, season, round).
# Sources without an entry use LIST-prefix or no-op resume (see below).
S3_KEY_FN: dict[str, Callable[[int, int, int | None], str]] = {
    "nrlcom-draw": lambda comp, season, rd: (
        f"miner/nrlcom/draw/{comp}/{season}/round-{int(rd or 0):02d}.json"
    ),
    "nrlcom-ladder": lambda comp, season, rd: (
        f"miner/nrlcom/ladder/{comp}/{season}/round-{int(rd or 0):02d}.json"
    ),
    "nrlcom-stats": lambda comp, season, rd: (
        f"miner/nrlcom/stats/{comp}/{season}.json"
    ),
    "supercoach-stats": lambda comp, season, rd: (
        f"miner/nrlsupercoachstats/stats/{season}/round-{int(rd or 0):02d}.json"
    ),
}

# Sources that need a LIST-prefix resume check (multi-key per (season, round)).
S3_LIST_PREFIX_FN: dict[str, Callable[[int, int, int | None], str]] = {
    "nrlcom-match-centre": lambda comp, season, rd: (
        f"miner/nrlcom/match-centre/{comp}/{season}/round-{int(rd or 0):02d}/"
    ),
}


def _s3_key_exists(client, *, bucket: str, key: str) -> bool:
    """HEAD the key; True if present, False on 404 / other ClientError."""
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def _s3_prefix_has_keys(client, *, bucket: str, prefix: str) -> bool:
    """LIST under prefix with MaxKeys=1; True if any object exists there."""
    try:
        resp = client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
        return bool(resp.get("Contents"))
    except Exception:
        return False


def _get_s3_client():
    """Lazy boto3 import — only needed when --resume is set."""
    import boto3
    return boto3.client("s3")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Pipeline name (e.g. nrlcom-draw)")
    parser.add_argument("--season-from", type=int, required=True)
    parser.add_argument("--season-to", type=int, default=None,
                        help="Defaults to --season-from")
    parser.add_argument("--round-from", type=int, default=0)
    parser.add_argument("--round-to", type=int, default=30)
    parser.add_argument("--competition", type=int, default=111)
    parser.add_argument("--api", required=True, help="API base URL")
    parser.add_argument("--admin-key", required=True)
    parser.add_argument("--rate-limit", type=float, default=1.0,
                        help="Seconds between requests")
    parser.add_argument("--archive-only", action="store_true",
                        help="Append archive_only=true to every POST (Phase 5 historical backfill).")
    parser.add_argument("--resume", action="store_true",
                        help="HEAD/LIST the expected S3 key before each POST; skip if present.")
    parser.add_argument("--force", action="store_true",
                        help="Override --resume; re-POST every (season, round) regardless of S3.")
    parser.add_argument(
        "--bucket", default=os.environ.get("S3_CLEAN_BUCKET", "jeromelu-clean-documents"),
        help="S3 bucket for --resume checks. Defaults to $S3_CLEAN_BUCKET or jeromelu-clean-documents.",
    )
    args = parser.parse_args(argv)

    if args.source not in TAKES_ROUND:
        print(f"Unknown source: {args.source}. Known: {sorted(TAKES_ROUND.keys())}", file=sys.stderr)
        return 2

    # Resolve resume strategy for the chosen source.
    s3_client = None
    resume_strategy: str  # 'head' | 'list' | 'noop'
    if args.resume and not args.force:
        s3_client = _get_s3_client()
        if args.source in S3_KEY_FN:
            resume_strategy = "head"
        elif args.source in S3_LIST_PREFIX_FN:
            resume_strategy = "list"
        else:
            resume_strategy = "noop"
            print(
                f"NOTE: --resume is a no-op for source={args.source} "
                f"(no deterministic key derivation; rerunning will overwrite).",
                file=sys.stderr,
            )
    else:
        resume_strategy = "noop"

    season_to = args.season_to or args.season_from
    seasons = list(range(args.season_from, season_to + 1))
    takes_round = TAKES_ROUND[args.source]
    takes_competition = TAKES_COMPETITION[args.source]
    rounds = list(range(args.round_from, args.round_to + 1)) if takes_round else [None]

    successes = 0
    skipped = 0
    failures: list[tuple[int, int | None, str]] = []
    headers = {"X-Admin-Key": args.admin_key}

    with httpx.Client(timeout=300.0) as client:
        for season in seasons:
            for rd in rounds:
                params: dict[str, Any] = {"season": season}
                if takes_competition:
                    params["competition"] = args.competition
                if rd is not None:
                    params["round"] = rd
                if args.archive_only:
                    params["archive_only"] = "true"
                url = f"{args.api}/api/admin/miner/{args.source}"
                label = f"season={season}" + (f" round={rd}" if rd is not None else "")

                # Resume gate: skip if S3 already has the expected key/prefix.
                if resume_strategy == "head":
                    expected_key = S3_KEY_FN[args.source](args.competition, season, rd)
                    if _s3_key_exists(s3_client, bucket=args.bucket, key=expected_key):
                        print(f"SKIP {label} (S3 exists at {expected_key})", file=sys.stderr)
                        skipped += 1
                        continue
                elif resume_strategy == "list":
                    prefix = S3_LIST_PREFIX_FN[args.source](args.competition, season, rd)
                    if _s3_prefix_has_keys(s3_client, bucket=args.bucket, prefix=prefix):
                        print(f"SKIP {label} (S3 has objects under {prefix})", file=sys.stderr)
                        skipped += 1
                        continue

                print(f"[{label}] POST {url} {params}", file=sys.stderr)
                try:
                    r = client.post(url, params=params, headers=headers)
                    if r.status_code == 200:
                        print(f"  OK ({r.json().get('run_id', '?')})", file=sys.stderr)
                        successes += 1
                    else:
                        msg = f"HTTP {r.status_code}: {r.text[:200]}"
                        print(f"  FAIL — {msg}", file=sys.stderr)
                        failures.append((season, rd, msg))
                except Exception as e:
                    msg = f"{type(e).__name__}: {e}"
                    print(f"  ERR — {msg}", file=sys.stderr)
                    failures.append((season, rd, msg))
                time.sleep(args.rate_limit)

    print("\n=== Backfill summary ===", file=sys.stderr)
    print(f"  source: {args.source}", file=sys.stderr)
    print(f"  seasons: {seasons[0]}..{seasons[-1]} ({len(seasons)} years)", file=sys.stderr)
    if takes_round:
        print(f"  rounds: {args.round_from}..{args.round_to}", file=sys.stderr)
    print(f"  archive_only: {args.archive_only}", file=sys.stderr)
    print(f"  resume_strategy: {resume_strategy}", file=sys.stderr)
    print(f"  successes: {successes}", file=sys.stderr)
    print(f"  skipped:   {skipped}", file=sys.stderr)
    print(f"  failures:  {len(failures)}", file=sys.stderr)
    for season, rd, msg in failures[:20]:
        print(f"    {season} round={rd}: {msg}", file=sys.stderr)
    if len(failures) > 20:
        print(f"    ... and {len(failures) - 20} more", file=sys.stderr)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
