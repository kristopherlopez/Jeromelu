"""Fetch post-game match stats, derived from player-level data.

Aggregates player stats per team per match to produce team-level match summaries.
Uses the same nrlsupercoachstats.com source as fetch_player_stats.py.

Usage:
    python scripts/fetchers/fetch_match_stats.py --round 2 --season 2026
    python scripts/fetchers/fetch_match_stats.py --round 2  # defaults to 2026

Output:
    data/match_stats/round_02.yaml
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


def fetch_and_aggregate(season: int, round_num: int) -> dict:
    """Fetch player data and aggregate into team-level match stats."""
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

    # Parse players and group by team
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
        stats = extract_all_stats(row)

        if jersey > 0:  # Only named squad
            opp_raw = str(row.get("vs", "")).strip()
            opp_normalized = normalize_team(opp_raw) if opp_raw else None
            teams[team].append({
                "name": name,
                "jersey": jersey,
                "score": parse_int(row.get("Score", 0)),
                "position": str(row.get("Posn1", "")).strip(),
                "opposition": opp_normalized,
                **{k: v for k, v in stats.items() if k != "opposition"},
            })

    # Build matches from opposition pairs
    matches = []
    matched_teams = set()

    for team in sorted(teams.keys()):
        if team in matched_teams:
            continue
        players = teams[team]
        if not players:
            continue

        opp = players[0].get("opposition")
        if not opp or opp not in teams or opp in matched_teams:
            continue

        home_players = players
        away_players = teams[opp]

        def aggregate(player_list):
            """Sum key stats across all players in the team."""
            agg = {
                "total_sc_points": sum(p.get("score", 0) or 0 for p in player_list),
                "tries": sum(p.get("tries", 0) or 0 for p in player_list),
                "try_assists": sum(p.get("try_assists", 0) or 0 for p in player_list),
                "goals": sum(p.get("goals", 0) or 0 for p in player_list),
                "field_goals": sum(p.get("field_goals", 0) or 0 for p in player_list),
                "line_breaks": sum(p.get("line_breaks", 0) or 0 for p in player_list),
                "tackle_busts": sum(p.get("tackle_busts", 0) or 0 for p in player_list),
                "offloads": sum(p.get("offloads", 0) or 0 for p in player_list),
                "kick_metres": sum(p.get("kick_metres", 0) or 0 for p in player_list),
                "tackles_made": sum(p.get("tackles_made", 0) or 0 for p in player_list),
                "missed_tackles": sum(p.get("missed_tackles", 0) or 0 for p in player_list),
                "errors": sum(p.get("errors", 0) or 0 for p in player_list),
                "penalties": sum(p.get("penalties", 0) or 0 for p in player_list),
                "sin_bins": sum(p.get("sin_bins", 0) or 0 for p in player_list),
                "intercepts": sum(p.get("intercepts", 0) or 0 for p in player_list),
            }
            # Derive NRL score from tries (4pts each in NRL, but SC uses different scoring)
            # SC tries value is points not count, so tries/17 ≈ actual try count
            return agg

        home_stats = aggregate(home_players)
        away_stats = aggregate(away_players)

        # Top scorers (SC points)
        home_top = sorted(home_players, key=lambda p: p.get("score", 0) or 0, reverse=True)[:5]
        away_top = sorted(away_players, key=lambda p: p.get("score", 0) or 0, reverse=True)[:5]

        # Try scorers (players with tries > 0)
        home_try_scorers = [p["name"] for p in home_players if (p.get("tries") or 0) > 0]
        away_try_scorers = [p["name"] for p in away_players if (p.get("tries") or 0) > 0]

        matches.append({
            "home": team,
            "away": opp,
            "stats": {
                team: home_stats,
                opp: away_stats,
            },
            "try_scorers": {
                team: home_try_scorers,
                opp: away_try_scorers,
            },
            "top_sc_scorers": {
                team: [{"name": p["name"], "score": p["score"], "position": p.get("position")}
                       for p in home_top],
                opp: [{"name": p["name"], "score": p["score"], "position": p.get("position")}
                      for p in away_top],
            },
        })
        matched_teams.add(team)
        matched_teams.add(opp)

    return {
        "round": round_num,
        "season": season,
        "fetched_at": datetime.now(AEST).isoformat(),
        "source": "nrlsupercoachstats.com (aggregated from player stats)",
        "match_count": len(matches),
        "matches": matches,
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch NRL match stats for a round")
    parser.add_argument("--round", type=int, required=True, help="Round number")
    parser.add_argument("--season", type=int, default=2026, help="Season year (default: 2026)")
    args = parser.parse_args()

    result = fetch_and_aggregate(args.season, args.round)

    if not result["matches"]:
        logger.error("No match data found for round %d, season %d", args.round, args.season)
        sys.exit(1)

    out_dir = PROJECT_ROOT / "data" / "match_stats"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"round_{args.round:02d}.yaml"

    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(result, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("Written %d matches to %s", len(result["matches"]), out_path)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Round {args.round} Match Stats — {len(result['matches'])} matches")
    print(f"{'='*60}")
    for match in result["matches"]:
        home = match["home"]
        away = match["away"]
        hs = match["stats"][home]
        as_ = match["stats"][away]
        print(f"\n  {home} vs {away}")
        print(f"    SC Points:    {hs['total_sc_points']:>4} - {as_['total_sc_points']:<4}")
        print(f"    Tries (SC):   {hs['tries']:>4} - {as_['tries']:<4}")
        print(f"    Line Breaks:  {hs['line_breaks']:>4} - {as_['line_breaks']:<4}")
        print(f"    Tackles:      {hs['tackles_made']:>4} - {as_['tackles_made']:<4}")
        print(f"    Missed:       {hs['missed_tackles']:>4} - {as_['missed_tackles']:<4}")
        print(f"    Errors:       {hs['errors']:>4} - {as_['errors']:<4}")


if __name__ == "__main__":
    main()
