"""Fetch the NRL player roster from supercoach.com.au and persist locally.

Thin CLI wrapper around :func:`jeromelu_shared.players.supercoach.fetch_supercoach_roster`.
Writes ``scripts/data/scraped_players_api_raw.json`` — the file that
``make seed-players`` and the prod admin endpoints already consume.

For prod, prefer the server-side endpoint:
``POST /api/admin/players/fetch-and-refresh`` (one call, fetch + SCD-2
diff in the API container; no payload to ship). This script remains the
right tool for local-dev and for regenerating ``data/players.yaml`` via
``make fetch-players``.

Usage::

    python scripts/data/fetchers/fetch_supercoach_players.py
    python scripts/data/fetchers/fetch_supercoach_players.py --season 2027
    python scripts/data/fetchers/fetch_supercoach_players.py --out path/to/roster.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

# Ensure the shared package is importable when run from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "packages", "shared"))

from jeromelu_shared.players.supercoach import (  # noqa: E402
    SuperCoachFetchError,
    fetch_supercoach_roster,
)


DEFAULT_OUT = Path(__file__).resolve().parent.parent / "scraped_players_api_raw.json"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=date.today().year)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    try:
        data = fetch_supercoach_roster(season=args.season)
    except SuperCoachFetchError as e:
        sys.exit(str(e))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2))
    print(f"Saved {len(data)} players (season {args.season}) to {args.out}")


if __name__ == "__main__":
    main()
