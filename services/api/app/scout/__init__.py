"""Scout — Jaromelu's source-discovery agent.

Hunts the web for new NRL YouTube channels and videos worth onboarding.
Persists candidates to `scout_candidates` for human review.

Implementation: Anthropic Python SDK, manual multi-turn streaming loop,
built-in web_search + web_fetch + custom DB tools. No Temporal.
"""

from app.scout.loop import run_scout
from app.scout.prompt import SCOUT_SYSTEM_PROMPT, build_user_brief

__all__ = ["run_scout", "SCOUT_SYSTEM_PROMPT", "build_user_brief"]
