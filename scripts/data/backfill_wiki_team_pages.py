"""Backfill `wiki_pages` rows for every existing `Team`.

The `teams` table is seeded by `seed_teams.py` / the `POST /api/admin/teams/seed`
endpoint, neither of which writes the matching `wiki_pages` row. As a result
the wiki dashboard shows "0 teams" even when the roster is fully populated.

This is a one-shot fix for the existing gap. It:

  1. Selects every Team that does not yet have a `wiki_pages` row
     (`wiki_pages.team_id` IS NULL match).
  2. Inserts a stub `wiki_pages` row per team — `page_type='team'`,
     `slug = team.slug`, `title = team.name`, `team_id` set, `status='stub'`,
     `summary` = competition label, empty content.
  3. Inserts an initial `wiki_revisions` entry for traceability.

Idempotent: re-running is a no-op once teams have pages. Skips rows whose
`team.slug` already exists in `wiki_pages` (defensive — the unique index
on `wiki_pages.slug` would reject the insert anyway).

Usage::

    cd services/api
    source .venv/Scripts/activate   # Windows (Git Bash)
    python ../../scripts/data/backfill_wiki_team_pages.py
"""

from __future__ import annotations

import os
import re
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

# Make the shared package importable when running from repo root.
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "..", "packages", "shared"),
)

from jeromelu_shared.db.models import Team, WikiPage, WikiRevision  # noqa: E402


def get_db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://jeromelu_admin:localdev123@localhost:5440/jeromelu",
    )


def _normalise_driver(url: str) -> str:
    # The rest of the codebase uses psycopg v3 (services/api/requirements.txt
    # ships psycopg[binary]==3.2.*), not the legacy psycopg2. Normalise any
    # incoming driver token to `+psycopg` so this script runs both locally
    # and inside the api container.
    if url.startswith("postgresql+psycopg://"):
        return url
    return re.sub(r"^postgresql(\+[a-z]+)?://", "postgresql+psycopg://", url)


def _summary_for(team: Team) -> str | None:
    if team.competition:
        return team.competition
    return team.grade.upper() if team.grade else None


def main() -> int:
    engine = create_engine(_normalise_driver(get_db_url()))
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db: Session = SessionLocal()

    try:
        existing_team_ids: set = set(
            r[0] for r in db.execute(
                select(WikiPage.team_id).where(WikiPage.team_id.is_not(None))
            ).all()
        )
        existing_slugs: set[str] = set(
            r[0] for r in db.execute(select(WikiPage.slug)).all()
        )

        teams = db.execute(select(Team)).scalars().all()

        created = 0
        skipped_have_page = 0
        skipped_slug_collision = 0

        for t in teams:
            if t.team_id in existing_team_ids:
                skipped_have_page += 1
                continue
            if t.slug in existing_slugs:
                # A wiki_page with this slug already exists but is bound to a
                # different (or no) team. Don't trample it — surface and skip.
                print(f"  WARN: slug collision on '{t.slug}' — skipping {t.name}")
                skipped_slug_collision += 1
                continue

            page = WikiPage(
                team_id=t.team_id,
                page_type="team",
                slug=t.slug,
                title=t.name,
                content="",
                summary=_summary_for(t),
                status="stub",
                metadata_json={
                    "grade": t.grade,
                    "competition": t.competition,
                    "short_name": t.short_name,
                },
            )
            db.add(page)
            db.flush()  # populate page_id

            db.add(WikiRevision(
                page_id=page.page_id,
                summary="Stub page created from teams roster",
                source_trigger="backfill_wiki_team_pages.py",
            ))
            existing_slugs.add(t.slug)
            existing_team_ids.add(t.team_id)
            created += 1

        db.commit()

        print(f"Created {created} team wiki page(s).")
        if skipped_have_page:
            print(f"  Skipped (already had page): {skipped_have_page}")
        if skipped_slug_collision:
            print(f"  Skipped (slug collision): {skipped_slug_collision}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
