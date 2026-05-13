"""Phase 1.6 — reconstruct people_attributes (team-tenure SCD-2) from
match_team_lists.

people_attributes is the canonical place to ask "who was on which team
when?". The SC roster pipeline already writes here for current
SC-eligible players (1,105 rows across 563 people). Historical players
(the 2,094 we just inserted via phase_people) have no tenure rows at
all — this phase fills that gap by walking each player's match-centre
appearances chronologically and grouping consecutive same-team games
into tenure windows.

Trust hierarchy (per [D11]):
  - SC owns `is_current=True` for SC-eligible players. We never write
    a competing is_current row for a person who has one from SC.
  - For historical/non-SC people, this phase marks the most-recent
    tenure is_current=True only if the player's last match was within
    the last 12 months (active heuristic). Otherwise all tenures are
    closed (is_current=False, effective_to set).

Idempotency:
  DELETE FROM people_attributes WHERE source='nrlcom/match-centre' at
  the start. Re-inserts produce the same set of rows each run.

Coaches (jersey_number IS NULL) are skipped — their tenures need a
different model (people_roles), which is a separate follow-up.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Don't mark as is_current any tenure whose last match was older than this.
ACTIVE_RECENCY_DAYS = 365


@dataclass
class TenureWindow:
    team_id: str
    first_match: date
    last_match: date
    primary_position: str | None
    match_count: int


def _iter_tenures(rows: Iterable[tuple[str, str, datetime, str | None]]) -> list[TenureWindow]:
    """Group consecutive same-team appearances into tenure windows.

    Input rows: (person_id, team_id, kickoff_at, named_position) sorted
    by (person_id, kickoff_at). Yields one tenure per (person, team)
    contiguous run, not per (person, team) distinct.
    """
    out: list[TenureWindow] = []
    cur_team: str | None = None
    positions: Counter[str] = Counter()
    first: date | None = None
    last: date | None = None
    match_count = 0

    for team_id, kickoff_at, named_position in rows:
        d = kickoff_at.date() if isinstance(kickoff_at, datetime) else kickoff_at
        if team_id != cur_team:
            if cur_team is not None and first is not None and last is not None:
                pos = positions.most_common(1)[0][0] if positions else None
                out.append(TenureWindow(cur_team, first, last, pos, match_count))
            cur_team = team_id
            positions = Counter()
            first = d
            match_count = 0
        last = d
        match_count += 1
        if named_position:
            positions[named_position] += 1

    if cur_team is not None and first is not None and last is not None:
        pos = positions.most_common(1)[0][0] if positions else None
        out.append(TenureWindow(cur_team, first, last, pos, match_count))
    return out


def populate_people_attributes(db: Session) -> dict[str, Any]:
    """Walk every player's match_team_lists chronologically and project
    tenure windows into people_attributes.
    """
    # 1. Who has an SC-sourced is_current row? Don't touch those.
    sc_current_rows = db.execute(text("""
        SELECT person_id FROM people_attributes
        WHERE is_current AND source = 'supercoach'
    """)).fetchall()
    sc_current = {str(r[0]) for r in sc_current_rows}
    logger.info("phase_attributes: %d people have SC-owned is_current rows", len(sc_current))

    # 2. Idempotent reset of our slice.
    deleted = db.execute(text(
        "DELETE FROM people_attributes WHERE source='nrlcom/match-centre'"
    )).rowcount or 0
    logger.info("phase_attributes: deleted %d existing nrlcom-sourced rows", deleted)

    # 3. Stream every player appearance, sorted by (person, kickoff).
    #    jersey_number IS NOT NULL keeps coaches out of the player tenure model.
    cursor = db.execute(text("""
        SELECT
            mtl.player_id::text AS person_id,
            mtl.team_id::text AS team_id,
            m.kickoff_at,
            mtl.named_position
        FROM match_team_lists mtl
        JOIN matches m ON m.match_id = mtl.match_id
        WHERE mtl.player_id IS NOT NULL
          AND mtl.jersey_number IS NOT NULL
          AND m.kickoff_at IS NOT NULL
        ORDER BY mtl.player_id, m.kickoff_at
    """))

    today = datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=ACTIVE_RECENCY_DAYS)

    insert_sql = text("""
        INSERT INTO people_attributes (
            person_id, team_id, primary_position,
            effective_from, effective_to, is_current,
            source, metadata_json
        )
        VALUES (
            :person_id, :team_id, :primary_position,
            :effective_from, :effective_to, :is_current,
            'nrlcom/match-centre',
            CAST(:metadata_json AS JSONB)
        )
    """)

    people_seen = 0
    tenures_inserted = 0
    most_recent_open = 0
    cur_person: str | None = None
    buffer: list[tuple[str, datetime, str | None]] = []

    def flush(person_id: str, rows: list[tuple[str, datetime, str | None]]) -> tuple[int, int]:
        if not rows:
            return 0, 0
        tenures = _iter_tenures(rows)
        last_idx = len(tenures) - 1
        n_inserted = 0
        n_open = 0
        for i, t in enumerate(tenures):
            is_latest = (i == last_idx)
            # SC owns is_current for its people. For others, mark the
            # most-recent tenure as is_current=True only if it's active.
            mark_current = (
                is_latest
                and person_id not in sc_current
                and t.last_match >= cutoff
            )
            if is_latest:
                effective_to = None if mark_current else t.last_match
            else:
                # Closed at successor's first match - 1 day
                effective_to = tenures[i + 1].first_match - timedelta(days=1)
                # Guard the period CHECK constraint: effective_to >= effective_from
                if effective_to < t.first_match:
                    effective_to = t.first_match

            db.execute(insert_sql, {
                "person_id": person_id,
                "team_id": t.team_id,
                "primary_position": t.primary_position,
                "effective_from": t.first_match,
                "effective_to": effective_to,
                "is_current": mark_current,
                "metadata_json": json.dumps({
                    "match_count": t.match_count,
                    "tenure_index": i,
                    "tenure_count": len(tenures),
                }),
            })
            n_inserted += 1
            if mark_current:
                n_open += 1
        return n_inserted, n_open

    for row in cursor:
        person_id = row.person_id
        if cur_person is not None and person_id != cur_person:
            ins, opn = flush(cur_person, buffer)
            tenures_inserted += ins
            most_recent_open += opn
            people_seen += 1
            buffer = []
            if people_seen % 200 == 0:
                logger.info(
                    "  phase_attributes: %d people processed (tenures=%d, open=%d)",
                    people_seen, tenures_inserted, most_recent_open,
                )
                db.commit()
        cur_person = person_id
        buffer.append((row.team_id, row.kickoff_at, row.named_position))

    if cur_person is not None:
        ins, opn = flush(cur_person, buffer)
        tenures_inserted += ins
        most_recent_open += opn
        people_seen += 1

    db.commit()
    logger.info(
        "phase_attributes: people_seen=%d tenures_inserted=%d most_recent_open=%d "
        "(sc_owned_current_preserved=%d)",
        people_seen, tenures_inserted, most_recent_open, len(sc_current),
    )
    return {
        "people_seen": people_seen,
        "tenures_inserted": tenures_inserted,
        "most_recent_open": most_recent_open,
        "sc_current_preserved": len(sc_current),
        "deleted_pre_insert": deleted,
    }
