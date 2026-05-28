"""nrl.com players-roster admin endpoint — pure capture per team."""

from __future__ import annotations

import logging
import time
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
from .teams import NRL_TEAM_IDS

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "nrlcom-players-roster"


def run_nrlcom_players_roster(
    db: Session,
    *,
    competition: int,
    team: int,
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
        logger.info("scout/nrlcom-players-roster: comp=%s team=%s profiles=%d", competition, team, n_profiles)
    except NrlcomPlayersFetchError as e:
        run.fail(e, summary_text=f"Upstream fetch failed: {e}")
        raise HTTPException(status_code=502, detail=f"players-roster fetch failed: {e}") from e
    except ValidationError as e:
        run.fail(
            e,
            summary_text=f"Players-roster response failed strict validation (drift): {e}",
        )
        raise HTTPException(status_code=500, detail=f"nrl.com players-roster drift: {e}") from e
    except Exception as e:
        run.fail(e, summary_text=f"Pipeline failed: {e}")
        raise

    run.complete(summary_text=(f"nrl.com players-roster: comp={competition} team={team} profiles={n_profiles}"))
    return {"run_id": run.run_id, "ok": True, **detail}


@router.post(
    "/admin/scout/nrlcom-players-roster",
    dependencies=[Depends(require_admin)],
)
def nrlcom_players_roster_endpoint(
    competition: int = Query(default=111),
    team: int = Query(..., description="nrl.com team_id (e.g. Broncos=500011, Storm=500021)"),
    db: Session = Depends(get_db),
):
    """Fetch nrl.com /players/data for one team and archive to S3."""
    return run_nrlcom_players_roster(db, competition=competition, team=team)


def run_nrlcom_players_roster_refresh_all(
    db: Session,
    *,
    competition: int = 111,
    sleep_seconds: float = 1.0,
) -> dict[str, Any]:
    """Server-side walk of the 17 NRL teams' /players/data with polite 1 req/sec spacing.

    Opens an envelope ``agent_runs`` row under
    ``pipeline='nrlcom-players-roster-refresh-all'`` and iterates
    :data:`NRL_TEAM_IDS` sequentially, calling :func:`run_nrlcom_players_roster`
    per team. Per-team failures are **non-aborting** — a single-team error
    (upstream 502, drift 500, or any other exception) is captured under
    ``errors[]`` and the walk continues, mirroring the match-centre
    "fail one match, keep walking" precedent.

    Sleeps ``sleep_seconds`` between iterations (skipped after the last team)
    to stay polite per the per-origin rate-limit guidance.

    The envelope completes successfully when ``errors == []``; otherwise it
    is failed with a summary listing the offending team ids. **The HTTP
    response is always 200** — per-team detail (incl. errors) is in the
    response body, not the status code.
    """
    n_teams = len(NRL_TEAM_IDS)
    brief = f"nrl.com players-roster walk (comp={competition}, {n_teams} teams)"
    envelope = start_deterministic_run(
        db,
        pipeline="nrlcom-players-roster-refresh-all",
        brief=brief,
        detail={"competition": competition, "team_count": n_teams},
    )

    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for idx, (short, team_id) in enumerate(NRL_TEAM_IDS):
        try:
            per_team = run_nrlcom_players_roster(
                db,
                competition=competition,
                team=team_id,
            )
            # Per-team detail comes back as {run_id, ok, **detail}; project
            # only the fields the envelope cares about for the response body.
            results.append(
                {
                    "team_id": team_id,
                    "short": short,
                    "ok": True,
                    "profiles": per_team.get("profiles"),
                    "s3_archive_key": per_team.get("s3_archive_key"),
                    "validated": per_team.get("validated"),
                    "run_id": per_team.get("run_id"),
                }
            )
        except HTTPException as e:
            errors.append(
                {
                    "team_id": team_id,
                    "short": short,
                    "status_code": e.status_code,
                    "error": str(e.detail),
                }
            )
            logger.warning(
                "scout/nrlcom-players-roster-refresh-all: team=%s (%s) failed with HTTPException %s: %s",
                team_id,
                short,
                e.status_code,
                e.detail,
            )
        except Exception as e:
            errors.append(
                {
                    "team_id": team_id,
                    "short": short,
                    "error": f"{type(e).__name__}: {e}",
                }
            )
            logger.warning(
                "scout/nrlcom-players-roster-refresh-all: team=%s (%s) failed with %s: %s",
                team_id,
                short,
                type(e).__name__,
                e,
            )

        if idx < n_teams - 1:
            time.sleep(sleep_seconds)

    envelope.detail.update(
        {
            "teams_walked": n_teams,
            "ok_count": len(results),
            "error_count": len(errors),
        }
    )

    summary = f"nrl.com players-roster walk: comp={competition} ok={len(results)}/{n_teams}"
    if errors:
        bad_ids = ",".join(str(e["team_id"]) for e in errors)
        envelope.fail(
            RuntimeError(f"{len(errors)} per-team failure(s): team_ids=[{bad_ids}]"),
            summary_text=f"{summary} — {len(errors)} failed: {bad_ids}",
        )
    else:
        envelope.complete(summary_text=summary)

    return {
        "run_id": envelope.run_id,
        "ok": True,
        "competition": competition,
        "teams_walked": n_teams,
        "results": results,
        "errors": errors,
    }


@router.post(
    "/admin/scout/nrlcom-players-roster/refresh-all",
    dependencies=[Depends(require_admin)],
)
def nrlcom_players_roster_refresh_all_endpoint(
    competition: int = Query(default=111),
    db: Session = Depends(get_db),
):
    """Walk all 17 NRL teams via /players/data, polite 1 req/sec spacing.

    Non-aborting per-team: a single-team failure is captured in ``errors[]``
    and the walk continues. HTTP status is always 200; the response body
    carries the per-team detail.
    """
    return run_nrlcom_players_roster_refresh_all(db, competition=competition)
