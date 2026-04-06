"""Entity resolution — find or create Entity records by name."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from jeromelu_shared.db import Entity
from jeromelu_shared.scraping.nrl import TEAM_CODE_MAP, normalize_name


# Reverse map: canonical team name -> canonical team name (identity, for lookup)
_TEAM_NAMES = {v.lower(): v for v in set(TEAM_CODE_MAP.values())}
# Also map codes themselves
_TEAM_NAMES.update({k.lower(): v for k, v in TEAM_CODE_MAP.items()})


def resolve_entity(session: Session, name: str, entity_type: str) -> Entity:
    """Find an existing Entity or create a new one.

    For players: normalizes name and checks canonical_name (case-insensitive) + aliases.
    For teams: also checks TEAM_CODE_MAP.
    """
    normalized = normalize_name(name).strip()

    # Try exact match on canonical_name (case-insensitive)
    entity = session.query(Entity).filter(
        Entity.entity_type == entity_type,
        func.lower(Entity.canonical_name) == normalized.lower(),
    ).first()
    if entity:
        return entity

    # Try alias match
    entity = session.query(Entity).filter(
        Entity.entity_type == entity_type,
        Entity.aliases.any(normalized),
    ).first()
    if entity:
        return entity

    # For teams, try the team code/name map
    if entity_type == "team":
        canonical_team = _TEAM_NAMES.get(normalized.lower())
        if canonical_team:
            entity = session.query(Entity).filter(
                Entity.entity_type == "team",
                func.lower(Entity.canonical_name) == canonical_team.lower(),
            ).first()
            if entity:
                return entity
            # Create with canonical team name
            normalized = canonical_team

    # Create new entity
    entity = Entity(
        entity_type=entity_type,
        canonical_name=normalized,
        aliases=[],
    )
    session.add(entity)
    session.flush()
    return entity
