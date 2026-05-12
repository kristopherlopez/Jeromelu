"""Scout/SuperCoach teams admin endpoint with agent_audit + S3-first capture."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from jeromelu_shared.agent_audit import (
    AgentBounds,
    make_run_id,
    record_agent_ended,
    record_agent_started,
)
from jeromelu_shared.db.models import Team
from jeromelu_shared.players.roster import SC_ABBREV_TO_TEAM_SLUG

from ...deps import get_db
from ...routers.admin import require_admin
from .._s3_archive import archive_response
from .fetcher import SuperCoachTeamsFetchError, fetch_supercoach_teams
from .models import SuperCoachTeam

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "supercoach-teams"
AGENT_ID = "scout"
AGENT_NAME = "Scout"
MODEL = "deterministic"


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
    run_id = make_run_id(AGENT_ID)
    bounds = AgentBounds(
        max_turns=0,
        max_tool_calls=0,
        max_wall_seconds=60,
        max_budget_usd=0.0,
    )
    effective_season = season or date.today().year
    brief = f"SuperCoach teams refresh (season={effective_season})"
    record_agent_started(
        db,
        agent_id=AGENT_ID,
        agent_name=AGENT_NAME,
        run_id=run_id,
        model=MODEL,
        brief=brief,
        bounds={
            "max_turns": bounds.max_turns,
            "max_tool_calls": bounds.max_tool_calls,
            "max_wall_seconds": bounds.max_wall_seconds,
            "max_budget_usd": bounds.max_budget_usd,
            "pipeline": PIPELINE,
            "season": effective_season,
        },
    )

    detail: dict[str, Any] = {"pipeline": PIPELINE, "season": effective_season}
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
        detail["s3_archive_key"] = archive_key
        if archive_key is None:
            detail["s3_archive_failed"] = True

        # Strict-parse per D8.
        parsed = [SuperCoachTeam.model_validate(t) for t in raw_teams]
        logger.info(
            "scout/supercoach-teams: fetched %d teams (season=%s, run_id=%s)",
            fetched, effective_season, run_id,
        )
        upsert_result = _upsert_team_supercoach_ids(db, parsed)
        detail.update({"fetched": fetched, **upsert_result})
    except SuperCoachTeamsFetchError as e:
        detail["error"] = f"SuperCoachTeamsFetchError: {e}"
        record_agent_ended(
            db, run_id=run_id, status="failed",
            summary_text=f"Upstream fetch failed: {e}",
            model=MODEL, detail=detail,
        )
        raise HTTPException(status_code=502, detail=f"SC teams fetch failed: {e}")
    except Exception as e:
        detail["error"] = f"{type(e).__name__}: {e}"
        record_agent_ended(
            db, run_id=run_id, status="failed",
            summary_text=f"Pipeline failed: {e}",
            model=MODEL, detail=detail,
        )
        raise

    record_agent_ended(
        db, run_id=run_id, status="completed",
        summary_text=(
            f"SuperCoach teams refresh: fetched={fetched}, "
            f"matched={upsert_result.get('matched', 0)}"
        ),
        model=MODEL, detail=detail,
    )

    return {
        "run_id": run_id,
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
