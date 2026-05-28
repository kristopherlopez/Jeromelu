"""Admin endpoint for seeding the ``teams`` table from a yaml-shaped JSON
payload. Mirrors the local-dev ``scripts/data/seed_teams.py`` flow but
runs server-side so prod can be populated without rsyncing files.

Body shape: the parsed contents of ``data/teams.yaml`` — a top-level
``teams`` map (NRL clubs + optional ``reserve_grade``) and an optional
``nrlw`` map. See :mod:`jeromelu_shared.teams.seed` for the full schema.

Idempotent: re-running with the same payload only bumps ``updated_at``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from jeromelu_shared.teams import seed_teams
from sqlalchemy.orm import Session

from ..deps import get_db
from .admin import require_admin

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/admin/teams/seed", dependencies=[Depends(require_admin)])
def seed_teams_endpoint(
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    if not isinstance(payload, dict) or "teams" not in payload:
        raise HTTPException(
            status_code=400,
            detail=(
                "Body must be a JSON object with a 'teams' map (and optional "
                "'nrlw' map). See data/teams.yaml for the canonical shape."
            ),
        )
    nrl_count = len(payload.get("teams") or {})
    nrlw_count = len(payload.get("nrlw") or {})
    logger.info(
        "admin/teams/seed: %d NRL clubs, %d NRLW clubs",
        nrl_count,
        nrlw_count,
    )
    counts = seed_teams(db, payload)
    return {"ok": True, "counts": counts}
