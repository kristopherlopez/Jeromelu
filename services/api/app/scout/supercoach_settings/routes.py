"""Scout/SuperCoach settings admin endpoint with agent_audit + S3-first capture + DB row."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from jeromelu_shared.agent_audit import (
    AgentBounds,
    make_run_id,
    record_agent_ended,
    record_agent_started,
)

from ...deps import get_db
from ...routers.admin import require_admin
from .._s3_archive import archive_response
from .fetcher import SuperCoachSettingsFetchError, fetch_supercoach_settings
from .models import SuperCoachSettings

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "supercoach-settings"
AGENT_ID = "scout"
AGENT_NAME = "Scout"
MODEL = "deterministic"


def _upsert_sc_settings(
    db: Session, *, season: int, mode: str, payload: dict[str, Any], s3_key: str | None
) -> dict[str, Any]:
    """Insert one row per (season, captured_date, mode); same-day re-run = update."""
    stmt = text("""
        INSERT INTO sc_settings (season, mode, payload, s3_archive_key)
        VALUES (:season, :mode, CAST(:payload AS JSONB), :s3_key)
        ON CONFLICT (season, captured_date, mode)
        DO UPDATE SET
            captured_at = EXCLUDED.captured_at,
            payload = EXCLUDED.payload,
            s3_archive_key = COALESCE(EXCLUDED.s3_archive_key, sc_settings.s3_archive_key)
        RETURNING id
    """)
    import json
    result = db.execute(
        stmt,
        {"season": season, "mode": mode, "payload": json.dumps(payload), "s3_key": s3_key},
    )
    db.commit()
    row_id = result.scalar()
    return {"upserted_id": str(row_id)}


def run_supercoach_settings(
    db: Session,
    *,
    season: int | None = None,
    mode: str = "classic",
) -> dict[str, Any]:
    """Fetch SC settings + archive to S3 + upsert into sc_settings."""
    run_id = make_run_id(AGENT_ID)
    bounds = AgentBounds(
        max_turns=0, max_tool_calls=0, max_wall_seconds=60, max_budget_usd=0.0,
    )
    effective_season = season or date.today().year
    brief = f"SuperCoach settings snapshot (season={effective_season}, mode={mode})"
    record_agent_started(
        db,
        agent_id=AGENT_ID,
        agent_name=AGENT_NAME,
        run_id=run_id,
        model=MODEL,
        brief=brief,
        bounds={
            "max_turns": bounds.max_turns,
            "max_tool_calls": bounds.max_tool_calls,
            "max_wall_seconds": bounds.max_wall_seconds,
            "max_budget_usd": bounds.max_budget_usd,
            "pipeline": PIPELINE,
            "season": effective_season,
            "mode": mode,
        },
    )

    detail: dict[str, Any] = {
        "pipeline": PIPELINE,
        "season": effective_season,
        "mode": mode,
    }
    upsert_result: dict[str, Any] = {}

    try:
        raw_settings = fetch_supercoach_settings(season=season, mode=mode)

        archive_key = archive_response(
            source="supercoach",
            pipeline=f"{mode}/settings",
            identity_path=(
                f"{effective_season}/"
                f"{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
            ),
            payload=raw_settings,
        )
        detail["s3_archive_key"] = archive_key
        if archive_key is None:
            detail["s3_archive_failed"] = True

        # Strict-parse per D8 — validates the four top-level groups exist.
        SuperCoachSettings.model_validate(raw_settings)

        upsert_result = _upsert_sc_settings(
            db, season=effective_season, mode=mode,
            payload=raw_settings, s3_key=archive_key,
        )
        detail.update(upsert_result)
    except SuperCoachSettingsFetchError as e:
        detail["error"] = f"SuperCoachSettingsFetchError: {e}"
        record_agent_ended(
            db, run_id=run_id, status="failed",
            summary_text=f"Upstream fetch failed: {e}",
            model=MODEL, detail=detail,
        )
        raise HTTPException(status_code=502, detail=f"SC settings fetch failed: {e}")
    except Exception as e:
        detail["error"] = f"{type(e).__name__}: {e}"
        record_agent_ended(
            db, run_id=run_id, status="failed",
            summary_text=f"Pipeline failed: {e}",
            model=MODEL, detail=detail,
        )
        raise

    record_agent_ended(
        db, run_id=run_id, status="completed",
        summary_text=f"SuperCoach settings snapshot: season={effective_season} mode={mode}",
        model=MODEL, detail=detail,
    )

    return {
        "run_id": run_id,
        "ok": True,
        "pipeline": PIPELINE,
        "season": effective_season,
        "mode": mode,
        **upsert_result,
    }


@router.post(
    "/admin/scout/supercoach-settings",
    dependencies=[Depends(require_admin)],
)
def supercoach_settings_endpoint(
    season: int | None = Query(default=None),
    mode: str = Query(default="classic", pattern="^(classic|draft)$"),
    db: Session = Depends(get_db),
):
    """Snapshot SC game settings for one (season, mode) into S3 + sc_settings."""
    return run_supercoach_settings(db, season=season, mode=mode)
