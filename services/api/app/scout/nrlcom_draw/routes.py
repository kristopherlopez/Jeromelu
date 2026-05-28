"""nrl.com draw admin endpoint — pure capture (S3 archive + audit row)."""

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
from .fetcher import NrlcomDrawFetchError, fetch_draw
from .models import NrlcomDraw

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "nrlcom-draw"


def run_nrlcom_draw(
    db: Session,
    *,
    competition: int,
    season: int,
    round: int | None = None,
    archive_only: bool = False,
) -> dict[str, Any]:
    """Fetch /draw/data + archive to S3.

    `archive_only=True` skips D8 strict-parse entirely — used by the Phase 5
    historical backfill where era-specific shape variance is expected and the
    strict model would 500. The S3 capture still happens (it runs before the
    parse). Response carries `validated:false, validation_skipped:true`. The
    daily-cron path leaves `archive_only` at its default False — drift on the
    modern shape still surfaces as 500.
    """
    brief = f"nrl.com draw fetch (comp={competition} season={season} round={round})"
    run = start_deterministic_run(
        db,
        pipeline=PIPELINE,
        brief=brief,
        detail={"competition": competition, "season": season, "round": round},
    )
    detail = run.detail

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
        set_archive_detail(detail, archive_key)
        detail.update({
            "fixtures": n_fixtures,
            "selected_round": round_for_path,
        })
        # D8: strict-parse the archived response so upstream shape drift
        # surfaces as a failed run. The raw payload is already in S3 above,
        # so a validation failure never loses the capture. In archive_only
        # mode (Phase 5 historical backfill) the strict-parse is skipped
        # entirely — capture is preserved unconditionally.
        if archive_only:
            detail["validated"] = False
            detail["validation_skipped"] = True
            logger.info(
                "scout/nrlcom-draw: archive_only=true; strict-parse skipped "
                "(comp=%s season=%s round=%s fixtures=%d s3=%s)",
                competition, season, round_for_path, n_fixtures, archive_key,
            )
        else:
            NrlcomDraw.model_validate(data)
            detail["validated"] = True
            logger.info(
                "scout/nrlcom-draw: comp=%s season=%s round=%s fixtures=%d s3=%s",
                competition, season, round_for_path, n_fixtures, archive_key,
            )
    except NrlcomDrawFetchError as e:
        run.fail(e, summary_text=f"Upstream fetch failed: {e}")
        raise HTTPException(status_code=502, detail=f"nrl.com draw fetch failed: {e}")
    except ValidationError as e:
        run.fail(
            e,
            summary_text=f"Draw response failed strict validation (drift): {e}",
        )
        raise HTTPException(status_code=500, detail=f"nrl.com draw drift: {e}")
    except Exception as e:
        run.fail(e, summary_text=f"Pipeline failed: {e}")
        raise

    run.complete(
        summary_text=(
            f"nrl.com draw: comp={competition} season={season} "
            f"round={detail.get('selected_round')} fixtures={n_fixtures}"
        )
    )
    return {"run_id": run.run_id, "ok": True, **detail}


@router.post(
    "/admin/scout/nrlcom-draw",
    dependencies=[Depends(require_admin)],
)
def nrlcom_draw_endpoint(
    competition: int = Query(default=111, description="NRL=111, NRLW=etc."),
    season: int = Query(..., description="Season year (1908..present)"),
    round: int | None = Query(default=None, description="Optional round number (omit for current)"),
    archive_only: bool = Query(
        default=False,
        description="Phase 5 historical-backfill mode: skip D8 strict-parse. Daily cron leaves false.",
    ),
    db: Session = Depends(get_db),
):
    """Fetch nrl.com /draw/data and archive to S3."""
    return run_nrlcom_draw(
        db, competition=competition, season=season, round=round, archive_only=archive_only,
    )
