"""Seed player_team_history from players.yaml.

Idempotent: uses ON CONFLICT to upsert rows.
"""

import os
import sys
from datetime import date
from pathlib import Path

import yaml
import psycopg2
from psycopg2.extras import execute_values

YAML_PATH = Path(__file__).resolve().parent.parent / "data" / "players.yaml"

UPSERT_SQL = """
INSERT INTO player_team_history (player_name, team_key, team_name, effective_from, is_current, source)
VALUES %s
ON CONFLICT (player_name, effective_from)
DO UPDATE SET
    team_key   = EXCLUDED.team_key,
    team_name  = EXCLUDED.team_name,
    updated_at = now()
"""


def get_db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://jeromelu:jeromelu@localhost:5432/jeromelu",
    )


def load_players(yaml_path: Path) -> list[tuple]:
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    rows = []
    effective_from = date(2026, 1, 1)

    for team_key, team_data in data["teams"].items():
        team_name = team_data["name"]
        for player in team_data["players"]:
            player_name = player["name"] if isinstance(player, dict) else player
            rows.append((player_name, team_key, team_name, effective_from, True, "seed"))

    return rows


def main():
    if not YAML_PATH.exists():
        print(f"ERROR: {YAML_PATH} not found")
        sys.exit(1)

    rows = load_players(YAML_PATH)
    print(f"Loaded {len(rows)} players from {YAML_PATH.name}")

    db_url = get_db_url()
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            execute_values(cur, UPSERT_SQL, rows)
            conn.commit()
            cur.execute("SELECT count(*) FROM player_team_history WHERE is_current")
            count = cur.fetchone()[0]
            print(f"player_team_history now has {count} current rows")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
