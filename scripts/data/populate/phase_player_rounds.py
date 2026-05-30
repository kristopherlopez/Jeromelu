"""Phase 5 — extract player_rounds from miner/nrlsupercoachstats/stats/* archives.

One row per (player_id, round, season) — idempotent UPSERT on the
`uq_player_round_season` unique index. Same projection the supercoach-stats
route does inline, but reading S3 archives (so historical backfill works:
the route's `archive_only=true` mode captures S3 without DB writes; this
extractor lands the DB rows era-aware).

S3 archive shape (per `services/api/app/miner/supercoach_stats/routes.py`):
    {"season": <int>, "round": <int>, "rows": [<raw jqGrid dicts>]}
Key path:
    miner/nrlsupercoachstats/stats/{season}/round-{NN:02d}.json

Per-row pipeline (matches the route's logic):
    raw jqGrid dict → extract_rows() → SuperCoachPlayerStats.model_validate()

Per the Phase 5 plan: if a historical season's shape differs from modern
(e.g. 2018 lacks a column today's model requires), the per-row strict-parse
raises ValidationError; the extractor records the failure in `failures[]`
and continues — same non-aborting pattern as match-centre's
`validation_failures`. The operator then iterates the model (add a legacy
variant, relax a field) and re-runs.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.miner.supercoach_stats.fetcher import extract_rows
from app.miner.supercoach_stats.models import SuperCoachPlayerStats
from jeromelu_shared.scraping.nrl import STAT_DB_COLUMNS

from ._s3_walk import list_keys, read_json_concurrent

logger = logging.getLogger(__name__)


_KEY_RE = re.compile(
    r"miner/nrlsupercoachstats/stats/(?P<season>\d{4})/round-(?P<round>\d+)\.json$"
)


# Identity + base columns, in the same order the route's _upsert_player_rounds uses.
_IDENTITY = ("player_id", "player_name", "team", "position", "round", "season")
_BASE = ("score", "price", "breakeven", "minutes")

# Columns refreshed on conflict — identity-PK is left alone.
_UPDATE_COLUMNS = (
    "player_name", "team", "position",
    *_BASE,
    *STAT_DB_COLUMNS,
)


def _extract_player_round_rows(
    payload: dict[str, Any],
    *,
    season: int,
    round_no: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pure projection: archive payload → (extracted_rows, failures).

    `payload` is the S3 archive object: `{season, round, rows: [<raw jqGrid>]}`.
    The `season` and `round_no` kwargs come from the S3 key path; they override
    whatever is in the payload itself (defensive — the key is authoritative).

    Returns:
        - `extracted_rows`: list of dicts ready for UPSERT — each carries the
          full `_IDENTITY + _BASE + STAT_DB_COLUMNS` keyset, with NULLs where
          the raw row lacked the column.
        - `failures`: list of `{player_name_hint, error}` for per-row
          ValidationError; the per-row strict-parse is non-aborting so one
          bad row doesn't lose the rest of the archive's data.
    """
    raw_rows = payload.get("rows") or []
    extracted_dicts = extract_rows(raw_rows)

    out: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for d in extracted_dicts:
        try:
            parsed = SuperCoachPlayerStats.model_validate(d)
        except ValidationError as e:
            failures.append({
                "player_name_hint": d.get("player_name"),
                "error": str(e)[:300],
            })
            continue
        row = parsed.model_dump()
        # Pin season/round from the authoritative key path (the payload's
        # own season/round are double-checked but the key wins on disagreement).
        row["season"] = season
        row["round"] = round_no
        out.append(row)
    return out, failures


def populate_player_rounds(
    db: Session,
    *,
    seasons: list[int] | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    """Walk miner/nrlsupercoachstats/stats/* archives and UPSERT player_rounds.

    Mirrors the inline route logic (see `supercoach_stats/routes.py`) but
    reads from S3 instead of fetching. Used by Phase 5 historical backfill
    after the route's `archive_only=true` mode has populated S3.
    """
    keys = list_keys("miner/nrlsupercoachstats/stats/")
    if seasons:
        season_strs = {f"/{s}/" for s in seasons}
        keys = [k for k in keys if any(s in k for s in season_strs)]
    logger.info("phase_player_rounds: %d SC stats archives to scan", len(keys))

    archives_read = 0
    archives_failed = 0
    rows_extracted = 0
    inserted = 0
    updated = 0
    failures: list[dict[str, Any]] = []

    insert_cols = (
        "player_id, player_name, team, position, round, season, "
        + ", ".join(_BASE) + ", "
        + ", ".join(STAT_DB_COLUMNS)
    )
    placeholders = (
        ":player_id, :player_name, :team, :position, :round, :season, "
        + ", ".join(f":{c}" for c in _BASE) + ", "
        + ", ".join(f":{c}" for c in STAT_DB_COLUMNS)
    )
    update_cols_sql = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in _UPDATE_COLUMNS
    )
    upsert_sql = text(f"""
        INSERT INTO player_rounds ({insert_cols})
        VALUES ({placeholders})
        ON CONFLICT ON CONSTRAINT uq_player_round_season
        DO UPDATE SET {update_cols_sql}
        RETURNING (xmax = 0) AS inserted
    """)

    for key, payload, err in read_json_concurrent(keys, max_workers=16):
        if err is not None or payload is None:
            archives_failed += 1
            continue
        archives_read += 1
        m = _KEY_RE.search(key)
        if not m:
            continue
        season = int(m.group("season"))
        round_no = int(m.group("round"))
        rows, archive_failures = _extract_player_round_rows(
            payload, season=season, round_no=round_no,
        )
        if archive_failures:
            for f in archive_failures:
                f["archive_key"] = key
            failures.extend(archive_failures)
        rows_extracted += len(rows)
        for row in rows:
            res = db.execute(upsert_sql, row)
            if res.scalar():
                inserted += 1
            else:
                updated += 1
        if archives_read % 50 == 0:
            if commit: db.commit()  # checkpoint per the streaming-loop lesson

    if commit: db.commit()
    logger.info(
        "phase_player_rounds: archives_read=%d archives_failed=%d "
        "rows_extracted=%d inserted=%d updated=%d failures=%d",
        archives_read, archives_failed, rows_extracted, inserted, updated, len(failures),
    )
    return {
        "archives_read": archives_read,
        "archives_failed": archives_failed,
        "rows_extracted": rows_extracted,
        "inserted": inserted,
        "updated": updated,
        "failures": failures[:20],  # bound the response; full list in logs
        "failure_count": len(failures),
    }
