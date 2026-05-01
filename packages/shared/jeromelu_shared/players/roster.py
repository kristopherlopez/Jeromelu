"""Player roster ingestion — idempotent seed + SCD-2 diff/refresh.

Single source of truth for transforming SuperCoach roster JSON (the array
returned by ``players-cf`` and saved to ``scraped_players_api_raw.json``)
into ``entities`` + ``player_attributes`` rows. The ``teams`` table is
assumed to be pre-seeded by ``scripts/data/seed_teams.py``
(``make seed-teams``); this module looks up Team rows by slug.

Used by:
- ``scripts/data/seed_players_prod.py`` — local-dev direct-DB seed
- ``/api/admin/players/seed`` and ``/refresh`` — prod ingestion (the same
  JSON payload is POSTed by the Makefile target).

Seed path is first-run idempotent: existing player_attributes rows are
left alone. Refresh path closes the current row and opens a new one
whenever team or primary position changes — the SCD-2 transition pattern
documented in ``docs/concepts/entity-roles.md``.

Lifetime constants (dob, debut date) live on ``entities.metadata_json``.
Per-round facts (price, breakeven, score, jersey, grade) live on
``player_rounds``. This module owns the slow-changing-but-not-constant
slice in between.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from jeromelu_shared.db.models import (
    Person,
    PersonAttributes,
    PersonRole,
    Team,
)


# ---------------------------------------------------------------------------
# SuperCoach abbrev → ``teams.slug`` for the parent NRL clubs. Slugs match
# the underscore convention in ``data/teams.yaml`` so seed_teams.py is the
# single canonical writer.
# ---------------------------------------------------------------------------
SC_ABBREV_TO_TEAM_SLUG: dict[str, str] = {
    "BRO": "brisbane_broncos",
    "BUL": "canterbury_bulldogs",
    "CBR": "canberra_raiders",
    "SHA": "cronulla_sharks",
    "DOL": "dolphins",
    "GCT": "gold_coast_titans",
    "MNL": "manly_sea_eagles",
    "MEL": "melbourne_storm",
    "NEW": "newcastle_knights",
    "NQC": "north_queensland_cowboys",
    "PAR": "parramatta_eels",
    "PTH": "penrith_panthers",
    "STH": "south_sydney_rabbitohs",
    "STG": "st_george_illawarra_dragons",
    "SYD": "sydney_roosters",
    "NZL": "new_zealand_warriors",
    "WST": "wests_tigers",
}


_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    base = _SLUG_STRIP.sub("-", (name or "").lower()).strip("-")
    return base or "entity"


# ---------------------------------------------------------------------------
# Team lookup — teams must already be seeded by scripts/data/seed_teams.py
# ---------------------------------------------------------------------------

class RosterPreconditionError(RuntimeError):
    """Raised when a precondition (e.g. teams seeded) is not met."""


def load_nrl_teams_by_abbrev(session: Session) -> dict[str, Team]:
    """Look up the 17 NRL Team rows by slug, keyed by SC abbrev.

    Raises if any are missing — populating ``teams`` is the responsibility
    of ``scripts/data/seed_teams.py`` (``make seed-teams``).
    """
    slugs = list(SC_ABBREV_TO_TEAM_SLUG.values())
    rows = session.execute(select(Team).where(Team.slug.in_(slugs))).scalars().all()
    by_slug = {team.slug: team for team in rows}

    missing = [slug for slug in slugs if slug not in by_slug]
    if missing:
        raise RosterPreconditionError(
            "teams not seeded yet — missing slugs: "
            + ", ".join(sorted(missing))
            + ". Run `make seed-teams` first."
        )
    return {abbrev: by_slug[slug] for abbrev, slug in SC_ABBREV_TO_TEAM_SLUG.items()}


# ---------------------------------------------------------------------------
# Entity & role ensure helpers
# ---------------------------------------------------------------------------

def _player_canonical_name(sc_player: dict[str, Any]) -> str:
    return f"{sc_player.get('first_name', '').strip()} {sc_player.get('last_name', '').strip()}".strip()


def _ensure_player_entity(session: Session, sc_player: dict[str, Any]) -> Person:
    name = _player_canonical_name(sc_player)
    sc_id = sc_player.get("id")

    person = None
    if sc_id is not None:
        person = session.execute(
            select(Person).where(Person.supercoach_id == sc_id)
        ).scalar_one_or_none()
    if person is None:
        person = session.execute(
            select(Person).where(Person.canonical_name == name)
        ).scalar_one_or_none()

    if person is None:
        person = Person(
            canonical_name=name,
            slug=_slugify(name),
            aliases=[],
            supercoach_id=sc_id,
            metadata_json={},
        )
        session.add(person)
        session.flush()
    elif sc_id and person.supercoach_id != sc_id:
        person.supercoach_id = sc_id

    return person


def _ensure_player_role(
    session: Session,
    entity: Person,
    source: str,
    effective_from: date,
) -> None:
    existing = session.execute(
        select(PersonRole).where(
            PersonRole.person_id == entity.person_id,
            PersonRole.role == "player",
            PersonRole.effective_to.is_(None),
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            PersonRole(
                person_id=entity.person_id,
                role="player",
                effective_from=effective_from,
                is_primary=True,
                source=source,
            )
        )


def _primary_and_secondary_positions(sc_player: dict[str, Any]) -> tuple[str | None, list[str]]:
    positions = sc_player.get("positions") or []
    sorted_positions = sorted(positions, key=lambda p: p.get("sort", 99))
    names = [p.get("position") for p in sorted_positions if p.get("position")]
    if not names:
        return None, []
    return names[0], names[1:]


# ---------------------------------------------------------------------------
# Public: seed (first-run) and refresh (diff-and-transition)
# ---------------------------------------------------------------------------

def seed_roster(
    session: Session,
    sc_players: list[dict[str, Any]],
    source: str = "supercoach",
    effective_from: date | None = None,
) -> dict[str, Any]:
    """First-run idempotent seed. Existing current player_attributes rows
    are left untouched. Use ``refresh_roster`` for diff-based updates."""
    effective_from = effective_from or date(date.today().year, 1, 1)
    teams_by_abbrev = load_nrl_teams_by_abbrev(session)

    counts = {
        "players_seen": 0,
        "entities_created": 0,
        "attributes_inserted": 0,
        "attributes_noop": 0,
        "skipped_unknown_team": 0,
    }

    for sc_player in sc_players:
        counts["players_seen"] += 1
        team_obj = sc_player.get("team") or {}
        abbrev = team_obj.get("abbrev")
        if abbrev not in teams_by_abbrev:
            counts["skipped_unknown_team"] += 1
            continue
        team = teams_by_abbrev[abbrev]

        existing_pid = session.execute(
            select(Person.person_id).where(
                Person.canonical_name == _player_canonical_name(sc_player),
            )
        ).scalar_one_or_none()
        entity = _ensure_player_entity(session, sc_player)
        if existing_pid is None:
            counts["entities_created"] += 1

        _ensure_player_role(session, entity, source=source, effective_from=effective_from)

        existing_attrs = session.execute(
            select(PersonAttributes).where(
                PersonAttributes.person_id == entity.person_id,
                PersonAttributes.is_current.is_(True),
            )
        ).scalar_one_or_none()
        if existing_attrs is not None:
            counts["attributes_noop"] += 1
            continue

        primary, secondary = _primary_and_secondary_positions(sc_player)
        session.add(
            PersonAttributes(
                person_id=entity.person_id,
                team_id=team.team_id,
                primary_position=primary,
                metadata_json={"secondary_positions": secondary},
                effective_from=effective_from,
                is_current=True,
                source=source,
            )
        )
        counts["attributes_inserted"] += 1

    session.commit()
    return counts


def refresh_roster(
    session: Session,
    sc_players: list[dict[str, Any]],
    source: str = "supercoach",
    today: date | None = None,
) -> dict[str, Any]:
    """Diff a fresh roster against current player_attributes rows and apply
    SCD-2 transitions. Returns counts plus a transition list suitable for
    serialising into the API response or emitting feed events."""
    today = today or date.today()
    teams_by_abbrev = load_nrl_teams_by_abbrev(session)

    counts = {
        "players_seen": 0,
        "new_players": 0,
        "team_changes": 0,
        "position_changes": 0,
        "unchanged": 0,
        "skipped_unknown_team": 0,
    }
    transitions: list[dict[str, Any]] = []

    for sc_player in sc_players:
        counts["players_seen"] += 1
        team_obj = sc_player.get("team") or {}
        abbrev = team_obj.get("abbrev")
        if abbrev not in teams_by_abbrev:
            counts["skipped_unknown_team"] += 1
            continue
        team = teams_by_abbrev[abbrev]
        primary, secondary = _primary_and_secondary_positions(sc_player)

        entity = _ensure_player_entity(session, sc_player)
        _ensure_player_role(session, entity, source=source, effective_from=today)

        current = session.execute(
            select(PersonAttributes).where(
                PersonAttributes.person_id == entity.person_id,
                PersonAttributes.is_current.is_(True),
            )
        ).scalar_one_or_none()

        if current is None:
            session.add(
                PersonAttributes(
                    person_id=entity.person_id,
                    team_id=team.team_id,
                    primary_position=primary,
                    metadata_json={"secondary_positions": secondary},
                    effective_from=today,
                    is_current=True,
                    source=source,
                )
            )
            counts["new_players"] += 1
            transitions.append({
                "kind": "new_player",
                "entity_id": str(entity.person_id),
                "name": entity.canonical_name,
                "team_slug": team.slug,
            })
            continue

        team_changed = current.team_id != team.team_id
        position_changed = (current.primary_position or None) != (primary or None)

        if not team_changed and not position_changed:
            counts["unchanged"] += 1
            continue

        prior_team_slug = None
        if current.team_id:
            prior_team = session.get(Team, current.team_id)
            prior_team_slug = prior_team.slug if prior_team else None
        prior_position = current.primary_position

        # SCD-2 transition: close current, open new.
        current.effective_to = today
        current.is_current = False

        session.add(
            PersonAttributes(
                person_id=entity.person_id,
                team_id=team.team_id,
                primary_position=primary,
                metadata_json={"secondary_positions": secondary},
                effective_from=today,
                is_current=True,
                source=source,
            )
        )

        if team_changed:
            counts["team_changes"] += 1
            transitions.append({
                "kind": "team_change",
                "entity_id": str(entity.person_id),
                "name": entity.canonical_name,
                "from_team_slug": prior_team_slug,
                "to_team_slug": team.slug,
            })
        if position_changed:
            counts["position_changes"] += 1
            transitions.append({
                "kind": "position_change",
                "entity_id": str(entity.person_id),
                "name": entity.canonical_name,
                "from_position": prior_position,
                "to_position": primary,
            })

    session.commit()
    return {"counts": counts, "transitions": transitions}
