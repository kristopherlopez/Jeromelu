"""Miner pipeline: SuperCoach game-settings snapshot.

Captures the SC game rules per season (lockouts, scoring config, captains,
emergencies, dual-position rules, currency, content templates) as a JSONB
snapshot. The payload is stored whole — querying individual fields is rare
and the schema is too deep to flatten usefully.
"""

from .routes import router

__all__ = ["router"]
