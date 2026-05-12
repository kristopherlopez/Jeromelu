"""nrl.com casualty-ward admin endpoint — pure capture (S3 archive + audit)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
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
from .fetcher import NrlcomCasualtyFetchError, fetch_casualty_ward

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "nrlcom-casualty-ward"
AGENT_ID = "scout"
AGENT_NAME = "Scout"
MODEL = "deterministic"


def run_nrlcom_casualty_ward(
    db: Session,
    *,
    season: int | None = None,
    competition: int = 111,
) -> dict[str, Any]:
    """Fetch /casualty-ward/data + archive timestamped daily snapshot to S3."""
    run_id = make_run_id(AGENT_ID)
    bounds = AgentBounds(
        max_turns=0, max_tool_calls=0, max_wall_seconds=60, max_budget_usd=0.0,
    )
    brief = f"nrl.com casualty-ward (comp={competition} season={season})"
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
        "pipeline": PIPELINE,
        "competition": competition,
        "season": season,
    }

    try:
        data = fetch_casualty_ward(season=season, competition=competition)
        casualties = data.get("casualties", [])
        n = len(casualties)
        archive_key = archive_response(
            source="nrlcom",
            pipeline="casualty-ward",
            identity_path=f"{competition}/{datetime.now(timezone.utc).strftime('%Y%m%d')}.json",
            payload=data,
        )
        detail.update({"casualties": n, "s3_archive_key": archive_key})
        if archive_key is None:
            detail["s3_archive_failed"] = True
        logger.info("scout/nrlcom-casualty-ward: comp=%s casualties=%d s3=%s",
                    competition, n, archive_key)
    except NrlcomCasualtyFetchError as e:
        detail["error"] = f"NrlcomCasualtyFetchError: {e}"
        record_agent_ended(
            db, run_id=run_id, status="failed",
            summary_text=f"Upstream fetch failed: {e}", model=MODEL, detail=detail,
        )
        raise HTTPException(status_code=502, detail=f"casualty-ward fetch failed: {e}")
    except Exception as e:
        detail["error"] = f"{type(e).__name__}: {e}"
        record_agent_ended(
            db, run_id=run_id, status="failed",
            summary_text=f"Pipeline failed: {e}", model=MODEL, detail=detail,
        )
        raise

    record_agent_ended(
        db, run_id=run_id, status="completed",
        summary_text=f"nrl.com casualty-ward: comp={competition} casualties={n}",
        model=MODEL, detail=detail,
    )
    return {"run_id": run_id, "ok": True, **detail}


@router.post(
    "/admin/scout/nrlcom-casualty-ward",
    dependencies=[Depends(require_admin)],
)
def nrlcom_casualty_ward_endpoint(
    season: int | None = Query(default=None),
    competition: int = Query(default=111),
    db: Session = Depends(get_db),
):
    """Fetch nrl.com casualty-ward and archive a timestamped snapshot to S3."""
    return run_nrlcom_casualty_ward(db, season=season, competition=competition)
