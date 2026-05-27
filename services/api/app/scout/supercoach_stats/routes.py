"""Scout/SuperCoach stats admin endpoint with the standard agent_audit wrapper.

POST /api/admin/scout/supercoach-stats?round=N&season=Y
  - Walks the jqGrid endpoint for the requested (season, round).
  - Extracts + strict-parses every row (D8 drift detection).
  - Bulk-upserts into player_rounds with idempotent ON CONFLICT
    (player_id, round, season) DO UPDATE.
  - Writes an agent_runs row under agent_id='scout',
    detail_json.pipeline='supercoach-stats'.
  - Returns {run_id, ok, round, season, fetched, upserted}.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from jeromelu_shared.db.models import PlayerRound
from jeromelu_shared.scraping.nrl import STAT_DB_COLUMNS

from ...deps import get_db
from ...routers.admin import require_admin
from .._s3_archive import archive_response
from ..common.pipeline_run import set_archive_detail, start_deterministic_run
from .fetcher import (
    SuperCoachStatsFetchError,
    extract_rows,
    fetch_stats_raw,
)
from .models import SuperCoachPlayerStats

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "supercoach-stats"

# Identity + base columns always present on each upsert row
_IDENTITY = ("player_id", "player_name", "team", "position", "round", "season")
_BASE = ("score", "price", "breakeven", "minutes")
# On conflict, refresh everything except the identity PK fields.
_UPDATE_COLUMNS = (
    "player_name", "team", "position",
    *_BASE,
    *STAT_DB_COLUMNS,
)


def _upsert_player_rounds(
    db: Session, *, players: list[dict[str, Any]], round: int, season: int,
) -> int:
    """Bulk upsert to player_rounds. Returns the row count upserted.

    Idempotent: ON CONFLICT (player_id, round, season) refreshes the
    mutable columns and leaves identity untouched.
    """
    if not players:
        return 0

    values = []
    for p in players:
        rec = {col: p.get(col) for col in _IDENTITY}
        rec["round"] = round
        rec["season"] = season
        for col in _BASE:
            rec[col] = p.get(col)
        for col in STAT_DB_COLUMNS:
            rec[col] = p.get(col)
        values.append(rec)

    stmt = insert(PlayerRound).values(values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_player_round_season",
        set_={col: stmt.excluded[col] for col in _UPDATE_COLUMNS},
    )
    db.execute(stmt)
    db.commit()
    return len(values)


def run_supercoach_stats(
    db: Session,
    *,
    season: int,
    round: int,
) -> dict[str, Any]:
    """Fetch + strict-parse + upsert, wrapped in the agent_audit pattern.

    Returns the run summary including run_id, ok, season, round, fetched,
    upserted.
    """
    brief = f"SuperCoach stats fetch + upsert (season={season}, round={round})"
    run = start_deterministic_run(
        db,
        pipeline=PIPELINE,
        brief=brief,
        detail={
            "season": season,
            "round": round,
        },
        max_wall_seconds=300,
    )
    detail = run.detail
    fetched = 0
    upserted = 0

    try:
        # Fetch raw paginated jqGrid rows, archive to S3 (D10), then extract+strict-parse.
        raw_rows = fetch_stats_raw(season=season, round=round)
        if not raw_rows:
            raise SuperCoachStatsFetchError(
                f"Empty response for season={season} round={round}"
            )

        archive_key = archive_response(
            source="nrlsupercoachstats",
            pipeline="stats",
            identity_path=f"{season}/round-{round:02d}.json",
            payload={"season": season, "round": round, "rows": raw_rows},
        )
        set_archive_detail(detail, archive_key)

        extracted = extract_rows(raw_rows)
        if not extracted:
            raise SuperCoachStatsFetchError(
                f"Zero parseable rows after extraction (raw: {len(raw_rows)})"
            )
        # Strict-parse per D8 — drift in any field raises ValidationError.
        players = [SuperCoachPlayerStats.model_validate(p) for p in extracted]
        fetched = len(players)
        as_dicts = [p.model_dump() for p in players]
        upserted = _upsert_player_rounds(
            db, players=as_dicts, round=round, season=season,
        )
        detail.update({"fetched": fetched, "upserted": upserted})
    except SuperCoachStatsFetchError as e:
        detail["fetched"] = fetched
        run.fail(e, summary_text=f"Upstream fetch failed: {e}")
        raise HTTPException(status_code=502, detail=f"SC stats fetch failed: {e}")
    except Exception as e:
        detail["fetched"] = fetched
        run.fail(e, summary_text=f"Pipeline failed: {e}")
        raise

    run.complete(
        summary_text=(
            f"SuperCoach stats refresh: season={season} round={round} "
            f"fetched={fetched} upserted={upserted}"
        )
    )

    return {
        "run_id": run.run_id,
        "ok": True,
        "pipeline": PIPELINE,
        "season": season,
        "round": round,
        "fetched": fetched,
        "upserted": upserted,
    }


@router.post(
    "/admin/scout/supercoach-stats",
    dependencies=[Depends(require_admin)],
)
def supercoach_stats_endpoint(
    round: int = Query(
        ...,
        ge=0,
        le=30,
        description="Round number (0 = Totals / season aggregate; 1-30 = regular rounds)",
    ),
    season: int | None = Query(
        default=None,
        description="SC season year (defaults to current year)",
    ),
    db: Session = Depends(get_db),
):
    """Acquire SuperCoach stats for one (round, season) and upsert into player_rounds.

    Cron-friendly: no payload, single admin key. The API container walks
    the jqGrid endpoint, extracts the ~58-field shape via shared utilities,
    strict-parses each row per D8, and bulk-upserts with idempotent
    ON CONFLICT (player_id, round, season). One `agent_runs` row per call
    under `agent_id='scout'`, `detail_json.pipeline='supercoach-stats'`.
    """
    effective_season = season or date.today().year
    return run_supercoach_stats(db, season=effective_season, round=round)
