"""Scout/SuperCoach roster admin endpoint with the standard agent_audit wrapper.

POST /api/admin/scout/supercoach-roster
  - Fetches the SC roster server-side (strict-parsed per D8).
  - Runs the SCD-2 refresh from jeromelu_shared.players.roster.
  - Writes an agent_runs row under agent_id='scout', detail_json.pipeline='supercoach-roster'.
  - Returns {run_id, ok, fetched, ...refresh counts}.

The actual fetch/persist logic is shared with the legacy
/api/admin/players/fetch-and-refresh route (which becomes a deprecated alias).
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from jeromelu_shared.players.roster import (
    RosterPreconditionError,
    refresh_roster,
)
from jeromelu_shared.players.supercoach import (
    SuperCoachFetchError,
    fetch_supercoach_roster,
)
from sqlalchemy.orm import Session

from ...deps import get_db
from ...routers.admin import require_admin
from ..common.archive import archive_response
from ..common.pipeline_run import set_archive_detail, start_deterministic_run
from .models import SuperCoachPlayer
from .notes_extractor import extract_notes_as_claims

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "supercoach-roster"


def run_supercoach_roster(
    db: Session,
    *,
    season: int | None = None,
    source: str = "supercoach",
) -> dict[str, Any]:
    """Fetch + strict-parse + SCD-2 refresh, wrapped in the agent_audit pattern.

    Returns the run summary including run_id, ok flag, fetched count, and
    the refresh_roster counts (players_seen, transitions, etc.).
    """
    brief = f"SuperCoach roster fetch + SCD-2 refresh (season={season or 'current'}, source={source})"
    run = start_deterministic_run(
        db,
        pipeline=PIPELINE,
        brief=brief,
        detail={"mode": "fetch-and-refresh"},
        max_wall_seconds=120,
    )
    detail = run.detail
    refresh_result: dict[str, Any] = {}
    fetched = 0
    effective_season = season or date.today().year

    try:
        # Fetch raw, archive to S3 (D10), then strict-parse.
        raw_players = fetch_supercoach_roster(season=season)
        fetched = len(raw_players)

        archive_key = archive_response(
            source="supercoach",
            pipeline="classic/players-cf",
            identity_path=(f"{effective_season}/{datetime.now(UTC).strftime('%Y%m%d')}.json"),
            payload=raw_players,
        )
        set_archive_detail(detail, archive_key)

        # Strict-parse per D8 (any drift here raises ValidationError).
        players = [SuperCoachPlayer.model_validate(p) for p in raw_players]
        # refresh_roster expects list[dict]; model_dump gets us back to the
        # plain dict shape the SCD-2 logic was written against.
        sc_players_dicts = [p.model_dump() for p in players]
        logger.info(
            "scout/supercoach-roster: fetched %d players (season=%s, source=%s, run_id=%s, s3=%s)",
            fetched,
            season,
            source,
            run.run_id,
            archive_key,
        )
        refresh_result = refresh_roster(db, sc_players_dicts, source=source)
        detail.update({"fetched": fetched, **refresh_result})

        # Extract SC editorial notes[] as claims attributed to the synthetic
        # SuperCoach Editorial advisor (per migration 061). Idempotent —
        # re-runs only insert new notes.
        notes_result = extract_notes_as_claims(db, sc_players=raw_players)
        detail.update(notes_result)
    except SuperCoachFetchError as e:
        detail["fetched"] = fetched
        run.fail(e, summary_text=f"Upstream fetch failed: {e}")
        # 502: upstream looked wrong; don't run the diff against a bad payload.
        raise HTTPException(status_code=502, detail=f"SC fetch failed: {e}") from e
    except RosterPreconditionError as e:
        detail["fetched"] = fetched
        run.fail(e, summary_text=f"Roster precondition failed: {e}")
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        detail["fetched"] = fetched
        run.fail(e, summary_text=f"Pipeline failed: {e}")
        raise

    run.complete(
        summary_text=f"SuperCoach roster refresh: fetched={fetched}",
    )

    return {
        "run_id": run.run_id,
        "ok": True,
        "pipeline": PIPELINE,
        "fetched": fetched,
        **refresh_result,
    }


@router.post(
    "/admin/scout/supercoach-roster",
    dependencies=[Depends(require_admin)],
)
def supercoach_roster_endpoint(
    season: int | None = Query(
        default=None,
        description="SC season year (defaults to current year)",
    ),
    source: str = Query(default="supercoach"),
    db: Session = Depends(get_db),
):
    """Acquire the SuperCoach roster and apply the SCD-2 refresh.

    Cron-friendly: no payload, single admin key. The API container fetches
    the roster directly from supercoach.com.au's unauthenticated
    players-cf endpoint, validates it via strict Pydantic models (D8),
    and pipes the result through `refresh_roster`. One `agent_runs` row
    per call under `agent_id='scout'`, `detail_json.pipeline='supercoach-roster'`.
    """
    return run_supercoach_roster(db, season=season, source=source)
