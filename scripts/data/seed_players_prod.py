"""Seed local Postgres from a SuperCoach roster JSON dump.

Reads ``scripts/data/scraped_players_api_raw.json`` (produced by the
``scrape-supercoach`` skill) and idempotently populates entities + teams +
player_attributes via the shared :mod:`jeromelu_shared.players.roster`
module.

For prod, push the same JSON file at the admin endpoint instead — see
``make prod-seed-players`` in the Makefile.

Usage::

    cd services/api
    source .venv/Scripts/activate          # Windows
    python ../../scripts/data/seed_players_prod.py
    # or with a specific roster file:
    python ../../scripts/data/seed_players_prod.py path/to/roster.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure shared package is importable when running from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "shared"))

from jeromelu_shared.players.roster import seed_roster  # noqa: E402


DEFAULT_ROSTER = (
    Path(__file__).resolve().parent / "scraped_players_api_raw.json"
)


def get_db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://jeromelu_admin:localdev123@localhost:5440/jeromelu",
    )


def main() -> None:
    roster_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ROSTER
    if not roster_path.exists():
        print(f"ERROR: roster file not found: {roster_path}")
        print("Run /scrape-supercoach first to produce scraped_players_api_raw.json.")
        sys.exit(1)

    with open(roster_path, encoding="utf-8") as f:
        sc_players = json.load(f)

    print(f"Loaded {len(sc_players)} players from {roster_path.name}")

    engine = create_engine(get_db_url())
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        result = seed_roster(session, sc_players, source="supercoach")
    finally:
        session.close()

    for k, v in result.items():
        print(f"  {k:<30}{v}")


if __name__ == "__main__":
    main()
