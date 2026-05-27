"""Scout — Jaromelu's acquisition boundary.

Scout owns raw external acquisition: agentic YouTube discovery,
deterministic feed snapshots, YouTube refresh jobs, and media collection.
Pipeline packages under this module expose admin endpoints and record
`agent_runs` rows with `agent_id='scout'` plus a pipeline discriminator.

This package deliberately has no eager re-exports. `loop.run_scout` and
`presenters.run_presenter_scout` import the Anthropic SDK at module top,
which would make any ``from app.scout import ...`` trigger that heavier
import even for callers that only want lightweight deterministic helpers.
Import submodules directly:

    from app.scout.loop import run_scout
    from app.scout.refresh import refresh_channel_videos
    from app.scout.routes import router as scout_router
"""
