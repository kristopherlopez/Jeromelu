"""nrl.com players-roster admin endpoint — pure capture per team."""

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
from .fetcher import NrlcomPlayersFetchError, fetch_players_roster
from .models import NrlcomPlayersRoster

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "nrlcom-players-roster"


def run_nrlcom_players_roster(
    db: Session, *, competition: int, team: int,
) -> dict[str, Any]:
    brief = f"nrl.com players-roster (comp={competition} team={team})"
    run = start_deterministic_run(
        db,
        pipeline=PIPELINE,
        brief=brief,
        detail={"competition": competition, "team": team},
    )
    detail = run.detail

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
        set_archive_detail(detail, archive_key)
        detail["profiles"] = n_profiles
        # D8: strict-parse the archived response so upstream shape drift
        # surfaces as a failed run. The raw payload is already in S3 above,
        # so a validation failure never loses the capture.
        NrlcomPlayersRoster.model_validate(data)
        detail["validated"] = True
        logger.info("scout/nrlcom-players-roster: comp=%s team=%s profiles=%d",
                    competition, team, n_profiles)
    except NrlcomPlayersFetchError as e:
        run.fail(e, summary_text=f"Upstream fetch failed: {e}")
        raise HTTPException(status_code=502, detail=f"players-roster fetch failed: {e}")
    except ValidationError as e:
        run.fail(
            e,
            summary_text=f"Players-roster response failed strict validation (drift): {e}",
        )
        raise HTTPException(status_code=500, detail=f"nrl.com players-roster drift: {e}")
    except Exception as e:
        run.fail(e, summary_text=f"Pipeline failed: {e}")
        raise

    run.complete(
        summary_text=(
            f"nrl.com players-roster: comp={competition} team={team} "
            f"profiles={n_profiles}"
        )
    )
    return {"run_id": run.run_id, "ok": True, **detail}


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
