"""Seed `teams` from data/teams.yaml.

Covers NRL + reserve grades (NSW Cup, QLD Cup) + NRLW. Junior grades
(Jersey Flegg, Mal Meninga, SG Ball, Cyril Connell, Harold Matthews) are
allowed by the schema but not seeded here — populate via a follow-up
script when current-season comp lineups are confirmed.

Idempotent: ON CONFLICT (slug) upserts. Two-phase to resolve
parent_team_id within the same run (NRL parents first, then feeders +
NRLW children that reference them).
"""

import os
import re
import sys
from pathlib import Path
from typing import Iterable

import psycopg2
import yaml
from psycopg2.extras import execute_values

YAML_PATH = Path(__file__).resolve().parents[2] / "data" / "teams.yaml"


COMPETITION_TO_GRADE = {
    "NSW Cup": "nsw_cup",
    "QLD Cup": "qld_cup",
}


def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def get_db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://jeromelu_admin:localdev123@localhost:5440/jeromelu",
    )


def _strip_driver(url: str) -> str:
    return re.sub(r"^postgresql\+[a-z]+://", "postgresql://", url)


def load_team_rows(yaml_path: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """Return (nrl_rows, feeder_rows, nrlw_rows).

    Feeder + NRLW rows include `parent_slug` so phase 2 can wire parent_team_id.
    """
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    nrl_rows: list[dict] = []
    feeder_rows: list[dict] = []
    nrlw_rows: list[dict] = []

    for slug, team in data.get("teams", {}).items():
        nrl_rows.append({
            "slug": slug,
            "name": team["name"],
            "short_name": team.get("short"),
            "aliases": team.get("aliases", []) or [],
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
            print(f"WARN: unknown competition '{rg_comp}' for {slug} feeder — skipping")
            continue
        rg_slug_base = _slugify(rg_name)
        # Disambiguate feeders that share the parent's NRL slug
        # (e.g. Newcastle Knights NSW Cup side keeps the same name).
        rg_slug = (
            f"{rg_slug_base}_{rg_grade}"
            if rg_slug_base == slug
            else rg_slug_base
        )
        feeder_rows.append({
            "slug": rg_slug,
            "name": rg_name,
            "short_name": None,
            "aliases": [],
            "grade": rg_grade,
            "competition": rg_comp,
            "parent_slug": slug,
        })

    for parent_slug, team in data.get("nrlw", {}).items():
        nrlw_rows.append({
            "slug": f"{parent_slug}_nrlw",
            "name": team["name"],
            "short_name": team.get("short"),
            "aliases": team.get("aliases", []) or [],
            "grade": "nrlw",
            "competition": "NRLW Premiership",
            "parent_slug": parent_slug,
        })

    return nrl_rows, feeder_rows, nrlw_rows


UPSERT_SQL = """
INSERT INTO teams (slug, name, short_name, aliases, grade, competition, parent_team_id, entity_id)
VALUES %s
ON CONFLICT (slug) DO UPDATE SET
    name           = EXCLUDED.name,
    short_name     = EXCLUDED.short_name,
    aliases        = EXCLUDED.aliases,
    grade          = EXCLUDED.grade,
    competition    = EXCLUDED.competition,
    parent_team_id = EXCLUDED.parent_team_id,
    entity_id      = COALESCE(EXCLUDED.entity_id, teams.entity_id),
    updated_at     = now()
"""

LINK_ENTITY_SQL = """
UPDATE teams t
   SET entity_id = e.entity_id,
       updated_at = now()
  FROM entities e
 WHERE e.entity_type = 'team'
   AND lower(e.canonical_name) = lower(t.name)
   AND t.entity_id IS NULL
   AND t.grade = 'nrl'
"""
# NRL-only auto-link: NRLW teams share canonical_name with their NRL parent
# (e.g. "Wests Tigers" exists at both grades). A name-based match would
# attach the same entity to both rows and trip teams.entity_id UNIQUE.
# NRLW rows get their entity_id wired manually when claims start landing
# on women's teams — likely via a slug-based convention, not name match.


def _to_tuples(rows: Iterable[dict], slug_to_id: dict[str, str]) -> list[tuple]:
    out: list[tuple] = []
    for r in rows:
        parent_id = slug_to_id.get(r["parent_slug"]) if r["parent_slug"] else None
        out.append((
            r["slug"],
            r["name"],
            r["short_name"],
            r["aliases"],
            r["grade"],
            r["competition"],
            parent_id,
            None,  # entity_id wired in a follow-up step
        ))
    return out


def main() -> int:
    if not YAML_PATH.exists():
        print(f"ERROR: {YAML_PATH} not found")
        return 1

    nrl_rows, feeder_rows, nrlw_rows = load_team_rows(YAML_PATH)
    print(
        f"Loaded {len(nrl_rows)} NRL, {len(feeder_rows)} reserve-grade, "
        f"{len(nrlw_rows)} NRLW rows from {YAML_PATH.name}"
    )

    conn = psycopg2.connect(_strip_driver(get_db_url()))
    try:
        with conn.cursor() as cur:
            # Phase 1 — NRL parents (no parent_team_id needed)
            execute_values(cur, UPSERT_SQL, _to_tuples(nrl_rows, {}))

            cur.execute("SELECT slug, team_id FROM teams WHERE grade = 'nrl'")
            slug_to_id: dict[str, str] = {row[0]: row[1] for row in cur.fetchall()}

            # Phase 2 — feeders + NRLW (parent_team_id resolved via slug_to_id)
            execute_values(cur, UPSERT_SQL, _to_tuples(feeder_rows, slug_to_id))
            execute_values(cur, UPSERT_SQL, _to_tuples(nrlw_rows, slug_to_id))

            # Phase 3 — opportunistic entity linkage for NRL/NRLW rows that
            # match an existing entities.canonical_name (case-insensitive).
            cur.execute(LINK_ENTITY_SQL)
            linked = cur.rowcount

            conn.commit()

            cur.execute("SELECT grade, count(*) FROM teams GROUP BY grade ORDER BY grade")
            for grade, count in cur.fetchall():
                print(f"  {grade:<16} {count}")
            print(f"  entity_id linked: {linked} row(s)")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
