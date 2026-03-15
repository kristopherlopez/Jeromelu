"""Fetch player prices from nrlsupercoachstats.com jqGrid endpoint."""

import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from temporalio import activity

from jeromelu_shared.s3 import upload_player_data
from jeromelu_shared.scraping.nrl import (
    clean_name,
    extract_all_stats,
    generate_player_id,
    normalize_name,
    normalize_team,
    parse_float,
    parse_int,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://nrlsupercoachstats.com"
AEST = timezone(timedelta(hours=11))


def _scrape_prices(season: int, round: int) -> list[dict]:
    """Fetch player data from the jqGrid endpoint (sync / blocking).

    round=0 fetches Totals (pre-season prices), round>0 fetches per-round stats.
    """
    all_rows: list[dict] = []

    # Round 0 → "Totals" for pre-season/aggregate; otherwise zero-padded round number
    rd_filter = "Totals" if round == 0 else f"{round:02d}"
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

        player = {
            "player_id": generate_player_id(name, team),
            "player_name": name,
            "team": team,
            "position": str(row.get("Posn1", "")).strip(),
            "price": parse_int(row.get("Price", 0)),
            "breakeven": parse_int(row.get("BE", 0)),
            "score": parse_int(row.get("Score", 0)),
            "minutes": parse_int(row.get("Time", 0)) or None,
            **extract_all_stats(row),
        }
        players.append(player)

    logger.info("Parsed %d players", len(players))
    return players


@activity.defn
def fetch_prices(round: int, season: int) -> dict:
    """Fetch player prices for a given round and season.

    Returns dict with keys: row_count, s3_key, rows (list of dicts).
    """
    players = _scrape_prices(season, round)

    s3_key = f"prices/{season}/round_{round:02d}.json"
    snapshot = {
        "round": round,
        "season": season,
        "fetched_at": datetime.now(AEST).isoformat(),
        "source": "nrlsupercoachstats.com",
        "players": players,
    }
    upload_player_data(s3_key, json.dumps(snapshot, indent=2, ensure_ascii=False))
    logger.info("Uploaded %d players to s3://%s", len(players), s3_key)

    return {
        "row_count": len(players),
        "s3_key": s3_key,
        "rows": players,
    }
