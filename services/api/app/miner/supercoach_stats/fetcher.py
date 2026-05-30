"""Fetch + extract per-round SuperCoach stats from nrlsupercoachstats.com.

Self-contained: inlines the jqGrid pagination logic (~50 lines). The
predecessor Temporal worker at `services/worker-scraper/` was retired and
deleted 2026-05-28 (Miner Phase 4 closure / TASK-28); the cleaning /
parsing utilities (JQGRID_COLUMN_MAP, extract_all_stats, parsers) live
in `jeromelu_shared.scraping.nrl` and are shared across Miner pipelines.

After fetching, every extracted row is parsed through `SuperCoachPlayerStats`
(strict Pydantic per D8) — drift on any field we depend on raises.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from jeromelu_shared.scraping.nrl import (
    clean_name,
    extract_all_stats,
    generate_player_id,
    normalize_name,
    normalize_team,
    parse_int,
)

from .models import SuperCoachPlayerStats

logger = logging.getLogger(__name__)


BASE_URL = "https://nrlsupercoachstats.com"
PAGE_SIZE = 200
DEFAULT_TIMEOUT = 30.0


class SuperCoachStatsFetchError(RuntimeError):
    """Raised when the SC stats fetch returns an unexpected payload or
    contains rows that fail strict validation."""


def fetch_stats_raw(season: int, round: int, timeout: float = DEFAULT_TIMEOUT) -> list[dict[str, Any]]:
    """Walk the jqGrid endpoint and return every raw row for the given
    (season, round). `round=0` fetches "Totals". Pure-ish — single HTTP
    session, no DB. Returns the raw upstream rows (95 fields each).
    """
    rd_filter = "Totals" if round == 0 else f"{round:02d}"
    filters = json.dumps(
        {
            "groupOp": "AND",
            "rules": [{"field": "Rd", "op": "eq", "data": rd_filter}],
        }
    )

    all_rows: list[dict[str, Any]] = []
    with httpx.Client(
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
        timeout=timeout,
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
                    "rows": PAGE_SIZE,
                    "jqgrid_page": page,
                    "sidx": "Name",
                    "sord": "asc",
                    "filters": filters,
                },
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json",
                    "Referer": page_url,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            rows = data.get("rows", [])
            if not rows:
                break
            all_rows.extend(rows)
            total_pages = int(data.get("total", 1))
            if page >= total_pages:
                break
            page += 1

    return all_rows


def extract_rows(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Transform raw jqGrid rows into the extracted-shape dicts.

    Skips rows with no resolvable name. Returns the cleaned shape — same
    structure SuperCoachPlayerStats expects. No DB writes here; persistence
    is the caller's responsibility.
    """
    extracted: list[dict[str, Any]] = []
    for row in raw_rows:
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
        extracted.append(player)
    return extracted


def fetch_strict(season: int, round: int, timeout: float = DEFAULT_TIMEOUT) -> list[SuperCoachPlayerStats]:
    """GET the upstream stats, extract, and strict-parse every row.

    Raises:
        SuperCoachStatsFetchError: empty response or zero parseable rows.
        pydantic.ValidationError: a row failed strict parsing — D8 drift signal.
            Propagates; do not catch.
    """
    raw_rows = fetch_stats_raw(season=season, round=round, timeout=timeout)
    if not raw_rows:
        raise SuperCoachStatsFetchError(f"Empty response for season={season} round={round}")
    extracted = extract_rows(raw_rows)
    if not extracted:
        raise SuperCoachStatsFetchError(f"Zero parseable rows after extraction (raw rows: {len(raw_rows)})")
    parsed = [SuperCoachPlayerStats.model_validate(p) for p in extracted]
    logger.info(
        "supercoach-stats: season=%s round=%s — fetched %d raw rows, extracted %d, strict-parsed %d",
        season,
        round,
        len(raw_rows),
        len(extracted),
        len(parsed),
    )
    return parsed


__all__ = ["SuperCoachStatsFetchError", "extract_rows", "fetch_stats_raw", "fetch_strict"]
