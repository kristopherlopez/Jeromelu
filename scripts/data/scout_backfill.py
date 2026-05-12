"""Generic Scout backfill driver.

Iterates over (season, round) pairs and hits the appropriate admin endpoint
for the named pipeline. Rate-limited at 1 req/sec to be polite to upstream.

Usage:
  python scripts/data/scout_backfill.py \
      --source nrlcom-draw \
      --season-from 1908 --season-to 2026 \
      --competition 111 \
      --api http://localhost:8000 \
      --admin-key local-dev-admin-key

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
import sys
import time

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
    args = parser.parse_args(argv)

    if args.source not in TAKES_ROUND:
        print(f"Unknown source: {args.source}. Known: {sorted(TAKES_ROUND.keys())}", file=sys.stderr)
        return 2

    season_to = args.season_to or args.season_from
    seasons = list(range(args.season_from, season_to + 1))
    takes_round = TAKES_ROUND[args.source]
    takes_competition = TAKES_COMPETITION[args.source]
    rounds = list(range(args.round_from, args.round_to + 1)) if takes_round else [None]

    successes = 0
    failures: list[tuple[int, int | None, str]] = []
    headers = {"X-Admin-Key": args.admin_key}

    with httpx.Client(timeout=300.0) as client:
        for season in seasons:
            for rd in rounds:
                params: dict[str, int] = {"season": season}
                if takes_competition:
                    params["competition"] = args.competition
                if rd is not None:
                    params["round"] = rd
                url = f"{args.api}/api/admin/scout/{args.source}"
                label = f"season={season}" + (f" round={rd}" if rd is not None else "")
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

    print(f"\n=== Backfill summary ===", file=sys.stderr)
    print(f"  source: {args.source}", file=sys.stderr)
    print(f"  seasons: {seasons[0]}..{seasons[-1]} ({len(seasons)} years)", file=sys.stderr)
    if takes_round:
        print(f"  rounds: {args.round_from}..{args.round_to}", file=sys.stderr)
    print(f"  successes: {successes}", file=sys.stderr)
    print(f"  failures: {len(failures)}", file=sys.stderr)
    for season, rd, msg in failures[:20]:
        print(f"    {season} round={rd}: {msg}", file=sys.stderr)
    if len(failures) > 20:
        print(f"    ... and {len(failures) - 20} more", file=sys.stderr)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
