"""Scout pipeline: SuperCoach player roster acquisition.

Fetches the NRL player registry from supercoach.com.au's unauthenticated
players-cf endpoint and applies the SCD-2 refresh in
jeromelu_shared.players.roster. Writes people / player_attributes /
people_roles.

Folder layout follows D9 of the Scout charter expansion: each pipeline
gets its own folder under services/api/app/scout/<pipeline_name>/.

See README.md for source, cadence, natural key, and owner.
"""

from .routes import router

__all__ = ["router"]
