"""Admin endpoints for player roster ingestion.

Both endpoints take the SuperCoach roster JSON as the request body — the
same array shape that ``scripts/data/scraped_players_api_raw.json`` holds
locally. The Makefile target (``make prod-seed-players``) curls the file
directly at this endpoint with the ``X-Admin-Key`` header.

- ``POST /admin/players/seed``   — first-run idempotent seed. Existing
  current ``player_attributes`` rows are left alone.
- ``POST /admin/players/refresh`` — diff vs current rows; transition team
  / primary-position changes via SCD-2 (close current + open new), add
  rows for never-before-seen players.

Both endpoints are pure transforms over the shared
:mod:`jeromelu_shared.players.roster` module. Logic stays there so the
local-dev seed script can call it directly.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from jeromelu_shared.players.roster import (
    RosterPreconditionError,
    refresh_roster,
    seed_roster,
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
