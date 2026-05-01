"""Idempotent team-roster seeding from a yaml-shaped dict payload.

Mirrors the legacy local script ``scripts/data/seed_teams.py`` but as ORM
logic that can be called from either the script or the
``POST /api/admin/teams/seed`` admin endpoint, giving prod a path to
populate ``teams`` without rsyncing files.

Payload shape — exactly the parsed ``data/teams.yaml`` content::

    {
      "teams": {
        "<parent_slug>": {
          "name": "...",
          "short": "...",
          "aliases": [...],
          "reserve_grade": {            # optional
              "name": "...",
              "competition": "NSW Cup" | "QLD Cup"
          }
        },
        ...
      },
      "nrlw": {                          # optional
        "<parent_slug>": {
          "name": "...",
          "short": "...",
          "aliases": [...]
        },
        ...
      }
    }

Behaviour:
- NRL parents are upserted first (slug as primary key on conflict).
- Reserve-grade rows are upserted next, with ``parent_team_id`` resolved
  to the just-inserted NRL row by ``parent_slug``.
- NRLW rows similarly resolve ``parent_team_id`` to the NRL parent.
- Finally, any ``teams`` row in grade ``nrl``/``nrlw`` whose
  ``entity_id`` is NULL is opportunistically linked to a matching
  ``entities`` row by case-insensitive ``canonical_name``.

Idempotent: re-running with the same payload is a no-op except for
``updated_at`` bumps.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from jeromelu_shared.db.models import Team


# Display competition name → schema grade enum.
COMPETITION_TO_GRADE: dict[str, str] = {
    "NSW Cup": "nsw_cup",
    "QLD Cup": "qld_cup",
}


_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    return _SLUG_STRIP.sub("_", (name or "").lower()).strip("_")


def _build_rows(payload: dict[str, Any]) -> tuple[list[dict], list[dict], list[dict]]:
    """Return (nrl_rows, feeder_rows, nrlw_rows) ready for upsert."""
    nrl_rows: list[dict] = []
    feeder_rows: list[dict] = []
    nrlw_rows: list[dict] = []

    teams_payload = payload.get("teams") or {}
    for slug, team in teams_payload.items():
        nrl_rows.append({
            "slug": slug,
            "name": team["name"],
            "short_name": team.get("short"),
            "aliases": team.get("aliases") or [],
            "grade": "nrl",
            "competition": "NRL Premiership",
            "parent_slug": None,
        })

        rg = team.get("reserve_grade")
        if not rg:
            continue
        rg_name = rg["name"]
        rg_comp = rg["competition"]
        rg_grade = COMPETITION_TO_GRADE.get(rg_comp)
        if rg_grade is None:
            # Unknown competition (Jersey Flegg etc. allowed by schema but
            # not yet used by the yaml). Skip rather than fail the run.
            continue
        rg_slug_base = _slugify(rg_name)
        # Disambiguate feeders that reuse the parent's NRL slug
        # (e.g. Newcastle Knights' NSW Cup side keeps the same name).
        rg_slug = f"{rg_slug_base}_{rg_grade}" if rg_slug_base == slug else rg_slug_base
        feeder_rows.append({
            "slug": rg_slug,
            "name": rg_name,
            "short_name": None,
            "aliases": [],
            "grade": rg_grade,
            "competition": rg_comp,
            "parent_slug": slug,
        })

    nrlw_payload = payload.get("nrlw") or {}
    for parent_slug, team in nrlw_payload.items():
        nrlw_rows.append({
            "slug": f"{parent_slug}_nrlw",
            "name": team["name"],
            "short_name": team.get("short"),
            "aliases": team.get("aliases") or [],
            "grade": "nrlw",
            "competition": "NRLW Premiership",
            "parent_slug": parent_slug,
        })

    return nrl_rows, feeder_rows, nrlw_rows


def _upsert_batch(
    session: Session,
    rows: list[dict],
    slug_to_id: dict[str, Any],
) -> None:
    if not rows:
        return
    values = []
    for r in rows:
        values.append({
            "slug": r["slug"],
            "name": r["name"],
            "short_name": r["short_name"],
            "aliases": r["aliases"],
            "grade": r["grade"],
            "competition": r["competition"],
            "parent_team_id": (
                slug_to_id.get(r["parent_slug"]) if r["parent_slug"] else None
            ),
            "entity_id": None,
        })
    stmt = pg_insert(Team).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Team.slug],
        set_={
            "name": stmt.excluded.name,
            "short_name": stmt.excluded.short_name,
            "aliases": stmt.excluded.aliases,
            "grade": stmt.excluded.grade,
            "competition": stmt.excluded.competition,
            "parent_team_id": stmt.excluded.parent_team_id,
            # entity_id is preserved across upserts — never overwritten
            # to NULL once linked.
            "updated_at": func.now(),
        },
    )
    session.execute(stmt)


_LINK_ENTITY_SQL = text("""
    UPDATE teams t
       SET entity_id = e.entity_id,
           updated_at = now()
      FROM entities e
     WHERE e.entity_type = 'team'
       AND lower(e.canonical_name) = lower(t.name)
       AND t.entity_id IS NULL
       AND t.grade IN ('nrl', 'nrlw')
""")


def seed_teams(
    session: Session,
    payload: dict[str, Any],
) -> dict[str, int]:
    """Idempotently seed the ``teams`` table from a yaml-shaped dict.

    Returns counts of rows in each grade after the operation, plus the
    number of opportunistically-linked entity rows.
    """
    nrl_rows, feeder_rows, nrlw_rows = _build_rows(payload)

    # Phase 1 — NRL parents
    _upsert_batch(session, nrl_rows, slug_to_id={})
    session.flush()

    # Build slug -> team_id map for NRL rows
    nrl_slug_to_id: dict[str, Any] = {
        slug: tid
        for slug, tid in session.execute(
            select(Team.slug, Team.team_id).where(Team.grade == "nrl")
        ).all()
    }

    # Phase 2 + 3 — feeders + NRLW (both reference NRL parents)
    _upsert_batch(session, feeder_rows, slug_to_id=nrl_slug_to_id)
    _upsert_batch(session, nrlw_rows, slug_to_id=nrl_slug_to_id)
    session.flush()

    # Phase 4 — opportunistic entity linkage
    link_result = session.execute(_LINK_ENTITY_SQL)
    linked = link_result.rowcount or 0

    session.commit()

    counts: dict[str, int] = {}
    for grade, n in session.execute(
        select(Team.grade, func.count()).group_by(Team.grade)
    ).all():
        counts[grade] = int(n)
    counts["entities_linked_this_run"] = int(linked)
    return counts
