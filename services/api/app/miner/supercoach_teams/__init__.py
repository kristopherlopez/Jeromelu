"""Miner pipeline: SuperCoach team registry.

Fetches the 17-team list from supercoach.com.au/api/nrl/classic/v1/teams
and cross-references the SC IDs into teams.metadata_json.supercoach for
later joining (SC player records reference their team via this id).
"""

from .routes import router

__all__ = ["router"]
