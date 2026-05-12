"""nrl.com players-roster admin endpoint — pure capture per team."""

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
from .fetcher import NrlcomPlayersFetchError, fetch_players_roster

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "nrlcom-players-roster"
AGENT_ID = "scout"
AGENT_NAME = "Scout"
MODEL = "deterministic"


def run_nrlcom_players_roster(
    db: Session, *, competition: int, team: int,
) -> dict[str, Any]:
    run_id = make_run_id(AGENT_ID)
    bounds = AgentBounds(
        max_turns=0, max_tool_calls=0, max_wall_seconds=60, max_budget_usd=0.0,
    )
    brief = f"nrl.com players-roster (comp={competition} team={team})"
    record_agent_started(
        db,
        agent_id=AGENT_ID, agent_name=AGENT_NAME, run_id=run_id,
        model=MODEL, brief=brief,
        bounds={
            **{k: getattr(bounds, k) for k in ("max_turns", "max_tool_calls", "max_wall_seconds", "max_budget_usd")},
            "pipeline": PIPELINE,
            "competition": competition,
            "team": team,
        },
    )

    detail: dict[str, Any] = {
        "pipeline": PIPELINE, "competition": competition, "team": team,
    }

    try:
        data = fetch_players_roster(competition=competition, team=team)
        profile_groups = data.get("profileGroups", [])
        n_profiles = sum(len(g.get("profiles", [])) for g in profile_groups)
        archive_key = archive_response(
            source="nrlcom",
            pipeline="players-roster",
            identity_path=f"{competition}/team-{team}.json",
            payload=data,
        )
        detail.update({
            "profiles": n_profiles,
            "s3_archive_key": archive_key,
        })
        if archive_key is None:
            detail["s3_archive_failed"] = True
        logger.info("scout/nrlcom-players-roster: comp=%s team=%s profiles=%d",
                    competition, team, n_profiles)
    except NrlcomPlayersFetchError as e:
        detail["error"] = f"NrlcomPlayersFetchError: {e}"
        record_agent_ended(
            db, run_id=run_id, status="failed",
            summary_text=f"Upstream fetch failed: {e}", model=MODEL, detail=detail,
        )
        raise HTTPException(status_code=502, detail=f"players-roster fetch failed: {e}")
    except Exception as e:
        detail["error"] = f"{type(e).__name__}: {e}"
        record_agent_ended(
            db, run_id=run_id, status="failed",
            summary_text=f"Pipeline failed: {e}", model=MODEL, detail=detail,
        )
        raise

    record_agent_ended(
        db, run_id=run_id, status="completed",
        summary_text=f"nrl.com players-roster: comp={competition} team={team} profiles={n_profiles}",
        model=MODEL, detail=detail,
    )
    return {"run_id": run_id, "ok": True, **detail}


@router.post(
    "/admin/scout/nrlcom-players-roster",
    dependencies=[Depends(require_admin)],
)
def nrlcom_players_roster_endpoint(
    competition: int = Query(default=111),
    team: int = Query(..., description="nrl.com team_id (e.g. Storm=500011)"),
    db: Session = Depends(get_db),
):
    """Fetch nrl.com /players/data for one team and archive to S3."""
    return run_nrlcom_players_roster(db, competition=competition, team=team)
