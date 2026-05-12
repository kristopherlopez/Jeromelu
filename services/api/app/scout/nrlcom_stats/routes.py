"""nrl.com stats admin endpoint — pure capture."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
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
from .fetcher import NrlcomStatsFetchError, fetch_stats

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "nrlcom-stats"
AGENT_ID = "scout"
AGENT_NAME = "Scout"
MODEL = "deterministic"


def run_nrlcom_stats(
    db: Session, *, competition: int, season: int,
) -> dict[str, Any]:
    run_id = make_run_id(AGENT_ID)
    bounds = AgentBounds(
        max_turns=0, max_tool_calls=0, max_wall_seconds=60, max_budget_usd=0.0,
    )
    brief = f"nrl.com stats (comp={competition} season={season})"
    record_agent_started(
        db,
        agent_id=AGENT_ID, agent_name=AGENT_NAME, run_id=run_id,
        model=MODEL, brief=brief,
        bounds={
            **{k: getattr(bounds, k) for k in ("max_turns", "max_tool_calls", "max_wall_seconds", "max_budget_usd")},
            "pipeline": PIPELINE,
            "competition": competition,
            "season": season,
        },
    )
    detail: dict[str, Any] = {
        "pipeline": PIPELINE, "competition": competition, "season": season,
    }
    try:
        data = fetch_stats(competition=competition, season=season)
        archive_key = archive_response(
            source="nrlcom",
            pipeline="stats",
            identity_path=f"{competition}/{season}.json",
            payload=data,
        )
        detail.update({
            "player_stat_groups": len(data.get("playerStats", [])),
            "team_stat_groups": len(data.get("teamStats", [])),
            "s3_archive_key": archive_key,
        })
        if archive_key is None:
            detail["s3_archive_failed"] = True
        logger.info("scout/nrlcom-stats: comp=%s season=%s s3=%s",
                    competition, season, archive_key)
    except NrlcomStatsFetchError as e:
        detail["error"] = f"NrlcomStatsFetchError: {e}"
        record_agent_ended(
            db, run_id=run_id, status="failed",
            summary_text=f"Upstream fetch failed: {e}", model=MODEL, detail=detail,
        )
        raise HTTPException(status_code=502, detail=f"stats fetch failed: {e}")
    except Exception as e:
        detail["error"] = f"{type(e).__name__}: {e}"
        record_agent_ended(
            db, run_id=run_id, status="failed",
            summary_text=f"Pipeline failed: {e}", model=MODEL, detail=detail,
        )
        raise

    record_agent_ended(
        db, run_id=run_id, status="completed",
        summary_text=f"nrl.com stats: comp={competition} season={season}",
        model=MODEL, detail=detail,
    )
    return {"run_id": run_id, "ok": True, **detail}


@router.post(
    "/admin/scout/nrlcom-stats",
    dependencies=[Depends(require_admin)],
)
def nrlcom_stats_endpoint(
    competition: int = Query(default=111),
    season: int = Query(...),
    db: Session = Depends(get_db),
):
    """Fetch nrl.com /stats/data and archive to S3."""
    return run_nrlcom_stats(db, competition=competition, season=season)
