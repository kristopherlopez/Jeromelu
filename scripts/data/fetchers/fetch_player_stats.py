"""Fetch post-game player stats from nrlsupercoachstats.com.

Usage:
    python scripts/fetchers/fetch_player_stats.py --round 2 --season 2026
    python scripts/fetchers/fetch_player_stats.py --round 2  # defaults to 2026

Output:
    data/player_stats/round_02.yaml
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import yaml

# Add packages to path for shared utilities
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


def fetch_round_stats(season: int, round_num: int) -> list[dict]:
    """Fetch all player stats for a specific round from nrlsupercoachstats.com."""
    all_rows: list[dict] = []

    rd_filter = "Totals" if round_num == 0 else f"{round_num:02d}"
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
            logger.info("Fetching page %d", page)
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

            try:
                data = resp.json()
            except Exception:
                logger.error("Failed to parse JSON on page %d", page)
                break

            rows = data.get("rows", [])
            if not rows:
                logger.info("No rows on page %d — done", page)
                break

            all_rows.extend(rows)
            logger.info("Page %d: %d rows", page, len(rows))

            total_pages = int(data.get("total", 1))
            if page >= total_pages:
                break
            page += 1

    logger.info("Total raw rows: %d", len(all_rows))

    players: list[dict] = []
    for row in all_rows:
        raw_name = str(row.get("Name2", "")).strip()
        if not raw_name:
            raw_name = clean_name(str(row.get("Name", "")))
        if not raw_name:
            continue

        name = normalize_name(raw_name)
        team = normalize_team(str(row.get("Team", "")))
        all_stats = extract_all_stats(row)

        player = {
            "name": name,
            "team": team,
            "position": str(row.get("Posn1", "")).strip(),
            "jersey": all_stats.get("jersey"),
            "score": parse_int(row.get("Score", 0)),
            "price": parse_int(row.get("Price", 0)),
            "breakeven": parse_int(row.get("BE", 0)),
            "minutes": parse_int(row.get("Time", 0)) or None,
            "ppm": all_stats.get("ppm"),
            # SC breakdown
            "base": all_stats.get("base"),
            "attack": all_stats.get("attack"),
            "playmaking": all_stats.get("playmaking"),
            "power": all_stats.get("power"),
            "negative": all_stats.get("negative"),
            # Scoring
            "tries": all_stats.get("tries"),
            "try_assists": all_stats.get("try_assists"),
            "goals": all_stats.get("goals"),
            "field_goals": all_stats.get("field_goals"),
            # Attack
            "line_breaks": all_stats.get("line_breaks"),
            "tackle_busts": all_stats.get("tackle_busts"),
            "offloads": all_stats.get("offloads"),
            "kick_metres": all_stats.get("kick_metres"),
            # Defence
            "tackles_made": all_stats.get("tackles_made"),
            "missed_tackles": all_stats.get("missed_tackles"),
            "intercepts": all_stats.get("intercepts"),
            # Discipline
            "errors": all_stats.get("errors"),
            "penalties": all_stats.get("penalties"),
            "sin_bins": all_stats.get("sin_bins"),
            # Context
            "opposition": all_stats.get("opposition"),
        }
        players.append(player)

    logger.info("Parsed %d players", len(players))
    return players


def main():
    parser = argparse.ArgumentParser(description="Fetch NRL player stats for a round")
    parser.add_argument("--round", type=int, required=True, help="Round number")
    parser.add_argument("--season", type=int, default=2026, help="Season year (default: 2026)")
    args = parser.parse_args()

    players = fetch_round_stats(args.season, args.round)

    if not players:
        logger.error("No player data found for round %d, season %d", args.round, args.season)
        sys.exit(1)

    # Sort by team then score descending
    players.sort(key=lambda p: (p["team"], -(p["score"] or 0)))

    output = {
        "round": args.round,
        "season": args.season,
        "fetched_at": datetime.now(AEST).isoformat(),
        "source": "nrlsupercoachstats.com",
        "player_count": len(players),
        "players": players,
    }

    out_dir = PROJECT_ROOT / "data" / "player_stats"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"round_{args.round:02d}.yaml"

    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(output, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("Written %d players to %s", len(players), out_path)

    # Print summary
    teams = {}
    for p in players:
        teams.setdefault(p["team"], []).append(p)

    print(f"\n{'='*60}")
    print(f"Round {args.round} Player Stats — {len(players)} players")
    print(f"{'='*60}")
    for team in sorted(teams.keys()):
        team_players = teams[team]
        avg_score = sum(p["score"] or 0 for p in team_players) / len(team_players)
        named = [p for p in team_players if p.get("jersey") and p["jersey"] > 0]
        print(f"  {team:15s}  {len(named):2d} named  avg={avg_score:.0f}")


if __name__ == "__main__":
    main()
