"""Walk scout/* archives in S3 and project into DB tables.

Usage:
    python -m scripts.data.populate_db_from_s3 --phase identity
    python -m scripts.data.populate_db_from_s3 --phase all
    python -m scripts.data.populate_db_from_s3 --phase matches --seasons 2024 2025 2026

Phases run in FK-dependency order. `--phase all` runs every phase in
sequence. Re-running is idempotent — each phase uses UPSERT semantics on
natural keys.

This is a one-shot backfill driver. Day-to-day, the Scout pipelines
(nrlcom-match-centre, nrlcom-ladder, etc.) keep the archives current and
their attached extractors keep the DB current. This script only exists to
project the historical backlog of archives that exist in S3 but never had
extractors when they were captured.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from jeromelu_shared.db.session import SessionLocal

from .populate.phase_identity import backfill_identity
from .populate.phase_matches import populate_matches
from .populate.phase_rounds import populate_rounds
from .populate.phase_aux import (
    populate_injuries,
    populate_stat_leaderboards,
    populate_team_standings,
)
from .populate.phase_people import populate_people_history, reresolve_person_ids
from .populate.phase_stats import populate_player_match_stats
from .populate.phase_team_lists import populate_team_lists
from .populate.phase_timeline import populate_timeline_and_officials

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


PHASES = ("identity", "people", "rounds", "matches", "team_lists", "stats",
          "timeline", "standings", "leaderboards", "injuries", "reresolve")


def main() -> int:
    parser = argparse.ArgumentParser(description="Populate DB from S3 archives.")
    parser.add_argument(
        "--phase",
        choices=(*PHASES, "all"),
        required=True,
        help="Which phase to run (run them in PHASES order if 'all').",
    )
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=[2024, 2025, 2026],
        help="Seasons to consider (where the phase is season-scoped).",
    )
    parser.add_argument(
        "--competition",
        type=int,
        default=111,
        help="NRL=111, NRLW=161 (default 111).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute counts but rollback the transaction at the end.",
    )
    args = parser.parse_args()

    chosen = PHASES if args.phase == "all" else (args.phase,)
    results: dict[str, dict] = {}

    db = SessionLocal()
    try:
        for phase in chosen:
            logger.info("======== phase: %s ========", phase)
            if phase == "identity":
                results[phase] = backfill_identity(
                    db, seasons=args.seasons, competition=args.competition,
                )
            elif phase == "people":
                results[phase] = populate_people_history(db, competition=args.competition)
            elif phase == "reresolve":
                results[phase] = reresolve_person_ids(db)
            elif phase == "rounds":
                results[phase] = populate_rounds(
                    db, seasons=args.seasons, competition=args.competition,
                )
            elif phase == "matches":
                results[phase] = populate_matches(
                    db, seasons=args.seasons, competition=args.competition,
                )
            elif phase == "team_lists":
                results[phase] = populate_team_lists(
                    db, seasons=args.seasons, competition=args.competition,
                )
            elif phase == "stats":
                results[phase] = populate_player_match_stats(
                    db, seasons=args.seasons, competition=args.competition,
                )
            elif phase == "timeline":
                results[phase] = populate_timeline_and_officials(
                    db, seasons=args.seasons, competition=args.competition,
                )
            elif phase == "standings":
                results[phase] = populate_team_standings(db, competition=args.competition)
            elif phase == "leaderboards":
                results[phase] = populate_stat_leaderboards(db, competition=args.competition)
            elif phase == "injuries":
                results[phase] = populate_injuries(db, competition=args.competition)
            else:
                logger.warning("phase %s not yet implemented — skipping", phase)
                results[phase] = {"skipped": True}

        if args.dry_run:
            logger.info("--dry-run — rolling back all changes")
            db.rollback()
    except Exception:
        db.rollback()
        logger.exception("populate failed — rolled back")
        raise
    finally:
        db.close()

    logger.info("done. summary:\n%s", json.dumps(results, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
