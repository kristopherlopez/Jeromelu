"""Admin routes for source-discovery entry points."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...deps import get_db
from ...routers.admin import require_admin
from ..common.pipeline_run import start_deterministic_run
from ..youtube.client import YouTubeAPIError
from .deterministic_youtube import DEFAULT_MIN_SCORE, run_deterministic_youtube_discovery

router = APIRouter()

PIPELINE = "youtube-discovery"


@router.post(
    "/admin/miner/source-discovery/youtube",
    dependencies=[Depends(require_admin)],
)
def deterministic_youtube_discovery_endpoint(
    channel_query: list[str] | None = Query(
        default=None,
        description="Override default channel-search queries. Repeat for multiple queries.",
    ),
    video_query: list[str] | None = Query(
        default=None,
        description="Override default video-search queries. Repeat for multiple queries.",
    ),
    harvest_query: list[str] | None = Query(
        default=None,
        description="Override default video-harvest queries. Repeat for multiple queries.",
    ),
    related_channel_id: list[str] | None = Query(
        default=None,
        description="Also inspect featured channels for this known YouTube channel ID. Repeatable.",
    ),
    no_channel_search: bool = Query(default=False),
    no_video_search: bool = Query(default=False),
    no_harvest_search: bool = Query(default=False),
    max_results: int = Query(default=10, ge=1, le=200),
    max_videos: int = Query(default=25, ge=1, le=200),
    published_after: str | None = Query(default=None, description="RFC 3339 timestamp for video searches."),
    min_score: float = Query(default=DEFAULT_MIN_SCORE, ge=0.0, le=1.0),
    dry_run: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Cron-friendly deterministic YouTube discovery.

    This endpoint runs inside the API container, uses the YouTube Data API
    helpers directly, dedupes against server-side DB state, and writes novel
    candidates to ``miner_candidates``. It does not schedule itself; cron can
    call this route later with the same X-Admin-Key pattern as other Miner
    deterministic endpoints.
    """

    channel_queries = [] if no_channel_search else channel_query
    video_queries = [] if no_video_search else video_query
    harvest_queries = [] if no_harvest_search else harvest_query
    detail = {
        "dry_run": dry_run,
        "max_results": max_results,
        "max_videos": max_videos,
        "published_after": published_after,
        "min_score": min_score,
    }
    run = start_deterministic_run(
        db,
        pipeline=PIPELINE,
        brief="Deterministic YouTube source discovery",
        detail=detail,
        max_wall_seconds=300,
    )
    try:
        result = run_deterministic_youtube_discovery(
            db,
            run_id=run.run_id,
            channel_queries=channel_queries,
            video_queries=video_queries,
            harvest_queries=harvest_queries,
            related_channel_ids=related_channel_id,
            max_results_per_query=max_results,
            max_videos_per_query=max_videos,
            published_after=published_after,
            min_score=min_score,
            dry_run=dry_run,
        )
    except YouTubeAPIError as e:
        run.fail(e, summary_text=f"YouTube discovery failed: {e}")
        raise HTTPException(status_code=502, detail=f"YouTube discovery failed: {e}") from e
    except Exception as e:
        run.fail(e, summary_text=f"Deterministic YouTube discovery failed: {e}")
        raise

    result_payload = result.to_dict()
    run.detail.update(result_payload)
    run.complete(
        summary_text=(
            "Deterministic YouTube discovery: "
            f"selected={result.candidates_selected}, inserted={result.candidates_inserted}, "
            f"duplicates={result.duplicates_skipped}, dry_run={dry_run}"
        )
    )
    return {"ok": True, "pipeline": PIPELINE, **result_payload}
