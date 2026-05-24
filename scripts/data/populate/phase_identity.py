"""Phase 1 — backfill people.nrlcom_player_id and teams.nrlcom_team_id.

Walks scout/nrlcom/match-centre/ for 2024-2026 and harvests
(firstName, lastName, teamNickName, playerId) tuples from every roster.
Matches against canonical_name + current team_id (via SCD-2 attributes)
to populate the nrl.com IDs onto our existing people/teams rows.

This must run before extract_match_team_lists / extract_player_match_stats
so those downstream extractors can JOIN on people.nrlcom_player_id without
fragile name matching.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ._s3_walk import list_keys, read_json_concurrent

logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    """Lowercase, strip diacritics-light, collapse whitespace.

    Used only for matching — never written back to the DB.
    """
    n = (name or "").lower().strip()
    # Replace common punctuation with single space
    n = re.sub(r"[^a-z0-9\s'-]+", " ", n)
    n = re.sub(r"\s+", " ", n)
    return n


def _team_nickname_to_slug(nickname: str) -> str:
    """Best-effort map from nrl.com nickName to our teams.slug.

    nrl.com nickNames: Roosters, Rabbitohs, Wests Tigers, Sea Eagles, etc.
    Our slugs: roosters, rabbitohs, wests-tigers, sea-eagles, etc.
    """
    return (nickname or "").lower().replace(" ", "-").strip("-")


def _build_team_lookup(db: Session) -> dict[str, str]:
    """Map normalized team identifiers to teams.team_id (str)."""
    rows = db.execute(text(
        "SELECT team_id, slug, short_name, aliases FROM teams WHERE grade='nrl'"
    )).fetchall()
    lookup: dict[str, str] = {}
    for team_id, slug, short_name, aliases in rows:
        team_id_s = str(team_id)
        lookup[_normalize_name(slug)] = team_id_s
        if short_name:
            lookup[_normalize_name(short_name)] = team_id_s
        for a in (aliases or []):
            lookup[_normalize_name(a)] = team_id_s
    return lookup


def _build_people_lookup(db: Session) -> dict[tuple[str, str], str]:
    """Map (normalized_name, team_id_str) → person_id (str).

    Uses current SCD-2 attributes (effective_to IS NULL) to scope each
    person to their current team. Players who have moved are findable
    against their *current* team, which matches the 2025/2026
    match-centre rosters we're harvesting from.

    Falls back to a name-only key for people without an active team
    record (coaches, advisors, retired).
    """
    rows = db.execute(text("""
        SELECT
            p.person_id,
            p.canonical_name,
            p.aliases,
            pa.team_id
        FROM people p
        LEFT JOIN player_attributes pa
            ON pa.person_id = p.person_id
            AND pa.effective_to IS NULL
    """)).fetchall()
    lookup: dict[tuple[str, str], str] = {}
    for person_id, canonical_name, aliases, team_id in rows:
        pid_s = str(person_id)
        team_key = str(team_id) if team_id else ""
        for n in [canonical_name, *(aliases or [])]:
            if n:
                lookup[(_normalize_name(n), team_key)] = pid_s
                # Also store name-only fallback under empty team key —
                # last writer wins, which is fine for unambiguous names.
                lookup.setdefault((_normalize_name(n), ""), pid_s)
    return lookup


def _harvest_player_tuples(
    match_data: dict[str, Any],
) -> list[tuple[str, str, int]]:
    """Pull (player_full_name, team_nickname, playerId) from one match-centre archive."""
    out: list[tuple[str, str, int]] = []
    for side in ("homeTeam", "awayTeam"):
        team = match_data.get(side) or {}
        nick = team.get("nickName", "")
        for p in team.get("players") or []:
            fn = (p.get("firstName") or "").strip()
            ln = (p.get("lastName") or "").strip()
            pid = p.get("playerId")
            if fn and ln and pid:
                out.append((f"{fn} {ln}", nick, int(pid)))
    return out


def _harvest_team_tuples(
    match_data: dict[str, Any],
) -> list[tuple[str, int]]:
    """Pull (team_nickname, teamId) from one match-centre archive."""
    out: list[tuple[str, int]] = []
    for side in ("homeTeam", "awayTeam"):
        team = match_data.get(side) or {}
        nick = team.get("nickName", "")
        tid = team.get("teamId")
        if nick and tid:
            out.append((nick, int(tid)))
    return out


def backfill_identity(
    db: Session,
    *,
    seasons: list[int] = (2024, 2025, 2026),
    competition: int = 111,
    commit: bool = True,
) -> dict[str, Any]:
    """Walk match-centre archives → set people.nrlcom_player_id, teams.nrlcom_team_id.

    Idempotent — re-runs only update rows where the column is currently NULL
    or where the existing value differs (UPSERT semantics via UPDATE).
    """
    team_lookup = _build_team_lookup(db)
    people_lookup = _build_people_lookup(db)
    logger.info(
        "phase_identity: lookup built — %d team aliases, %d people keys",
        len(team_lookup), len(people_lookup),
    )

    # Collect candidate keys
    all_keys: list[str] = []
    for s in seasons:
        keys = list_keys(f"scout/nrlcom/match-centre/{competition}/{s}/")
        logger.info("phase_identity: %d archives in season %d", len(keys), s)
        all_keys.extend(keys)
    logger.info("phase_identity: %d total match-centre archives to scan", len(all_keys))

    # Build distinct tuples across all archives
    player_tuples: dict[tuple[str, str], int] = {}  # (norm_name, norm_team_nick) → playerId
    team_tuples: dict[str, int] = {}  # norm_team_nick → teamId
    archives_read = 0
    archives_failed = 0
    for key, payload, err in read_json_concurrent(all_keys, max_workers=16):
        if err is not None or payload is None:
            archives_failed += 1
            continue
        archives_read += 1
        for fullname, nick, pid in _harvest_player_tuples(payload):
            player_tuples[(_normalize_name(fullname), _normalize_name(nick))] = pid
        for nick, tid in _harvest_team_tuples(payload):
            team_tuples[_normalize_name(nick)] = tid

    logger.info(
        "phase_identity: harvested %d distinct players, %d distinct teams from %d archives (%d failed)",
        len(player_tuples), len(team_tuples), archives_read, archives_failed,
    )

    # Backfill teams.nrlcom_team_id
    teams_updated = 0
    for nick_norm, tid in team_tuples.items():
        team_id = team_lookup.get(nick_norm) or team_lookup.get(_team_nickname_to_slug(nick_norm))
        if not team_id:
            logger.debug("phase_identity: no team match for nickname=%s", nick_norm)
            continue
        res = db.execute(
            text("""
                UPDATE teams
                SET nrlcom_team_id = :tid
                WHERE team_id = :team_id
                  AND (nrlcom_team_id IS NULL OR nrlcom_team_id <> :tid)
            """),
            {"tid": tid, "team_id": team_id},
        )
        teams_updated += res.rowcount or 0

    # Backfill people.nrlcom_player_id
    # Two safeguards against unique-violation on nrlcom_player_id:
    #   1. Build a first-match-wins map (person_id → pid). If a person matches
    #      multiple (name, team) tuples, the first one wins; later ones are
    #      logged.
    #   2. SQL guard: skip the UPDATE if any other row already has this pid.
    people_updated = 0
    people_unmatched: list[tuple[str, str, int]] = []
    people_skipped_collision: list[tuple[str, int, int]] = []  # (person_id, pid_attempted, pid_existing)
    chosen: dict[str, int] = {}
    for (name_norm, nick_norm), pid in player_tuples.items():
        team_id = team_lookup.get(nick_norm) or team_lookup.get(_team_nickname_to_slug(nick_norm)) or ""
        person_id = (
            people_lookup.get((name_norm, team_id))
            or people_lookup.get((name_norm, ""))
        )
        if not person_id:
            people_unmatched.append((name_norm, nick_norm, pid))
            continue
        existing = chosen.get(person_id)
        if existing is not None and existing != pid:
            people_skipped_collision.append((person_id, pid, existing))
            continue
        chosen[person_id] = pid

    for person_id, pid in chosen.items():
        res = db.execute(
            text("""
                UPDATE people
                SET nrlcom_player_id = :pid
                WHERE person_id = :person_id
                  AND (nrlcom_player_id IS DISTINCT FROM :pid)
                  AND NOT EXISTS (
                      SELECT 1 FROM people
                      WHERE nrlcom_player_id = :pid AND person_id <> :person_id
                  )
            """),
            {"pid": pid, "person_id": person_id},
        )
        people_updated += res.rowcount or 0

    if commit: db.commit()

    logger.info(
        "phase_identity: teams_updated=%d  people_updated=%d  unmatched=%d  collisions=%d",
        teams_updated, people_updated, len(people_unmatched), len(people_skipped_collision),
    )
    if people_unmatched[:5]:
        logger.info(
            "phase_identity: first 5 unmatched players (likely historical-only): %s",
            people_unmatched[:5],
        )
    if people_skipped_collision[:5]:
        logger.info(
            "phase_identity: first 5 collision skips (likely same person, multiple rows): %s",
            people_skipped_collision[:5],
        )

    return {
        "archives_read": archives_read,
        "archives_failed": archives_failed,
        "distinct_players_seen": len(player_tuples),
        "distinct_teams_seen": len(team_tuples),
        "teams_updated": teams_updated,
        "people_updated": people_updated,
        "people_unmatched": len(people_unmatched),
        "people_collisions": len(people_skipped_collision),
        "unmatched_sample": people_unmatched[:10],
        "collision_sample": people_skipped_collision[:10],
    }
