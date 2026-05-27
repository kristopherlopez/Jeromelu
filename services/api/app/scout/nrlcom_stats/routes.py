"""nrl.com stats admin endpoint — pure capture."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...deps import get_db
from ...routers.admin import require_admin
from ..common.archive import archive_response
from ..common.pipeline_run import set_archive_detail, start_deterministic_run
from .fetcher import NrlcomStatsFetchError, fetch_stats

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "nrlcom-stats"


def run_nrlcom_stats(
    db: Session, *, competition: int, season: int,
) -> dict[str, Any]:
    brief = f"nrl.com stats (comp={competition} season={season})"
    run = start_deterministic_run(
        db,
        pipeline=PIPELINE,
        brief=brief,
        detail={"competition": competition, "season": season},
    )
    detail = run.detail
    try:
        data = fetch_stats(competition=competition, season=season)
        archive_key = archive_response(
            source="nrlcom",
            pipeline="stats",
            identity_path=f"{competition}/{season}.json",
            payload=data,
        )
        set_archive_detail(detail, archive_key)
        detail.update({
            "player_stat_groups": len(data.get("playerStats", [])),
            "team_stat_groups": len(data.get("teamStats", [])),
        })
        logger.info("scout/nrlcom-stats: comp=%s season=%s s3=%s",
                    competition, season, archive_key)
    except NrlcomStatsFetchError as e:
        run.fail(e, summary_text=f"Upstream fetch failed: {e}")
        raise HTTPException(status_code=502, detail=f"stats fetch failed: {e}")
    except Exception as e:
        run.fail(e, summary_text=f"Pipeline failed: {e}")
        raise

    run.complete(
        summary_text=f"nrl.com stats: comp={competition} season={season}",
    )
    return {"run_id": run.run_id, "ok": True, **detail}


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
