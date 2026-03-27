"""Fetch weekly NRL team lists.

Primary source: nrlsupercoachstats.com (jersey numbers from player stats data)
Future: nrl.com/draw via Playwright for reserves and positional detail

Usage:
    python scripts/fetchers/fetch_teamlists.py --round 2 --season 2026
    python scripts/fetchers/fetch_teamlists.py --round 2  # defaults to 2026

Output:
    data/teamlists/round_02.yaml
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "shared"))

from jeromelu_shared.scraping.nrl import (
    clean_name,
    extract_all_stats,
    normalize_name,
    normalize_team,
    parse_int,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://nrlsupercoachstats.com"
AEST = timezone(timedelta(hours=11))
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Map opposition codes to short team names
OPP_TO_TEAM = {
    "BRO": "Broncos", "BUL": "Bulldogs", "CBR": "Raiders",
    "DOL": "Dolphins", "DRA": "Dragons", "EEL": "Eels",
    "KNI": "Knights", "COW": "Cowboys", "MAN": "Sea Eagles",
    "MEL": "Storm", "PAN": "Panthers", "PAR": "Eels",
    "RAB": "Rabbitohs", "ROO": "Roosters", "SHA": "Sharks",
    "TIG": "Tigers", "TIT": "Titans", "WAR": "Warriors",
    "NQL": "Cowboys", "NEW": "Knights", "CRO": "Sharks",
    "SOU": "Rabbitohs", "SYD": "Roosters", "GLD": "Titans",
    "NZL": "Warriors", "WES": "Tigers", "CAN": "Raiders",
    "STG": "Dragons", "PEN": "Panthers", "BRI": "Broncos",
}


def fetch_teamlists_from_stats(season: int, round_num: int) -> dict:
    """Extract team lists from nrlsupercoachstats.com jqGrid data.

    Players with jersey numbers 1-22 are in the named squad.
    Jersey 1-13 = starting, 14-17 = interchange, 18-22 = reserves.
    """
    all_rows: list[dict] = []
    rd_filter = f"{round_num:02d}"
    filters = json.dumps({
        "groupOp": "AND",
        "rules": [{"field": "Rd", "op": "eq", "data": rd_filter}],
    })

    with httpx.Client(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        },
        follow_redirects=True,
        timeout=30.0,
    ) as client:
        page_url = f"{BASE_URL}/stats.php?year={season}"
        logger.info("Establishing session at %s", page_url)
        client.get(page_url)

        page = 1
        while True:
            resp = client.get(
                f"{BASE_URL}/stats.php",
                params={
                    "year": str(season),
                    "grid_id": "list1",
                    "_search": "true",
                    "rows": 200,
                    "jqgrid_page": page,
                    "sidx": "Name",
                    "sord": "asc",
                    "filters": filters,
                },
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Referer": page_url,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            rows = data.get("rows", [])
            if not rows:
                break
            all_rows.extend(rows)
            if page >= int(data.get("total", 1)):
                break
            page += 1

    logger.info("Total rows: %d", len(all_rows))

    # Group by team, filter to named squad (jersey > 0)
    teams: dict[str, list[dict]] = defaultdict(list)
    for row in all_rows:
        raw_name = str(row.get("Name2", "")).strip()
        if not raw_name:
            raw_name = clean_name(str(row.get("Name", "")))
        if not raw_name:
            continue

        name = normalize_name(raw_name)
        team = normalize_team(str(row.get("Team", "")))
        jersey = parse_int(row.get("Jersey", 0))
        position = str(row.get("Posn1", "")).strip()
        opposition = str(row.get("vs", "")).strip()

        if jersey > 0:
            teams[team].append({
                "jersey": jersey,
                "name": name,
                "position": position,
                "opposition": normalize_team(opposition) if opposition else None,
            })

    # Sort each team by jersey number
    for team in teams:
        teams[team].sort(key=lambda p: p["jersey"])

    # Build matches from opposition pairs
    matches = []
    matched_teams = set()

    for team, players in sorted(teams.items()):
        if team in matched_teams:
            continue
        if not players:
            continue

        opp = players[0].get("opposition")
        if opp and opp in teams and opp not in matched_teams:
            matches.append({
                "home": team,
                "away": opp,
                "team_lists": {
                    team: [{"jersey": p["jersey"], "name": p["name"], "position": p["position"]} for p in players],
                    opp: [{"jersey": p["jersey"], "name": p["name"], "position": p["position"]} for p in teams[opp]],
                },
            })
            matched_teams.add(team)
            matched_teams.add(opp)

    # Handle any unmatched teams (byes, data issues)
    for team, players in sorted(teams.items()):
        if team not in matched_teams and players:
            matches.append({
                "home": team,
                "away": "BYE",
                "team_lists": {
                    team: [{"jersey": p["jersey"], "name": p["name"], "position": p["position"]} for p in players],
                },
            })

    return {
        "round": round_num,
        "season": season,
        "fetched_at": datetime.now(AEST).isoformat(),
        "source": "nrlsupercoachstats.com",
        "match_count": len(matches),
        "matches": matches,
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch NRL team lists for a round")
    parser.add_argument("--round", type=int, required=True, help="Round number")
    parser.add_argument("--season", type=int, default=2026, help="Season year (default: 2026)")
    args = parser.parse_args()

    result = fetch_teamlists_from_stats(args.season, args.round)

    if not result["matches"]:
        logger.error("No team list data found for round %d, season %d", args.round, args.season)
        sys.exit(1)

    out_dir = PROJECT_ROOT / "data" / "teamlists"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"round_{args.round:02d}.yaml"

    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(result, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("Written %d matches to %s", len(result["matches"]), out_path)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Round {args.round} Team Lists — {len(result['matches'])} matches")
    print(f"{'='*60}")
    for match in result["matches"]:
        home = match["home"]
        away = match["away"]
        home_count = len(match["team_lists"].get(home, []))
        away_count = len(match["team_lists"].get(away, [])) if away != "BYE" else 0
        print(f"  {home:15s} vs {away:15s}  ({home_count} + {away_count} players)")


if __name__ == "__main__":
    main()
