"""Scout/SuperCoach settings admin endpoint with agent_audit + S3-first capture + DB row."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...deps import get_db
from ...routers.admin import require_admin
from ..common.archive import archive_response
from ..common.pipeline_run import set_archive_detail, start_deterministic_run
from .fetcher import SuperCoachSettingsFetchError, fetch_supercoach_settings
from .models import SuperCoachSettings

logger = logging.getLogger(__name__)

router = APIRouter()


PIPELINE = "supercoach-settings"


def _upsert_sc_settings(
    db: Session, *, season: int, mode: str, payload: dict[str, Any], s3_key: str | None
) -> dict[str, Any]:
    """Insert one row per (season, captured_date, mode); same-day re-run = update."""
    stmt = text("""
        INSERT INTO sc_settings (season, mode, payload, s3_archive_key)
        VALUES (:season, :mode, CAST(:payload AS JSONB), :s3_key)
        ON CONFLICT (season, captured_date, mode)
        DO UPDATE SET
            captured_at = EXCLUDED.captured_at,
            payload = EXCLUDED.payload,
            s3_archive_key = COALESCE(EXCLUDED.s3_archive_key, sc_settings.s3_archive_key)
        RETURNING id
    """)
    import json

    result = db.execute(
        stmt,
        {"season": season, "mode": mode, "payload": json.dumps(payload), "s3_key": s3_key},
    )
    db.commit()
    row_id = result.scalar()
    return {"upserted_id": str(row_id)}


def run_supercoach_settings(
    db: Session,
    *,
    season: int | None = None,
    mode: str = "classic",
) -> dict[str, Any]:
    """Fetch SC settings + archive to S3 + upsert into sc_settings."""
    effective_season = season or date.today().year
    brief = f"SuperCoach settings snapshot (season={effective_season}, mode={mode})"
    run = start_deterministic_run(
        db,
        pipeline=PIPELINE,
        brief=brief,
        detail={
            "season": effective_season,
            "mode": mode,
        },
    )
    detail = run.detail
    upsert_result: dict[str, Any] = {}

    try:
        raw_settings = fetch_supercoach_settings(season=season, mode=mode)

        archive_key = archive_response(
            source="supercoach",
            pipeline=f"{mode}/settings",
            identity_path=(f"{effective_season}/{datetime.now(UTC).strftime('%Y%m%d')}.json"),
            payload=raw_settings,
        )
        set_archive_detail(detail, archive_key)

        # Strict-parse per D8 — validates the four top-level groups exist.
        SuperCoachSettings.model_validate(raw_settings)

        upsert_result = _upsert_sc_settings(
            db,
            season=effective_season,
            mode=mode,
            payload=raw_settings,
            s3_key=archive_key,
        )
        detail.update(upsert_result)
    except SuperCoachSettingsFetchError as e:
        run.fail(e, summary_text=f"Upstream fetch failed: {e}")
        raise HTTPException(status_code=502, detail=f"SC settings fetch failed: {e}") from e
    except Exception as e:
        run.fail(e, summary_text=f"Pipeline failed: {e}")
        raise

    run.complete(summary_text=(f"SuperCoach settings snapshot: season={effective_season} mode={mode}"))

    return {
        "run_id": run.run_id,
        "ok": True,
        "pipeline": PIPELINE,
        "season": effective_season,
        "mode": mode,
        **upsert_result,
    }


@router.post(
    "/admin/scout/supercoach-settings",
    dependencies=[Depends(require_admin)],
)
def supercoach_settings_endpoint(
    season: int | None = Query(default=None),
    mode: str = Query(default="classic", pattern="^(classic|draft)$"),
    db: Session = Depends(get_db),
):
    """Snapshot SC game settings for one (season, mode) into S3 + sc_settings."""
    return run_supercoach_settings(db, season=season, mode=mode)
