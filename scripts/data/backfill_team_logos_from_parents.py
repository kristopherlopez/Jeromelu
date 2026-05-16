"""Backfill `teams.logo_url` for child teams (NRLW + reserve grades) by
inheriting from their NRL parent.

After `seed_teams.py` populates the roster and `seed_teams_logos.py` (or
the manual NRL-only logo seed) sets `logo_url` on the 19 NRL clubs, the
NRLW and feeder rows are still blank. They almost always share a brand
with the NRL parent (e.g. Brisbane Broncos NRLW → Broncos badge), so the
straightforward fix is `child.logo_url = parent.logo_url` wherever the
child has none.

Idempotent: only updates rows where `logo_url IS NULL` and the parent
has one. Re-runs are no-ops.

Independent reserve teams (QLD Cup clubs without a `parent_team_id` —
Northern Pride, Mackay Cutters, PNG Hunters, etc.) and the PNG Chiefs
NRL row are NOT touched here; those need hand-curated URLs.

Usage::

    cd services/api
    source .venv/Scripts/activate   # Windows (Git Bash)
    python ../../scripts/data/backfill_team_logos_from_parents.py
"""

from __future__ import annotations

import os
import re
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker


def get_db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://jeromelu_admin:localdev123@localhost:5440/jeromelu",
    )


def _normalise_driver(url: str) -> str:
    return re.sub(r"^postgresql\+[a-z]+://", "postgresql://", url)


UPDATE_SQL = text("""
    UPDATE teams c
       SET logo_url   = p.logo_url,
           updated_at = now()
      FROM teams p
     WHERE c.parent_team_id = p.team_id
       AND c.logo_url IS NULL
       AND p.logo_url IS NOT NULL
""")

REPORT_SQL = text("""
    SELECT grade,
           count(*) FILTER (WHERE logo_url IS NULL) AS missing,
           count(*)                                 AS total
      FROM teams
     GROUP BY grade
     ORDER BY grade
""")


def main() -> int:
    engine = create_engine(_normalise_driver(get_db_url()))
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db: Session = SessionLocal()
    try:
        result = db.execute(UPDATE_SQL)
        db.commit()
        print(f"Updated {result.rowcount} team row(s) with parent logo_url.")
        print("Logo coverage by grade:")
        for grade, missing, total in db.execute(REPORT_SQL).all():
            print(f"  {grade:<8} missing {missing:>2} / {total}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
