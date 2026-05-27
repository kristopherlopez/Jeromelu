"""Scout — Jaromelu's acquisition boundary.

Scout owns raw external acquisition: agentic YouTube discovery,
deterministic feed snapshots, YouTube refresh jobs, and media collection.
Pipeline packages under this module expose admin endpoints and record
`agent_runs` rows with `agent_id='scout'` plus a pipeline discriminator.

This package deliberately has no eager re-exports. Source Discovery and
Presenter Research import the Anthropic SDK at module top,
which would make any ``from app.scout import ...`` trigger that heavier
import even for callers that only want lightweight deterministic helpers.
Import submodules directly:

    from app.scout.source_discovery.agent import run_source_discovery
    from app.scout.presenter_research.agent import run_presenter_research
    from app.scout.youtube.refresh import refresh_channel_videos
    from app.scout.routes import router as scout_router
"""
