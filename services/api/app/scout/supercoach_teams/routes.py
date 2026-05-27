"""Scout/SuperCoach teams admin endpoint with agent_audit + S3-first capture."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from jeromelu_shared.db.models import Team
from jeromelu_shared.players.roster import SC_ABBREV_TO_TEAM_SLUG

from ...deps import get_db
from ...routers.admin import require_admin
from ..common.archive import archive_response
from ..common.pipeline_run import set_archive_detail, start_deterministic_run
from .fetcher import SuperCoachTeamsFetchError, fetch_supercoach_teams
from .models import SuperCoachTeam

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "supercoach-teams"


def _upsert_team_supercoach_ids(
    db: Session, sc_teams: list[SuperCoachTeam]
) -> dict[str, Any]:
    """Patch teams.metadata_json.supercoach for each matching team.

    Returns counts: matched (linked), unknown_abbrev (SC abbrev not in our
    mapping), missing_team_row (mapping present but no teams row by slug).
    """
    matched = 0
    unknown_abbrev = []
    missing_team_row = []

    for sc_team in sc_teams:
        slug = SC_ABBREV_TO_TEAM_SLUG.get(sc_team.abbrev)
        if not slug:
            unknown_abbrev.append(sc_team.abbrev)
            continue
        team_row = db.execute(
            select(Team).where(Team.slug == slug)
        ).scalar_one_or_none()
        if team_row is None:
            missing_team_row.append(slug)
            continue
        meta = dict(team_row.metadata_json or {})
        meta["supercoach"] = {
            "id": sc_team.id,
            "abbrev": sc_team.abbrev,
            "feed_name": sc_team.feed_name,
            "name": sc_team.name,
            "competition": sc_team.competition.model_dump(),
        }
        team_row.metadata_json = meta
        matched += 1

    db.commit()
    return {
        "matched": matched,
        "unknown_abbrev": unknown_abbrev,
        "missing_team_row": missing_team_row,
    }


def run_supercoach_teams(
    db: Session,
    *,
    season: int | None = None,
) -> dict[str, Any]:
    """Fetch SC teams + archive to S3 + cross-reference into teams.metadata_json."""
    effective_season = season or date.today().year
    brief = f"SuperCoach teams refresh (season={effective_season})"
    run = start_deterministic_run(
        db,
        pipeline=PIPELINE,
        brief=brief,
        detail={"season": effective_season},
    )
    detail = run.detail
    upsert_result: dict[str, Any] = {}
    fetched = 0

    try:
        raw_teams = fetch_supercoach_teams(season=season)
        fetched = len(raw_teams)

        archive_key = archive_response(
            source="supercoach",
            pipeline="classic/teams",
            identity_path=f"{effective_season}.json",
            payload=raw_teams,
        )
        set_archive_detail(detail, archive_key)

        # Strict-parse per D8.
        parsed = [SuperCoachTeam.model_validate(t) for t in raw_teams]
        logger.info(
            "scout/supercoach-teams: fetched %d teams (season=%s, run_id=%s)",
            fetched, effective_season, run.run_id,
        )
        upsert_result = _upsert_team_supercoach_ids(db, parsed)
        detail.update({"fetched": fetched, **upsert_result})
    except SuperCoachTeamsFetchError as e:
        run.fail(e, summary_text=f"Upstream fetch failed: {e}")
        raise HTTPException(status_code=502, detail=f"SC teams fetch failed: {e}")
    except Exception as e:
        run.fail(e, summary_text=f"Pipeline failed: {e}")
        raise

    run.complete(
        summary_text=(
            f"SuperCoach teams refresh: fetched={fetched}, "
            f"matched={upsert_result.get('matched', 0)}"
        ),
    )

    return {
        "run_id": run.run_id,
        "ok": True,
        "pipeline": PIPELINE,
        "season": effective_season,
        "fetched": fetched,
        **upsert_result,
    }


@router.post(
    "/admin/scout/supercoach-teams",
    dependencies=[Depends(require_admin)],
)
def supercoach_teams_endpoint(
    season: int | None = Query(
        default=None,
        description="SC season year (defaults to current year)",
    ),
    db: Session = Depends(get_db),
):
    """Acquire SuperCoach team registry and cross-reference SC IDs into teams.metadata_json."""
    return run_supercoach_teams(db, season=season)
