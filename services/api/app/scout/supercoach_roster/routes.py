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
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from jeromelu_shared.agent_audit import (
    AgentBounds,
    make_run_id,
    record_agent_ended,
    record_agent_started,
)
from jeromelu_shared.players.roster import (
    RosterPreconditionError,
    refresh_roster,
)
from jeromelu_shared.players.supercoach import (
    SuperCoachFetchError,
    fetch_supercoach_roster,
)

from ...deps import get_db
from ...routers.admin import require_admin
from .._s3_archive import archive_response
from .models import SuperCoachPlayer
from .notes_extractor import extract_notes_as_claims

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "supercoach-roster"
AGENT_ID = "scout"
AGENT_NAME = "Scout"
# Deterministic pipeline — no LLM. agent_audit still requires a model field;
# the pricing fallback in estimate_token_cost ensures cost = $0.00 since
# no tokens are reported.
MODEL = "deterministic"


def _record_failure(
    db: Session,
    *,
    run_id: str,
    exc: Exception,
    detail: dict[str, Any],
    fetched: int,
    summary_text: str,
) -> None:
    """Stamp a failure on the agent_runs row.

    Caller is responsible for raising the appropriate HTTPException (or
    re-raising) after this returns.
    """
    detail["error"] = f"{type(exc).__name__}: {exc}"
    detail["fetched"] = fetched
    record_agent_ended(
        db, run_id=run_id, status="failed", summary_text=summary_text,
        model=MODEL, detail=detail,
    )


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
    run_id = make_run_id(AGENT_ID)
    bounds = AgentBounds(
        max_turns=0,
        max_tool_calls=0,
        max_wall_seconds=120,
        max_budget_usd=0.0,
    )
    brief = (
        f"SuperCoach roster fetch + SCD-2 refresh (season={season or 'current'}, "
        f"source={source})"
    )
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
        },
    )

    detail: dict[str, Any] = {"pipeline": PIPELINE, "mode": "fetch-and-refresh"}
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
            identity_path=(
                f"{effective_season}/"
                f"{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
            ),
            payload=raw_players,
        )
        detail["s3_archive_key"] = archive_key
        if archive_key is None:
            detail["s3_archive_failed"] = True

        # Strict-parse per D8 (any drift here raises ValidationError).
        players = [SuperCoachPlayer.model_validate(p) for p in raw_players]
        # refresh_roster expects list[dict]; model_dump gets us back to the
        # plain dict shape the SCD-2 logic was written against.
        sc_players_dicts = [p.model_dump() for p in players]
        logger.info(
            "scout/supercoach-roster: fetched %d players (season=%s, source=%s, run_id=%s, s3=%s)",
            fetched, season, source, run_id, archive_key,
        )
        refresh_result = refresh_roster(db, sc_players_dicts, source=source)
        detail.update({"fetched": fetched, **refresh_result})

        # Extract SC editorial notes[] as claims attributed to the synthetic
        # SuperCoach Editorial advisor (per migration 061). Idempotent —
        # re-runs only insert new notes.
        notes_result = extract_notes_as_claims(db, sc_players=raw_players)
        detail.update(notes_result)
    except SuperCoachFetchError as e:
        _record_failure(
            db, run_id=run_id, exc=e, detail=detail,
            fetched=fetched, summary_text=f"Upstream fetch failed: {e}",
        )
        # 502: upstream looked wrong; don't run the diff against a bad payload.
        raise HTTPException(status_code=502, detail=f"SC fetch failed: {e}")
    except RosterPreconditionError as e:
        _record_failure(
            db, run_id=run_id, exc=e, detail=detail,
            fetched=fetched, summary_text=f"Roster precondition failed: {e}",
        )
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        _record_failure(
            db, run_id=run_id, exc=e, detail=detail,
            fetched=fetched, summary_text=f"Pipeline failed: {e}",
        )
        raise

    record_agent_ended(
        db, run_id=run_id, status="completed",
        summary_text=f"SuperCoach roster refresh: fetched={fetched}",
        model=MODEL, detail=detail,
    )

    return {
        "run_id": run_id,
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
