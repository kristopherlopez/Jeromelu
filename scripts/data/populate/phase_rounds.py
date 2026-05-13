"""Phase 2a — extract rounds from scout/nrlcom/draw/* archives.

One row per (season, round_number). Idempotent upsert keyed on the existing
unique constraint `rounds_season_round_number_key`.

Round label is taken from `filterRounds[].name` where the value matches
`selectedRoundId`. Kickoff bounds (`starts_at`, `ends_at`) are derived as
min/max of `fixtures[*].clock.kickOffTimeLong`.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ._s3_walk import list_keys, read_json_concurrent

logger = logging.getLogger(__name__)


# Filename pattern: scout/nrlcom/draw/111/<season>/round-<NN>.json
_KEY_RE = re.compile(r"scout/nrlcom/draw/\d+/(\d{4})/round-(\d+)\.json$")


def _extract_one(payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    m = _KEY_RE.search(key)
    if not m:
        return None
    season = int(m.group(1))
    round_number = int(m.group(2))

    round_label = f"Round {round_number}"
    for r in payload.get("filterRounds") or []:
        if r.get("value") == round_number:
            round_label = r.get("name") or round_label
            break

    kickoffs: list[str] = []
    for f in payload.get("fixtures") or []:
        k = (f.get("clock") or {}).get("kickOffTimeLong")
        if k:
            kickoffs.append(k)
    starts_at = min(kickoffs) if kickoffs else None
    ends_at = max(kickoffs) if kickoffs else None

    is_finals = "Final" in round_label or "Qualifying" in round_label or "Elimination" in round_label

    return {
        "season": season,
        "round_number": round_number,
        "round_label": round_label,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "is_finals": is_finals,
    }


def populate_rounds(
    db: Session,
    *,
    seasons: list[int] | None = None,
    competition: int = 111,
) -> dict[str, Any]:
    keys = list_keys(f"scout/nrlcom/draw/{competition}/")
    if seasons:
        seasons_set = {str(s) for s in seasons}
        keys = [k for k in keys if any(f"/{s}/" in k for s in seasons_set)]
    logger.info("phase_rounds: %d draw archives to scan", len(keys))

    rounds_seen: dict[tuple[int, int], dict] = {}
    archives_read = 0
    archives_failed = 0
    for key, payload, err in read_json_concurrent(keys, max_workers=16):
        if err is not None or payload is None:
            archives_failed += 1
            continue
        archives_read += 1
        row = _extract_one(payload, key)
        if row is None:
            continue
        rounds_seen[(row["season"], row["round_number"])] = row

    logger.info("phase_rounds: %d distinct rounds (from %d archives, %d failed)",
                len(rounds_seen), archives_read, archives_failed)

    inserted = 0
    updated = 0
    for row in rounds_seen.values():
        res = db.execute(
            text("""
                INSERT INTO rounds (season, round_number, round_label, starts_at, ends_at, is_finals)
                VALUES (:season, :round_number, :round_label, :starts_at, :ends_at, :is_finals)
                ON CONFLICT (season, round_number) DO UPDATE
                SET round_label = EXCLUDED.round_label,
                    starts_at = EXCLUDED.starts_at,
                    ends_at = EXCLUDED.ends_at,
                    is_finals = EXCLUDED.is_finals
                RETURNING (xmax = 0) AS inserted
            """),
            row,
        )
        was_insert = res.scalar()
        if was_insert:
            inserted += 1
        else:
            updated += 1
    db.commit()

    logger.info("phase_rounds: inserted=%d updated=%d", inserted, updated)
    return {
        "archives_read": archives_read,
        "archives_failed": archives_failed,
        "rounds_seen": len(rounds_seen),
        "rounds_inserted": inserted,
        "rounds_updated": updated,
    }
