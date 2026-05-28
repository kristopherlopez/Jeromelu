"""nrl.com casualty-ward admin endpoint — pure capture (S3 archive + audit)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ...deps import get_db
from ...routers.admin import require_admin
from ..common.archive import archive_response
from ..common.pipeline_run import set_archive_detail, start_deterministic_run
from .fetcher import NrlcomCasualtyFetchError, fetch_casualty_ward
from .models import NrlcomCasualtyWard

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "nrlcom-casualty-ward"


def run_nrlcom_casualty_ward(
    db: Session,
    *,
    season: int | None = None,
    competition: int = 111,
) -> dict[str, Any]:
    """Fetch /casualty-ward/data + archive timestamped daily snapshot to S3."""
    brief = f"nrl.com casualty-ward (comp={competition} season={season})"
    run = start_deterministic_run(
        db,
        pipeline=PIPELINE,
        brief=brief,
        detail={"competition": competition, "season": season},
    )
    detail = run.detail

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
        set_archive_detail(detail, archive_key)
        detail["casualties"] = n
        # D8: strict-parse the archived response so upstream shape drift
        # surfaces as a failed run. The raw payload is already in S3 above,
        # so a validation failure never loses the capture.
        NrlcomCasualtyWard.model_validate(data)
        detail["validated"] = True
        logger.info("scout/nrlcom-casualty-ward: comp=%s casualties=%d s3=%s",
                    competition, n, archive_key)
    except NrlcomCasualtyFetchError as e:
        run.fail(e, summary_text=f"Upstream fetch failed: {e}")
        raise HTTPException(status_code=502, detail=f"casualty-ward fetch failed: {e}")
    except ValidationError as e:
        run.fail(
            e,
            summary_text=f"Casualty-ward response failed strict validation (drift): {e}",
        )
        raise HTTPException(status_code=500, detail=f"nrl.com casualty-ward drift: {e}")
    except Exception as e:
        run.fail(e, summary_text=f"Pipeline failed: {e}")
        raise

    run.complete(
        summary_text=f"nrl.com casualty-ward: comp={competition} casualties={n}",
    )
    return {"run_id": run.run_id, "ok": True, **detail}


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
