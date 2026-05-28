"""nrl.com ladder admin endpoint — pure capture."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ...deps import get_db
from ...routers.admin import require_admin
from ..common.archive import archive_response
from ..common.pipeline_run import set_archive_detail, start_deterministic_run
from .fetcher import NrlcomLadderFetchError, fetch_ladder
from .models import NrlcomLadder

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "nrlcom-ladder"


def run_nrlcom_ladder(
    db: Session,
    *,
    competition: int,
    season: int,
    round: int | None = None,
    archive_only: bool = False,
) -> dict[str, Any]:
    """Fetch /ladder/data + archive to S3.

    `archive_only=True` skips D8 strict-parse — Phase 5 historical-backfill
    mode. See nrlcom_draw.routes for the pattern.
    """
    brief = f"nrl.com ladder (comp={competition} season={season} round={round})"
    run = start_deterministic_run(
        db,
        pipeline=PIPELINE,
        brief=brief,
        detail={"competition": competition, "season": season, "round": round},
    )
    detail = run.detail

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
        set_archive_detail(detail, archive_key)
        detail.update({
            "teams": len(positions),
            "selected_round": round_for_path,
        })
        # D8: strict-parse the archived response so upstream shape drift
        # surfaces as a failed run. The raw payload is already in S3 above,
        # so a validation failure never loses the capture. archive_only=True
        # skips the strict-parse entirely (Phase 5 historical backfill).
        if archive_only:
            detail["validated"] = False
            detail["validation_skipped"] = True
            logger.info(
                "scout/nrlcom-ladder: archive_only=true; strict-parse skipped "
                "(comp=%s season=%s round=%s teams=%d s3=%s)",
                competition, season, round_for_path, len(positions), archive_key,
            )
        else:
            NrlcomLadder.model_validate(data)
            detail["validated"] = True
            logger.info("scout/nrlcom-ladder: comp=%s season=%s round=%s teams=%d",
                        competition, season, round_for_path, len(positions))
    except NrlcomLadderFetchError as e:
        run.fail(e, summary_text=f"Upstream fetch failed: {e}")
        raise HTTPException(status_code=502, detail=f"ladder fetch failed: {e}")
    except ValidationError as e:
        run.fail(
            e,
            summary_text=f"Ladder response failed strict validation (drift): {e}",
        )
        raise HTTPException(status_code=500, detail=f"nrl.com ladder drift: {e}")
    except Exception as e:
        run.fail(e, summary_text=f"Pipeline failed: {e}")
        raise

    run.complete(
        summary_text=(
            f"nrl.com ladder: comp={competition} season={season} "
            f"teams={len(positions)}"
        )
    )
    return {"run_id": run.run_id, "ok": True, **detail}


@router.post(
    "/admin/scout/nrlcom-ladder",
    dependencies=[Depends(require_admin)],
)
def nrlcom_ladder_endpoint(
    competition: int = Query(default=111),
    season: int = Query(...),
    round: int | None = Query(default=None),
    archive_only: bool = Query(
        default=False,
        description="Phase 5 historical-backfill mode: skip D8 strict-parse. Daily cron leaves false.",
    ),
    db: Session = Depends(get_db),
):
    """Fetch nrl.com /ladder/data and archive to S3."""
    return run_nrlcom_ladder(
        db, competition=competition, season=season, round=round, archive_only=archive_only,
    )
