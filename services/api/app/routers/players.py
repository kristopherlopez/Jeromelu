"""Admin endpoints for player roster ingestion.

Three endpoints, all behind the same ``X-Admin-Key`` admin auth:

- ``POST /admin/players/seed`` — first-run idempotent seed from a SC
  roster JSON body. Existing current ``people_attributes`` rows are left
  alone.
- ``POST /admin/players/refresh`` — diff a SC roster JSON body vs current
  rows; transition team / primary-position changes via SCD-2 (close
  current + open new), add rows for never-before-seen players.
- ``POST /admin/players/fetch-and-refresh`` — server-side equivalent of
  ``/refresh``: the API container fetches the roster from SC directly,
  validates it, then runs the same diff. No payload required, so it's
  cron-friendly: a single ``curl -X POST`` from the Lightsail box runs
  the weekly Tuesday refresh end-to-end.

The first two endpoints exist for local-dev parity (push a JSON the
operator scraped). The fetch-and-refresh endpoint is the
production-grade path — preferred for cron and routine ops because it
removes the "ship a JSON file from one machine to another" step.

All three are pure transforms over the shared
:mod:`jeromelu_shared.players.roster` (and :mod:`.supercoach`) module.
Logic stays there so the local-dev seed script can call it directly.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from jeromelu_shared.players.nrlcom_refresh import refresh_from_nrlcom
from jeromelu_shared.players.roster import (
    RosterPreconditionError,
    refresh_roster,
    seed_roster,
)
from jeromelu_shared.players.supercoach import (
    SuperCoachFetchError,
    fetch_supercoach_roster,
)

from ..deps import get_db
from .admin import require_admin

logger = logging.getLogger(__name__)

router = APIRouter()


def _coerce_roster(payload: Any) -> list[dict[str, Any]]:
    """Accept either a bare JSON array or {'players': [...]} envelope."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("players"), list):
        return payload["players"]
    raise HTTPException(
        status_code=400,
        detail=(
            "Body must be a JSON array of SC players, or an object with a "
            "'players' list."
        ),
    )


@router.post("/admin/players/seed", dependencies=[Depends(require_admin)])
def seed_players(
    payload: Any = Body(...),
    source: str = "supercoach",
    db: Session = Depends(get_db),
):
    """First-run idempotent seed from a SC roster payload."""
    sc_players = _coerce_roster(payload)
    logger.info("admin/players/seed: %d players from source=%s", len(sc_players), source)
    try:
        result = seed_roster(db, sc_players, source=source)
    except RosterPreconditionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True, **result}


@router.post("/admin/players/refresh", dependencies=[Depends(require_admin)])
def refresh_players(
    payload: Any = Body(...),
    source: str = "supercoach",
    db: Session = Depends(get_db),
):
    """Diff-and-transition refresh from a fresh SC roster payload."""
    sc_players = _coerce_roster(payload)
    logger.info("admin/players/refresh: %d players from source=%s", len(sc_players), source)
    try:
        result = refresh_roster(db, sc_players, source=source)
    except RosterPreconditionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True, **result}


@router.post(
    "/admin/players/fetch-and-refresh",
    dependencies=[Depends(require_admin)],
)
def fetch_and_refresh_players(
    season: int | None = Query(default=None, description="SC season year (defaults to current year)"),
    source: str = Query(default="supercoach"),
    db: Session = Depends(get_db),
):
    """Fetch the SC roster server-side, then run the standard SCD-2 refresh.

    Cron-friendly weekly entry point: no payload, just an admin key.
    The API container itself does the outbound GET to supercoach.com.au's
    unauthenticated ``players-cf`` endpoint, validates the response covers
    all 17 NRL clubs and ≥400 players, and pipes the result through the
    same ``refresh_roster`` used by ``/admin/players/refresh``.
    """
    try:
        sc_players = fetch_supercoach_roster(season=season)
    except SuperCoachFetchError as e:
        # 502: upstream looked wrong. Don't run the diff against a bad payload.
        raise HTTPException(status_code=502, detail=f"SC fetch failed: {e}")

    logger.info(
        "admin/players/fetch-and-refresh: fetched %d players (season=%s, source=%s)",
        len(sc_players), season, source,
    )
    try:
        result = refresh_roster(db, sc_players, source=source)
    except RosterPreconditionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True, "fetched": len(sc_players), **result}


@router.post(
    "/admin/players/refresh-nrlcom",
    dependencies=[Depends(require_admin)],
)
def refresh_players_nrlcom(
    team: str | None = Query(default=None, description="Optional Team.short_name filter (e.g. 'Broncos')"),
    rate_limit_ms: int = Query(default=0, ge=0, le=2000, description="Sleep between profile fetches"),
    db: Session = Depends(get_db),
):
    """Enrich every current player row from nrl.com profile pages.

    Walks ``people`` rows that have a current ``people_attributes`` row,
    fetches each one's nrl.com profile, parses the embedded JSON-LD, and
    promotes:

    - ``people.dob``           — set if currently null
    - ``people.image_url``     — always update
    - ``people.metadata_json.birthplace_text`` — set if currently empty
    - ``people_attributes.height_cm / weight_kg`` — in-place update on diff

    404s are logged + flagged on ``people.metadata_json.nrlcom`` (with
    ``last_status: "404"`` and ``tried_url``) and returned in the
    response ``mismatches`` list. Per-person overrides on the same JSON
    block (``slug``, ``team_short``, ``skip``) handle apostrophes /
    accents / recently-traded players.

    Sequential fetches (~550 by default). Expect ~2–3 minutes for a full
    run; pass ``?team=Broncos`` for a one-club test.
    """
    team_filter = [team] if team else None
    rate_limit = (rate_limit_ms / 1000) if rate_limit_ms else 0.0
    result = refresh_from_nrlcom(
        db,
        team_filter=team_filter,
        rate_limit_sleep=rate_limit,
    )
    return {"ok": True, **result}
