"""nrl.com match-centre admin endpoint — pure capture per match (S3 archive + audit)."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from jeromelu_shared.agent_audit import (
    AgentBounds,
    make_run_id,
    record_agent_ended,
    record_agent_started,
)

from ...deps import get_db
from ...routers.admin import require_admin
from .._s3_archive import archive_response
from ..nrlcom_draw.fetcher import fetch_draw, NrlcomDrawFetchError
from .fetcher import (
    NrlcomMatchCentreFetchError,
    extract_slug_from_match_centre_url,
    fetch_match_centre,
)

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "nrlcom-match-centre"
AGENT_ID = "scout"
AGENT_NAME = "Scout"
MODEL = "deterministic"
RATE_LIMIT_SECONDS = 1.0  # polite — nrl.com isn't infinite


def run_nrlcom_match_centre(
    db: Session,
    *,
    competition: int,
    season: int,
    round: int,
) -> dict[str, Any]:
    """Walk the draw → fetch each match-centre → archive each to S3."""
    run_id = make_run_id(AGENT_ID)
    bounds = AgentBounds(
        max_turns=0, max_tool_calls=0,
        max_wall_seconds=600,  # ~8 matches × 5s each + rate-limit padding
        max_budget_usd=0.0,
    )
    brief = (
        f"nrl.com match-centre walk (comp={competition} season={season} round={round})"
    )
    record_agent_started(
        db,
        agent_id=AGENT_ID, agent_name=AGENT_NAME, run_id=run_id,
        model=MODEL, brief=brief,
        bounds={
            **{k: getattr(bounds, k) for k in ("max_turns", "max_tool_calls", "max_wall_seconds", "max_budget_usd")},
            "pipeline": PIPELINE,
            "competition": competition,
            "season": season,
            "round": round,
        },
    )

    detail: dict[str, Any] = {
        "pipeline": PIPELINE,
        "competition": competition,
        "season": season,
        "round": round,
    }
    matches_archived = 0
    fetch_failures: list[dict[str, Any]] = []
    archive_failures: list[str] = []
    archive_keys: list[str] = []

    try:
        # 1. Discover fixtures for the round
        draw = fetch_draw(competition=competition, season=season, round=round)
        fixtures = draw.get("fixtures", [])
        detail["fixtures_in_round"] = len(fixtures)

        # 2. Fetch each match centre + archive
        for f in fixtures:
            mc_url = f.get("matchCentreUrl")
            if not mc_url:
                continue
            slug = extract_slug_from_match_centre_url(mc_url)
            try:
                match_data = fetch_match_centre(mc_url)
            except (NrlcomMatchCentreFetchError, httpx.HTTPError) as e:
                logger.warning("match-centre fetch failed for %s: %s", slug, e)
                fetch_failures.append({"slug": slug, "error": str(e)})
                continue

            key = archive_response(
                source="nrlcom",
                pipeline="match-centre",
                identity_path=f"{competition}/{season}/round-{round:02d}/{slug}.json",
                payload=match_data,
            )
            if key is None:
                archive_failures.append(slug)
            else:
                archive_keys.append(key)
                matches_archived += 1

            time.sleep(RATE_LIMIT_SECONDS)

        detail.update({
            "matches_archived": matches_archived,
            "fetch_failures": fetch_failures,
            "archive_failures": archive_failures,
            "archive_keys": archive_keys[:5] + (["..."] if len(archive_keys) > 5 else []),
        })
        logger.info(
            "scout/nrlcom-match-centre: comp=%s season=%s round=%s — archived %d/%d",
            competition, season, round, matches_archived, len(fixtures),
        )
    except NrlcomDrawFetchError as e:
        detail["error"] = f"NrlcomDrawFetchError: {e}"
        record_agent_ended(
            db, run_id=run_id, status="failed",
            summary_text=f"Could not discover fixtures: {e}",
            model=MODEL, detail=detail,
        )
        raise HTTPException(status_code=502, detail=f"draw fetch failed: {e}")
    except Exception as e:
        detail["error"] = f"{type(e).__name__}: {e}"
        record_agent_ended(
            db, run_id=run_id, status="failed",
            summary_text=f"Pipeline failed: {e}", model=MODEL, detail=detail,
        )
        raise

    record_agent_ended(
        db, run_id=run_id, status="completed",
        summary_text=(
            f"nrl.com match-centre: comp={competition} season={season} round={round} "
            f"archived={matches_archived} fetch_failures={len(fetch_failures)} "
            f"archive_failures={len(archive_failures)}"
        ),
        model=MODEL, detail=detail,
    )
    return {"run_id": run_id, "ok": True, **detail}


@router.post(
    "/admin/scout/nrlcom-match-centre",
    dependencies=[Depends(require_admin)],
)
def nrlcom_match_centre_endpoint(
    competition: int = Query(default=111, description="NRL=111"),
    season: int = Query(..., description="Season year"),
    round: int = Query(..., description="Round number"),
    db: Session = Depends(get_db),
):
    """Walk draw → fetch each match-centre → archive each to S3."""
    return run_nrlcom_match_centre(db, competition=competition, season=season, round=round)
