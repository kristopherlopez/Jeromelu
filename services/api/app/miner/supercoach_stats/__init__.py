"""Miner pipeline: SuperCoach per-round stats acquisition.

Fetches per-round (or Totals) player stats from
nrlsupercoachstats.com's jqGrid endpoint and upserts into player_rounds.
The shape and column mapping live in jeromelu_shared.scraping.nrl
(JQGRID_COLUMN_MAP + extract_all_stats); this module wraps that with the
Miner pattern (folder layout per D9, agent_audit per D6, strict Pydantic
+ drift fixture per D8).

See README.md for source, cadence, natural key, and owner.
"""

from .routes import router

__all__ = ["router"]
