"""nrl.com ladder admin endpoint — pure capture."""

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
from .fetcher import NrlcomLadderFetchError, fetch_ladder

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "nrlcom-ladder"
AGENT_ID = "scout"
AGENT_NAME = "Scout"
MODEL = "deterministic"


def run_nrlcom_ladder(
    db: Session,
    *,
    competition: int,
    season: int,
    round: int | None = None,
) -> dict[str, Any]:
    run_id = make_run_id(AGENT_ID)
    bounds = AgentBounds(
        max_turns=0, max_tool_calls=0, max_wall_seconds=60, max_budget_usd=0.0,
    )
    brief = f"nrl.com ladder (comp={competition} season={season} round={round})"
    record_agent_started(
        db,
        agent_id=AGENT_ID, agent_name=AGENT_NAME, run_id=run_id,
        model=MODEL, brief=brief,
        bounds={
            **{k: getattr(bounds, k) for k in ("max_turns", "max_tool_calls", "max_wall_seconds", "max_budget_usd")},
            "pipeline": PIPELINE,
            "competition": competition,
            "season": season,
            "round": round,
        },
    )

    detail: dict[str, Any] = {
        "pipeline": PIPELINE,
        "competition": competition,
        "season": season,
        "round": round,
    }

    try:
        data = fetch_ladder(competition=competition, season=season, round=round)
        positions = data.get("positions", [])
        round_for_path = round if round is not None else data.get("selectedRoundId", 0)
        archive_key = archive_response(
            source="nrlcom",
            pipeline="ladder",
            identity_path=f"{competition}/{season}/round-{int(round_for_path):02d}.json",
            payload=data,
        )
        detail.update({
            "teams": len(positions),
            "selected_round": round_for_path,
            "s3_archive_key": archive_key,
        })
        if archive_key is None:
            detail["s3_archive_failed"] = True
        logger.info("scout/nrlcom-ladder: comp=%s season=%s round=%s teams=%d",
                    competition, season, round_for_path, len(positions))
    except NrlcomLadderFetchError as e:
        detail["error"] = f"NrlcomLadderFetchError: {e}"
        record_agent_ended(
            db, run_id=run_id, status="failed",
            summary_text=f"Upstream fetch failed: {e}", model=MODEL, detail=detail,
        )
        raise HTTPException(status_code=502, detail=f"ladder fetch failed: {e}")
    except Exception as e:
        detail["error"] = f"{type(e).__name__}: {e}"
        record_agent_ended(
            db, run_id=run_id, status="failed",
            summary_text=f"Pipeline failed: {e}", model=MODEL, detail=detail,
        )
        raise

    record_agent_ended(
        db, run_id=run_id, status="completed",
        summary_text=f"nrl.com ladder: comp={competition} season={season} teams={len(positions)}",
        model=MODEL, detail=detail,
    )
    return {"run_id": run_id, "ok": True, **detail}


@router.post(
    "/admin/scout/nrlcom-ladder",
    dependencies=[Depends(require_admin)],
)
def nrlcom_ladder_endpoint(
    competition: int = Query(default=111),
    season: int = Query(...),
    round: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Fetch nrl.com /ladder/data and archive to S3."""
    return run_nrlcom_ladder(db, competition=competition, season=season, round=round)
