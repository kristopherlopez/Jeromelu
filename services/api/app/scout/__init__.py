"""Scout — Jaromelu's source-discovery agent.

Hunts the web for new NRL YouTube channels and videos worth onboarding.
Persists candidates to `scout_candidates` for human review.

Implementation: Anthropic Python SDK, manual multi-turn streaming loop,
built-in web_search + web_fetch + custom DB tools. No Temporal.

This module deliberately has no eager re-exports. `loop.run_scout`
imports the Anthropic SDK at module top, which would make any
``from app.scout import ...`` trigger that heavy import even for
callers that only want the lightweight refresh helpers. Import
submodules directly:

    from app.scout.loop import run_scout
    from app.scout.refresh import refresh_channel_videos
"""
