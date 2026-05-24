"""Phase 2e — extract_match_timeline + extract_match_officials.

Both come from the same scout/nrlcom/match-centre/* archives — combined
here so we only walk the archive set once.

match_timeline:
  One row per event in `timeline[]`. Ordered via `sequence` (0..N).
  Idempotent UPSERT on (nrlcom_match_id, sequence).

match_officials:
  4 rows per match from `officials[]`. Idempotent UPSERT on
  (nrlcom_match_id, first_name, last_name, role).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ._s3_walk import list_keys, read_json_concurrent

logger = logging.getLogger(__name__)


def _build_team_id_map(db: Session) -> dict[int, str]:
    rows = db.execute(text(
        "SELECT team_id, nrlcom_team_id FROM teams WHERE nrlcom_team_id IS NOT NULL"
    )).fetchall()
    return {nid: str(tid) for tid, nid in rows}


def _build_match_id_map(db: Session, seasons: list[int] | None) -> dict[str, str]:
    q = "SELECT match_id, external_match_id FROM matches WHERE source='nrl_com' AND external_match_id IS NOT NULL"
    if seasons:
        q += f" AND season IN ({','.join(str(s) for s in seasons)})"
    rows = db.execute(text(q)).fetchall()
    return {ext: str(mid) for mid, ext in rows}


def _build_player_id_map(db: Session) -> dict[int, str]:
    rows = db.execute(text(
        "SELECT person_id, nrlcom_player_id FROM people WHERE nrlcom_player_id IS NOT NULL"
    )).fetchall()
    return {nid: str(pid) for pid, nid in rows}


def _extract_timeline_rows(
    payload: dict[str, Any],
    key: str,
    match_id: str,
    team_map: dict[int, str],
    player_map: dict[int, str],
) -> list[dict[str, Any]]:
    """Pure projection of one match-centre archive into match_timeline rows.

    One row per event in `timeline[]`, ordered by `sequence` (0..N-1). Team
    and player are resolved via the passed-in maps. No S3, no DB — mirrors
    the `phase_matches._extract_one` template.
    """
    match_ext = str(payload.get("matchId") or "").strip()
    rows: list[dict[str, Any]] = []
    for sequence, ev in enumerate(payload.get("timeline") or []):
        nrlcom_team_id = ev.get("teamId")
        team_id = team_map.get(int(nrlcom_team_id)) if nrlcom_team_id else None
        nrlcom_player_id = ev.get("playerId")
        person_id = player_map.get(int(nrlcom_player_id)) if nrlcom_player_id else None
        rows.append({
            "match_id": match_id,
            "nrlcom_match_id": match_ext,
            "sequence": sequence,
            "event_type": ev.get("type") or "Unknown",
            "title": ev.get("title"),
            "game_seconds": ev.get("gameSeconds"),
            "nrlcom_team_id": int(nrlcom_team_id) if nrlcom_team_id else None,
            "team_id": team_id,
            "nrlcom_player_id": int(nrlcom_player_id) if nrlcom_player_id else None,
            "person_id": person_id,
            "running_home_score": ev.get("homeScore"),
            "running_away_score": ev.get("awayScore"),
            "raw_payload": json.dumps(ev, default=str),
            "s3_archive_key": key,
        })
    return rows


def _extract_official_rows(
    payload: dict[str, Any],
    key: str,
    match_id: str,
) -> list[dict[str, Any]]:
    """Pure projection of one match-centre archive into match_officials rows.

    One row per official in `officials[]` that has a first or last name.
    `person_id` is left None (officials don't share the players profile-id
    space cleanly). No S3, no DB.
    """
    rows: list[dict[str, Any]] = []
    match_ext = str(payload.get("matchId") or "").strip()
    for o in payload.get("officials") or []:
        fn = (o.get("firstName") or "").strip()
        ln = (o.get("lastName") or "").strip()
        if not (fn or ln):
            continue
        role = (o.get("position") or "").strip() or None
        rows.append({
            "match_id": match_id,
            "nrlcom_match_id": match_ext,
            "first_name": fn,
            "last_name": ln,
            "role": role,
            "person_id": None,
            "raw_payload": json.dumps(o, default=str),
            "s3_archive_key": key,
        })
    return rows


def populate_timeline_and_officials(
    db: Session,
    *,
    seasons: list[int] | None = None,
    competition: int = 111,
) -> dict[str, Any]:
    team_map = _build_team_id_map(db)
    match_map = _build_match_id_map(db, seasons)
    player_map = _build_player_id_map(db)
    logger.info(
        "phase_timeline: lookups — %d teams, %d matches, %d players",
        len(team_map), len(match_map), len(player_map),
    )

    keys = list_keys(f"scout/nrlcom/match-centre/{competition}/")
    if seasons:
        season_strs = {f"/{s}/" for s in seasons}
        keys = [k for k in keys if any(s in k for s in season_strs)]
    logger.info("phase_timeline: %d match-centre archives to scan", len(keys))

    archives_read = 0
    archives_failed = 0
    timeline_inserted = 0
    timeline_updated = 0
    officials_inserted = 0
    officials_updated = 0
    matches_unmatched = 0

    timeline_sql = text("""
        INSERT INTO match_timeline (
            match_id, nrlcom_match_id, sequence, event_type, title,
            game_seconds, nrlcom_team_id, team_id, nrlcom_player_id, person_id,
            running_home_score, running_away_score, raw_payload, s3_archive_key
        )
        VALUES (
            :match_id, :nrlcom_match_id, :sequence, :event_type, :title,
            :game_seconds, :nrlcom_team_id, :team_id, :nrlcom_player_id, :person_id,
            :running_home_score, :running_away_score,
            CAST(:raw_payload AS JSONB), :s3_archive_key
        )
        ON CONFLICT (nrlcom_match_id, sequence) DO UPDATE SET
            match_id = EXCLUDED.match_id,
            event_type = EXCLUDED.event_type,
            title = EXCLUDED.title,
            game_seconds = EXCLUDED.game_seconds,
            nrlcom_team_id = EXCLUDED.nrlcom_team_id,
            team_id = EXCLUDED.team_id,
            nrlcom_player_id = EXCLUDED.nrlcom_player_id,
            person_id = EXCLUDED.person_id,
            running_home_score = EXCLUDED.running_home_score,
            running_away_score = EXCLUDED.running_away_score,
            raw_payload = EXCLUDED.raw_payload,
            s3_archive_key = EXCLUDED.s3_archive_key
        RETURNING (xmax = 0) AS inserted
    """)

    officials_sql = text("""
        INSERT INTO match_officials (
            match_id, nrlcom_match_id, first_name, last_name, role,
            person_id, raw_payload, s3_archive_key
        )
        VALUES (
            :match_id, :nrlcom_match_id, :first_name, :last_name, :role,
            :person_id, CAST(:raw_payload AS JSONB), :s3_archive_key
        )
        ON CONFLICT (nrlcom_match_id, first_name, last_name, COALESCE(role, ''))
        DO UPDATE SET
            match_id = EXCLUDED.match_id,
            person_id = EXCLUDED.person_id,
            raw_payload = EXCLUDED.raw_payload,
            s3_archive_key = EXCLUDED.s3_archive_key
        RETURNING (xmax = 0) AS inserted
    """)

    for key, payload, err in read_json_concurrent(keys, max_workers=16):
        if err is not None or payload is None:
            archives_failed += 1
            continue
        archives_read += 1
        match_ext = str(payload.get("matchId") or "").strip()
        if not match_ext or match_ext not in match_map:
            matches_unmatched += 1
            continue
        match_id = match_map[match_ext]

        # Timeline events
        for row in _extract_timeline_rows(payload, key, match_id, team_map, player_map):
            res = db.execute(timeline_sql, row)
            if res.scalar():
                timeline_inserted += 1
            else:
                timeline_updated += 1

        # Officials
        for row in _extract_official_rows(payload, key, match_id):
            res = db.execute(officials_sql, row)
            if res.scalar():
                officials_inserted += 1
            else:
                officials_updated += 1

        if archives_read % 50 == 0:
            db.commit()

    db.commit()
    logger.info(
        "phase_timeline: timeline_inserted=%d updated=%d  officials_inserted=%d updated=%d  matches_unmatched=%d",
        timeline_inserted, timeline_updated,
        officials_inserted, officials_updated,
        matches_unmatched,
    )
    return {
        "archives_read": archives_read,
        "archives_failed": archives_failed,
        "timeline_inserted": timeline_inserted,
        "timeline_updated": timeline_updated,
        "officials_inserted": officials_inserted,
        "officials_updated": officials_updated,
        "matches_unmatched": matches_unmatched,
    }
