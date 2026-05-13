"""Phase 2c — extract match_team_lists from scout/nrlcom/match-centre/* archives.

Two row classes land in match_team_lists:

1. Players: one row per (match, team, player) with jersey_number,
   named_position, is_captain. Resolved against people via
   people.nrlcom_player_id (populated by phase_identity).

2. Coaches: per user direction, coaches are captured in the people table
   (insert if missing) and attributed to matches via match_team_lists rows
   with jersey_number=NULL, named_position in {'Coach', 'Assistant Coach'}.
   Coach profileId is stored on people.nrlcom_player_id (same identity
   space upstream).

There is no DB unique constraint on (match_id, team_id, player_id,
list_version) — match_team_lists supports late-change versions. For the
post-match snapshot, we treat list_version=1 as the canonical capture and
pre-check existence before INSERT.
"""

from __future__ import annotations

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


def _ensure_coach_person(
    db: Session,
    *,
    coach: dict[str, Any],
    player_id_map: dict[int, str],
) -> str | None:
    """Find or insert a `people` row for a coach. Returns person_id (str) or None.

    Coaches share the nrlcom profileId space with players, so we store
    profileId in people.nrlcom_player_id. The metadata_json.role_class='coach'
    tag distinguishes them from players in queries.
    """
    profile_id = coach.get("profileId")
    fn = (coach.get("firstName") or "").strip()
    ln = (coach.get("lastName") or "").strip()
    if not profile_id or not (fn or ln):
        return None
    cached = player_id_map.get(int(profile_id))
    if cached:
        return cached

    existing = db.execute(
        text("SELECT person_id FROM people WHERE nrlcom_player_id = :pid"),
        {"pid": int(profile_id)},
    ).first()
    if existing:
        person_id = str(existing[0])
        player_id_map[int(profile_id)] = person_id
        return person_id

    canonical = f"{fn} {ln}".strip()
    slug_base = canonical.lower().replace(" ", "-").replace("'", "")
    for slug in (slug_base, f"{slug_base}-{profile_id}"):
        row = db.execute(
            text("""
                INSERT INTO people (canonical_name, slug, image_url, nrlcom_player_id, metadata_json)
                VALUES (:name, :slug, :image, :pid, '{"role_class": "coach"}'::jsonb)
                ON CONFLICT (slug) DO NOTHING
                RETURNING person_id
            """),
            {
                "name": canonical,
                "slug": slug,
                "image": coach.get("headImage"),
                "pid": int(profile_id),
            },
        ).first()
        if row:
            person_id = str(row[0])
            player_id_map[int(profile_id)] = person_id
            return person_id
    logger.warning("coach insert failed (slug collision) profile_id=%s name=%s", profile_id, canonical)
    return None


def populate_team_lists(
    db: Session,
    *,
    seasons: list[int] | None = None,
    competition: int = 111,
) -> dict[str, Any]:
    team_map = _build_team_id_map(db)
    match_map = _build_match_id_map(db, seasons)
    player_map = _build_player_id_map(db)
    logger.info(
        "phase_team_lists: lookups — %d teams, %d matches, %d players",
        len(team_map), len(match_map), len(player_map),
    )

    keys = list_keys(f"scout/nrlcom/match-centre/{competition}/")
    if seasons:
        season_strs = {f"/{s}/" for s in seasons}
        keys = [k for k in keys if any(s in k for s in season_strs)]
    logger.info("phase_team_lists: %d match-centre archives to scan", len(keys))

    archives_read = 0
    archives_failed = 0
    rows_inserted = 0
    rows_already_present = 0
    coaches_inserted = 0
    coaches_already_present = 0
    players_no_match = 0
    matches_unmatched = 0

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

        for side in ("homeTeam", "awayTeam"):
            team_block = payload.get(side) or {}
            nrl_team_id = team_block.get("teamId")
            team_id = team_map.get(int(nrl_team_id)) if nrl_team_id else None
            if not team_id:
                continue
            captain_id = team_block.get("captainPlayerId")

            for p in team_block.get("players") or []:
                nrlcom_player_id = p.get("playerId")
                if not nrlcom_player_id:
                    continue
                person_id = player_map.get(int(nrlcom_player_id))
                if not person_id:
                    players_no_match += 1
                    continue
                jersey = p.get("number")
                position = p.get("position")
                is_captain = bool(captain_id and int(captain_id) == int(nrlcom_player_id))

                existing = db.execute(
                    text("""
                        SELECT 1 FROM match_team_lists
                        WHERE match_id = :match_id
                          AND team_id = :team_id
                          AND player_id = :player_id
                          AND list_version = 1
                    """),
                    {"match_id": match_id, "team_id": team_id, "player_id": person_id},
                ).first()
                if existing:
                    rows_already_present += 1
                    continue
                db.execute(
                    text("""
                        INSERT INTO match_team_lists (
                            match_id, team_id, player_id, jersey_number,
                            named_position, list_version, status, source, is_captain
                        )
                        VALUES (
                            :match_id, :team_id, :player_id, :jersey,
                            :position, 1, 'named', 'nrl_com', :is_captain
                        )
                    """),
                    {
                        "match_id": match_id, "team_id": team_id, "player_id": person_id,
                        "jersey": jersey, "position": position, "is_captain": is_captain,
                    },
                )
                rows_inserted += 1

            for c in team_block.get("coaches") or []:
                person_id = _ensure_coach_person(db, coach=c, player_id_map=player_map)
                if not person_id:
                    continue
                role = (c.get("position") or "Coach").strip()
                existing = db.execute(
                    text("""
                        SELECT 1 FROM match_team_lists
                        WHERE match_id = :match_id
                          AND team_id = :team_id
                          AND player_id = :player_id
                          AND list_version = 1
                          AND named_position = :role
                    """),
                    {
                        "match_id": match_id, "team_id": team_id,
                        "player_id": person_id, "role": role,
                    },
                ).first()
                if existing:
                    coaches_already_present += 1
                    continue
                db.execute(
                    text("""
                        INSERT INTO match_team_lists (
                            match_id, team_id, player_id, jersey_number,
                            named_position, list_version, status, source, is_captain
                        )
                        VALUES (
                            :match_id, :team_id, :player_id, NULL,
                            :role, 1, 'named', 'nrl_com', FALSE
                        )
                    """),
                    {
                        "match_id": match_id, "team_id": team_id,
                        "player_id": person_id, "role": role,
                    },
                )
                coaches_inserted += 1

    db.commit()
    logger.info(
        "phase_team_lists: rows_inserted=%d already=%d coaches_inserted=%d coaches_already=%d "
        "players_no_match=%d matches_unmatched=%d",
        rows_inserted, rows_already_present, coaches_inserted, coaches_already_present,
        players_no_match, matches_unmatched,
    )
    return {
        "archives_read": archives_read,
        "archives_failed": archives_failed,
        "rows_inserted": rows_inserted,
        "rows_already_present": rows_already_present,
        "coaches_inserted": coaches_inserted,
        "coaches_already_present": coaches_already_present,
        "players_no_match": players_no_match,
        "matches_unmatched": matches_unmatched,
    }
