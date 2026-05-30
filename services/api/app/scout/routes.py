"""Aggregate router for Scout admin acquisition pipelines."""

from __future__ import annotations

from fastapi import APIRouter

from .dashboard import router as dashboard_router
from .nrlcom_casualty_ward import router as nrlcom_casualty_ward_router
from .nrlcom_draw import router as nrlcom_draw_router
from .nrlcom_ladder import router as nrlcom_ladder_router
from .nrlcom_match_centre import router as nrlcom_match_centre_router
from .nrlcom_players_roster import router as nrlcom_players_roster_router
from .nrlcom_stats import router as nrlcom_stats_router
from .source_discovery.routes import router as source_discovery_router
from .supercoach_roster import router as supercoach_roster_router
from .supercoach_settings import router as supercoach_settings_router
from .supercoach_stats import router as supercoach_stats_router
from .supercoach_teams import router as supercoach_teams_router

router = APIRouter()

for pipeline_router in (
    dashboard_router,
    supercoach_roster_router,
    supercoach_settings_router,
    supercoach_stats_router,
    supercoach_teams_router,
    nrlcom_draw_router,
    nrlcom_match_centre_router,
    nrlcom_casualty_ward_router,
    nrlcom_ladder_router,
    nrlcom_stats_router,
    nrlcom_players_roster_router,
    source_discovery_router,
):
    router.include_router(pipeline_router)

__all__ = ["router"]
