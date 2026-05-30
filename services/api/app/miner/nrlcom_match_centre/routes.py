"""nrl.com match-centre admin endpoint — pure capture per match (S3 archive + audit)."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ...deps import get_db
from ...routers.admin import require_admin
from ..common.archive import archive_response
from ..common.pipeline_run import start_deterministic_run
from ..nrlcom_draw.fetcher import NrlcomDrawFetchError, fetch_draw
from .fetcher import (
    NrlcomMatchCentreFetchError,
    extract_slug_from_match_centre_url,
    fetch_match_centre,
)
from .models import NrlcomMatchCentre

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "nrlcom-match-centre"
RATE_LIMIT_SECONDS = 1.0  # polite — nrl.com isn't infinite


def run_nrlcom_match_centre(
    db: Session,
    *,
    competition: int,
    season: int,
    round: int | None = None,
    archive_only: bool = False,
) -> dict[str, Any]:
    """Walk the draw → fetch each match-centre → archive each to S3.

    `archive_only=True` skips the per-match D8 strict-parse — Phase 5
    historical-backfill mode. The S3 archive per match still happens
    (capture is preserved). Response carries `validated:false,
    validation_skipped:true` at the envelope level; `validation_failures`
    stays empty (no per-match strict-parse ran).
    """
    brief = f"nrl.com match-centre walk (comp={competition} season={season} round={round})"
    run = start_deterministic_run(
        db,
        pipeline=PIPELINE,
        brief=brief,
        detail={"competition": competition, "season": season, "round": round},
        max_wall_seconds=600,
    )
    detail = run.detail
    matches_archived = 0
    fetch_failures: list[dict[str, Any]] = []
    archive_failures: list[str] = []
    archive_keys: list[str] = []
    validation_failures: list[dict[str, Any]] = []

    try:
        # 1. Discover fixtures for the round (round=None → current round).
        draw = fetch_draw(competition=competition, season=season, round=round)
        if round is None:
            round = draw.get("selectedRoundId")
            if round is None:
                raise HTTPException(
                    status_code=502,
                    detail="could not resolve current round from draw",
                )
            detail["resolved_round"] = round
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

            # D8: strict-parse the envelope (raw already archived above). Drift on
            # a single match is logged but does NOT abort the round walk — one bad
            # match shouldn't lose the rest of the round's capture. archive_only=True
            # skips the per-match strict-parse entirely (Phase 5 historical backfill).
            if not archive_only:
                try:
                    NrlcomMatchCentre.model_validate(match_data)
                except ValidationError as e:
                    validation_failures.append({"slug": slug, "error": str(e)[:300]})

            time.sleep(RATE_LIMIT_SECONDS)

        if archive_only:
            detail["validated"] = False
            detail["validation_skipped"] = True
        detail.update(
            {
                "matches_archived": matches_archived,
                "fetch_failures": fetch_failures,
                "archive_failures": archive_failures,
                "validation_failures": validation_failures,
                "archive_keys": archive_keys[:5] + (["..."] if len(archive_keys) > 5 else []),
            }
        )
        logger.info(
            "miner/nrlcom-match-centre: comp=%s season=%s round=%s archive_only=%s — archived %d/%d",
            competition,
            season,
            round,
            archive_only,
            matches_archived,
            len(fixtures),
        )
    except NrlcomDrawFetchError as e:
        run.fail(e, summary_text=f"Could not discover fixtures: {e}")
        raise HTTPException(status_code=502, detail=f"draw fetch failed: {e}") from e
    except Exception as e:
        run.fail(e, summary_text=f"Pipeline failed: {e}")
        raise

    run.complete(
        summary_text=(
            f"nrl.com match-centre: comp={competition} season={season} round={round} "
            f"archived={matches_archived} fetch_failures={len(fetch_failures)} "
            f"archive_failures={len(archive_failures)} "
            f"validation_failures={len(validation_failures)}"
        ),
    )
    return {"run_id": run.run_id, "ok": True, **detail}


@router.post(
    "/admin/miner/nrlcom-match-centre",
    dependencies=[Depends(require_admin)],
)
def nrlcom_match_centre_endpoint(
    competition: int = Query(default=111, description="NRL=111"),
    season: int = Query(..., description="Season year"),
    round: int | None = Query(default=None, description="Round number (omit for current round)"),
    archive_only: bool = Query(
        default=False,
        description="Phase 5 historical-backfill mode: skip per-match D8 strict-parse. Daily cron leaves false.",
    ),
    db: Session = Depends(get_db),
):
    """Walk draw → fetch each match-centre → archive each to S3.

    `round` omitted → resolves the current round from the draw's `selectedRoundId`.
    """
    return run_nrlcom_match_centre(
        db,
        competition=competition,
        season=season,
        round=round,
        archive_only=archive_only,
    )
