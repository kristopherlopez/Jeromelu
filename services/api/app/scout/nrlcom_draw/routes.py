"""nrl.com draw admin endpoint — pure capture (S3 archive + audit row)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
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
from .fetcher import NrlcomDrawFetchError, fetch_draw
from .models import NrlcomDraw

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "nrlcom-draw"
AGENT_ID = "scout"
AGENT_NAME = "Scout"
MODEL = "deterministic"


def run_nrlcom_draw(
    db: Session,
    *,
    competition: int,
    season: int,
    round: int | None = None,
) -> dict[str, Any]:
    """Fetch /draw/data + archive to S3."""
    run_id = make_run_id(AGENT_ID)
    bounds = AgentBounds(
        max_turns=0, max_tool_calls=0, max_wall_seconds=60, max_budget_usd=0.0,
    )
    brief = f"nrl.com draw fetch (comp={competition} season={season} round={round})"
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
        data = fetch_draw(competition=competition, season=season, round=round)
        fixtures = data.get("fixtures", [])
        n_fixtures = len(fixtures)
        round_for_path = round if round is not None else data.get("selectedRoundId", 0)
        archive_key = archive_response(
            source="nrlcom",
            pipeline="draw",
            identity_path=f"{competition}/{season}/round-{int(round_for_path):02d}.json",
            payload=data,
        )
        detail.update({
            "fixtures": n_fixtures,
            "s3_archive_key": archive_key,
            "selected_round": round_for_path,
        })
        if archive_key is None:
            detail["s3_archive_failed"] = True
        # D8: strict-parse the archived response so upstream shape drift
        # surfaces as a failed run. The raw payload is already in S3 above,
        # so a validation failure never loses the capture.
        NrlcomDraw.model_validate(data)
        detail["validated"] = True
        logger.info(
            "scout/nrlcom-draw: comp=%s season=%s round=%s fixtures=%d s3=%s",
            competition, season, round_for_path, n_fixtures, archive_key,
        )
    except NrlcomDrawFetchError as e:
        detail["error"] = f"NrlcomDrawFetchError: {e}"
        record_agent_ended(
            db, run_id=run_id, status="failed",
            summary_text=f"Upstream fetch failed: {e}", model=MODEL, detail=detail,
        )
        raise HTTPException(status_code=502, detail=f"nrl.com draw fetch failed: {e}")
    except ValidationError as e:
        detail["error"] = f"ValidationError: {e}"
        record_agent_ended(
            db, run_id=run_id, status="failed",
            summary_text=f"Draw response failed strict validation (drift): {e}",
            model=MODEL, detail=detail,
        )
        raise HTTPException(status_code=500, detail=f"nrl.com draw drift: {e}")
    except Exception as e:
        detail["error"] = f"{type(e).__name__}: {e}"
        record_agent_ended(
            db, run_id=run_id, status="failed",
            summary_text=f"Pipeline failed: {e}", model=MODEL, detail=detail,
        )
        raise

    record_agent_ended(
        db, run_id=run_id, status="completed",
        summary_text=f"nrl.com draw: comp={competition} season={season} round={detail.get('selected_round')} fixtures={n_fixtures}",
        model=MODEL, detail=detail,
    )
    return {"run_id": run_id, "ok": True, **detail}


@router.post(
    "/admin/scout/nrlcom-draw",
    dependencies=[Depends(require_admin)],
)
def nrlcom_draw_endpoint(
    competition: int = Query(default=111, description="NRL=111, NRLW=etc."),
    season: int = Query(..., description="Season year (1908..present)"),
    round: int | None = Query(default=None, description="Optional round number (omit for current)"),
    db: Session = Depends(get_db),
):
    """Fetch nrl.com /draw/data and archive to S3."""
    return run_nrlcom_draw(db, competition=competition, season=season, round=round)
