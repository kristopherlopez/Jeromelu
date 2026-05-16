"""Seed `venues` from data/venues.yaml.

Idempotent — ON CONFLICT (slug) upserts. Mirrors the conventions of
``seed_teams.py``.
"""

import os
import re
import sys
from pathlib import Path

import psycopg2
import yaml
from psycopg2.extras import execute_values

YAML_PATH = Path(__file__).resolve().parents[2] / "data" / "venues.yaml"


def get_db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://jeromelu_admin:localdev123@localhost:5440/jeromelu",
    )


def _strip_driver(url: str) -> str:
    return re.sub(r"^postgresql\+[a-z]+://", "postgresql://", url)


UPSERT_SQL = """
INSERT INTO venues (
    slug, name, aliases, city, state, country,
    capacity, surface, roof, tz
)
VALUES %s
ON CONFLICT (slug) DO UPDATE SET
    name       = EXCLUDED.name,
    aliases    = EXCLUDED.aliases,
    city       = EXCLUDED.city,
    state      = EXCLUDED.state,
    country    = EXCLUDED.country,
    capacity   = EXCLUDED.capacity,
    surface    = EXCLUDED.surface,
    roof       = EXCLUDED.roof,
    tz         = EXCLUDED.tz,
    updated_at = now()
"""


def load_venue_rows(yaml_path: Path) -> list[tuple]:
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    rows: list[tuple] = []
    for slug, venue in (data.get("venues") or {}).items():
        rows.append((
            slug,
            venue["name"],
            venue.get("aliases") or [],
            venue.get("city"),
            venue.get("state"),
            venue.get("country", "AU"),
            venue.get("capacity"),
            venue.get("surface"),
            venue.get("roof"),
            venue.get("tz"),
        ))
    return rows


def main() -> int:
    if not YAML_PATH.exists():
        print(f"ERROR: {YAML_PATH} not found")
        return 1

    rows = load_venue_rows(YAML_PATH)
    print(f"Loaded {len(rows)} venue(s) from {YAML_PATH.name}")

    conn = psycopg2.connect(_strip_driver(get_db_url()))
    try:
        with conn.cursor() as cur:
            execute_values(cur, UPSERT_SQL, rows)
            conn.commit()
            cur.execute("SELECT count(*) FROM venues")
            (count,) = cur.fetchone()
            print(f"  venues now in DB: {count}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
