"""Phase 3 — auxiliary extractors.

  - populate_team_standings:   scout/nrlcom/ladder/* → team_standings
  - populate_stat_leaderboards: scout/nrlcom/stats/* → stat_leaderboards
  - populate_injuries:         scout/nrlcom/casualty-ward/* → injuries

All three are independent — they run in one pass per archive set, but the
top-level driver runs each in its own DB transaction so a failure in one
doesn't block the others.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ._s3_walk import list_keys, read_json_concurrent

logger = logging.getLogger(__name__)


_LADDER_KEY_RE = re.compile(r"scout/nrlcom/ladder/(?P<comp>\d+)/(?P<season>\d{4})/round-(?P<round>\d+)\.json$")
_STATS_KEY_RE = re.compile(r"scout/nrlcom/stats/(?P<comp>\d+)/(?P<season>\d{4})\.json$")
_CASUALTY_KEY_RE = re.compile(r"scout/nrlcom/casualty-ward/(?P<comp>\d+)/(?P<date>\d{8})\.json$")

_EXPECTED_RETURN_RE = re.compile(r"Round\s+(\d+)", re.IGNORECASE)


def _bucket_status(return_text: str, current_round: int | None = None) -> str:
    """Map nrl.com `expectedReturn` text to the injuries.status enum.

    Allowed: 'training', 'test', '1_week', '2_4_weeks', '4_8_weeks',
             'indefinite', 'season', 'suspended', 'cleared'
    """
    t = (return_text or "").lower().strip()
    if "indefinite" in t or "tbc" in t:
        return "indefinite"
    if "next season" in t or "season" in t:
        return "season"
    if "training" in t:
        return "training"
    if "test" in t:
        return "test"
    m = _EXPECTED_RETURN_RE.search(t)
    if m and current_round is not None:
        gap = max(0, int(m.group(1)) - current_round)
        if gap <= 1:
            return "1_week"
        if gap <= 4:
            return "2_4_weeks"
        return "4_8_weeks"
    if m:
        # Round-N without a known current round — assume mid-term
        return "2_4_weeks"
    return "indefinite"


def _build_team_nick_map(db: Session) -> dict[str, str]:
    """Lower-cased team nickname → team_id (str)."""
    rows = db.execute(text(
        "SELECT team_id, slug, short_name, aliases FROM teams WHERE grade='nrl'"
    )).fetchall()
    out: dict[str, str] = {}
    for tid, slug, short, aliases in rows:
        tid_s = str(tid)
        out[(slug or "").lower()] = tid_s
        if short:
            out[short.lower()] = tid_s
        for a in (aliases or []):
            out[a.lower()] = tid_s
    return out


def _build_player_id_map(db: Session) -> dict[int, str]:
    rows = db.execute(text(
        "SELECT person_id, nrlcom_player_id FROM people WHERE nrlcom_player_id IS NOT NULL"
    )).fetchall()
    return {nid: str(pid) for pid, nid in rows}


# ─────────────────────────────────────────────────────────────────────────
# team_standings
# ─────────────────────────────────────────────────────────────────────────

def populate_team_standings(
    db: Session,
    *,
    competition: int = 111,
) -> dict[str, Any]:
    team_map = _build_team_nick_map(db)
    keys = list_keys(f"scout/nrlcom/ladder/{competition}/")
    logger.info("phase_standings: %d ladder archives to scan", len(keys))

    upsert_sql = text("""
        INSERT INTO team_standings (
            team_id, nrlcom_team_nickname, competition, season, round,
            ladder_position, movement, played, wins, lost, drawn, byes,
            points, points_for, points_against, points_difference, bonus_points,
            form, streak, home_record, away_record, day_record, night_record,
            average_winning_margin, average_losing_margin, close_games,
            golden_point, players_used, odds, raw_payload, s3_archive_key
        )
        VALUES (
            :team_id, :nrlcom_team_nickname, :competition, :season, :round,
            :ladder_position, :movement, :played, :wins, :lost, :drawn, :byes,
            :points, :points_for, :points_against, :points_difference, :bonus_points,
            :form, :streak, :home_record, :away_record, :day_record, :night_record,
            :average_winning_margin, :average_losing_margin, :close_games,
            :golden_point, :players_used, :odds, CAST(:raw_payload AS JSONB), :s3_archive_key
        )
        ON CONFLICT (nrlcom_team_nickname, competition, season, round)
        DO UPDATE SET
            team_id = COALESCE(EXCLUDED.team_id, team_standings.team_id),
            ladder_position = EXCLUDED.ladder_position,
            movement = EXCLUDED.movement,
            played = EXCLUDED.played, wins = EXCLUDED.wins, lost = EXCLUDED.lost,
            drawn = EXCLUDED.drawn, byes = EXCLUDED.byes,
            points = EXCLUDED.points, points_for = EXCLUDED.points_for,
            points_against = EXCLUDED.points_against, points_difference = EXCLUDED.points_difference,
            bonus_points = EXCLUDED.bonus_points,
            form = EXCLUDED.form, streak = EXCLUDED.streak,
            home_record = EXCLUDED.home_record, away_record = EXCLUDED.away_record,
            day_record = EXCLUDED.day_record, night_record = EXCLUDED.night_record,
            average_winning_margin = EXCLUDED.average_winning_margin,
            average_losing_margin = EXCLUDED.average_losing_margin,
            close_games = EXCLUDED.close_games, golden_point = EXCLUDED.golden_point,
            players_used = EXCLUDED.players_used, odds = EXCLUDED.odds,
            raw_payload = EXCLUDED.raw_payload,
            updated_at = NOW()
        RETURNING (xmax = 0) AS inserted
    """)

    inserted = 0
    updated = 0
    archives_read = 0
    archives_failed = 0
    for key, payload, err in read_json_concurrent(keys, max_workers=16):
        if err is not None or payload is None:
            archives_failed += 1
            continue
        archives_read += 1
        m = _LADDER_KEY_RE.search(key)
        if not m:
            continue
        season = int(m.group("season"))
        round_no = int(m.group("round"))

        for idx, pos in enumerate(payload.get("positions") or [], start=1):
            stats = pos.get("stats") or {}
            nick = pos.get("teamNickname") or ""
            team_id = team_map.get(nick.lower())
            # 'next' isn't part of the schema; 'odds' lives in stats.odds for some seasons.
            row = {
                "team_id": team_id,
                "nrlcom_team_nickname": nick,
                "competition": competition,
                "season": season,
                "round": round_no,
                "ladder_position": pos.get("position") or idx,
                "movement": pos.get("movement"),
                "played": stats.get("played"),
                "wins": stats.get("wins"),
                "lost": stats.get("lost"),
                "drawn": stats.get("drawn"),
                "byes": stats.get("byes"),
                "points": stats.get("points"),
                "points_for": stats.get("points for"),
                "points_against": stats.get("points against"),
                "points_difference": stats.get("points difference"),
                "bonus_points": stats.get("bonus points"),
                "form": stats.get("form"),
                "streak": stats.get("streak"),
                "home_record": stats.get("home record"),
                "away_record": stats.get("away record"),
                "day_record": stats.get("day record"),
                "night_record": stats.get("night record"),
                "average_winning_margin": stats.get("average winning margin"),
                "average_losing_margin": stats.get("average losing margin"),
                "close_games": stats.get("close games"),
                "golden_point": stats.get("golden point"),
                "players_used": stats.get("players used"),
                "odds": stats.get("odds"),
                "raw_payload": json.dumps(pos, default=str),
                "s3_archive_key": key,
            }
            res = db.execute(upsert_sql, row)
            if res.scalar():
                inserted += 1
            else:
                updated += 1

    db.commit()
    logger.info("phase_standings: inserted=%d updated=%d", inserted, updated)
    return {
        "archives_read": archives_read,
        "archives_failed": archives_failed,
        "rows_inserted": inserted,
        "rows_updated": updated,
    }


# ─────────────────────────────────────────────────────────────────────────
# stat_leaderboards
# ─────────────────────────────────────────────────────────────────────────

def populate_stat_leaderboards(
    db: Session,
    *,
    competition: int = 111,
) -> dict[str, Any]:
    team_map = _build_team_nick_map(db)
    player_map = _build_player_id_map(db)
    keys = list_keys(f"scout/nrlcom/stats/{competition}/")
    logger.info("phase_leaderboards: %d stats archives to scan", len(keys))

    upsert_sql = text("""
        INSERT INTO stat_leaderboards (
            competition, season, scope, category, subgroup, stat_id, stat_title,
            leader_position, leader_first_name, leader_last_name,
            leader_team_nickname, leader_value, person_id, team_id,
            raw_payload, s3_archive_key, captured_at
        )
        VALUES (
            :competition, :season, :scope, :category, :subgroup, :stat_id, :stat_title,
            :leader_position, :leader_first_name, :leader_last_name,
            :leader_team_nickname, :leader_value, :person_id, :team_id,
            CAST(:raw_payload AS JSONB), :s3_archive_key, NOW()
        )
        ON CONFLICT (competition, season, scope, category, subgroup, stat_title, leader_position)
        DO UPDATE SET
            stat_id = EXCLUDED.stat_id,
            leader_first_name = EXCLUDED.leader_first_name,
            leader_last_name = EXCLUDED.leader_last_name,
            leader_team_nickname = EXCLUDED.leader_team_nickname,
            leader_value = EXCLUDED.leader_value,
            person_id = COALESCE(EXCLUDED.person_id, stat_leaderboards.person_id),
            team_id = COALESCE(EXCLUDED.team_id, stat_leaderboards.team_id),
            raw_payload = EXCLUDED.raw_payload,
            captured_at = NOW()
        RETURNING (xmax = 0) AS inserted
    """)

    inserted = 0
    updated = 0
    archives_read = 0
    archives_failed = 0

    for key, payload, err in read_json_concurrent(keys, max_workers=8):
        if err is not None or payload is None:
            archives_failed += 1
            continue
        archives_read += 1
        m = _STATS_KEY_RE.search(key)
        if not m:
            continue
        season = int(m.group("season"))

        for scope_key, scope_block in (("player", payload.get("playerStats") or []),
                                       ("team", payload.get("teamStats") or [])):
            for category_block in scope_block:
                category = category_block.get("title") or ""
                for subgroup_block in category_block.get("groups") or []:
                    subgroup_title = subgroup_block.get("title") or ""
                    stat_id = subgroup_block.get("statId")
                    leaders = subgroup_block.get("leaders") or []
                    for pos_idx, leader in enumerate(leaders, start=1):
                        try:
                            value = float(leader.get("value")) if leader.get("value") not in (None, "") else None
                        except (TypeError, ValueError):
                            value = None
                        nick = leader.get("teamNickName") or leader.get("teamName") or ""
                        team_id = team_map.get(nick.lower())
                        person_id = None
                        if scope_key == "player":
                            pid = leader.get("playerId")
                            if pid:
                                person_id = player_map.get(int(pid))
                        row = {
                            "competition": competition,
                            "season": season,
                            "scope": scope_key,
                            "category": category,
                            "subgroup": subgroup_title,
                            "stat_id": stat_id,
                            "stat_title": subgroup_title,
                            "leader_position": pos_idx,
                            "leader_first_name": leader.get("firstName"),
                            "leader_last_name": leader.get("lastName"),
                            "leader_team_nickname": nick,
                            "leader_value": value,
                            "person_id": person_id,
                            "team_id": team_id,
                            "raw_payload": json.dumps(leader, default=str),
                            "s3_archive_key": key,
                        }
                        res = db.execute(upsert_sql, row)
                        if res.scalar():
                            inserted += 1
                        else:
                            updated += 1

    db.commit()
    logger.info("phase_leaderboards: inserted=%d updated=%d", inserted, updated)
    return {
        "archives_read": archives_read,
        "archives_failed": archives_failed,
        "rows_inserted": inserted,
        "rows_updated": updated,
    }


# ─────────────────────────────────────────────────────────────────────────
# injuries (state machine over daily casualty snapshots)
# ─────────────────────────────────────────────────────────────────────────

def _build_people_name_lookup(db: Session) -> dict[tuple[str, str], str]:
    """(canonical_name_lower, team_nickname_lower) → person_id.

    Falls back to name-only when team unknown.
    """
    rows = db.execute(text("""
        SELECT p.person_id, p.canonical_name, p.aliases, t.short_name, t.slug
        FROM people p
        LEFT JOIN player_attributes pa
            ON pa.person_id = p.person_id AND pa.effective_to IS NULL
        LEFT JOIN teams t ON t.team_id = pa.team_id
    """)).fetchall()
    lookup: dict[tuple[str, str], str] = {}
    for person_id, canonical_name, aliases, short_name, slug in rows:
        pid_s = str(person_id)
        team_keys: list[str] = ["", (short_name or "").lower(), (slug or "").lower()]
        for n in [canonical_name, *(aliases or [])]:
            if not n:
                continue
            for tk in team_keys:
                lookup.setdefault((n.lower(), tk), pid_s)
    return lookup


def populate_injuries(
    db: Session,
    *,
    competition: int = 111,
) -> dict[str, Any]:
    team_map = _build_team_nick_map(db)
    people_lookup = _build_people_name_lookup(db)
    keys = sorted(list_keys(f"scout/nrlcom/casualty-ward/{competition}/"))
    logger.info("phase_injuries: %d casualty snapshots to scan", len(keys))

    archives_read = 0
    archives_failed = 0
    inserted = 0
    resolved = 0

    # State machine: walk snapshots chronologically. For each (player, team)
    # currently in casualty: ensure an open injury row exists. For each
    # previously-open injury not in today's snapshot: close it (resolved_at).

    for key in keys:
        payload, err = None, None
        try:
            from ._s3_walk import read_json
            payload = read_json(key)
        except Exception as e:  # noqa: BLE001
            err = e
        if err is not None or payload is None:
            archives_failed += 1
            continue
        archives_read += 1

        m = _CASUALTY_KEY_RE.search(key)
        if not m:
            continue
        snap_date = datetime.strptime(m.group("date"), "%Y%m%d").replace(tzinfo=timezone.utc)

        casualties = payload.get("casualties") or []
        seen_keys_today: set[tuple[str, str]] = set()
        for c in casualties:
            fn = (c.get("firstName") or "").strip()
            ln = (c.get("lastName") or "").strip()
            nick = (c.get("teamNickname") or "").strip()
            if not (fn or ln) or not nick:
                continue
            canonical = f"{fn} {ln}".strip()
            team_id = team_map.get(nick.lower())
            person_id = (
                people_lookup.get((canonical.lower(), nick.lower()))
                or people_lookup.get((canonical.lower(), ""))
            )
            return_text = (c.get("expectedReturn") or "").strip()
            ret_round = None
            mr = _EXPECTED_RETURN_RE.search(return_text)
            if mr:
                ret_round = int(mr.group(1))

            key_today = (canonical.lower(), nick.lower())
            seen_keys_today.add(key_today)

            # Is there already an open injury for this (player, team)?
            existing = db.execute(
                text("""
                    SELECT injury_id FROM injuries
                    WHERE COALESCE(player_id::text, '') = COALESCE(:pid, '')
                      AND COALESCE(team_id::text, '') = COALESCE(:tid, '')
                      AND description = :desc
                      AND resolved_at IS NULL
                """),
                {"pid": person_id, "tid": team_id, "desc": canonical},
            ).first()
            if existing:
                # Update expected return if changed
                db.execute(
                    text("""
                        UPDATE injuries
                        SET expected_return_round = :rr,
                            metadata_json = metadata_json
                                || jsonb_build_object('expected_return_text', :text,
                                                      'last_seen_snapshot', :snap)
                        WHERE injury_id = :iid
                    """),
                    {
                        "rr": ret_round,
                        "text": return_text,
                        "snap": snap_date.isoformat(),
                        "iid": existing[0],
                    },
                )
            else:
                # Determine current-round context from any open match in this season.
                current_round_row = db.execute(
                    text("""
                        SELECT MAX(round) FROM matches
                        WHERE season = :season AND kickoff_at <= :snap
                    """),
                    {"season": snap_date.year, "snap": snap_date},
                ).first()
                current_round = current_round_row[0] if current_round_row else None
                status = _bucket_status(return_text, current_round)

                db.execute(
                    text("""
                        INSERT INTO injuries (
                            team_id, player_id, status, body_part, description,
                            expected_return_round, reported_at, source, source_url,
                            metadata_json
                        )
                        VALUES (
                            :tid, :pid, :status, :body_part, :desc,
                            :rr, :snap, 'nrl.com/casualty-ward', :url,
                            CAST(:meta AS JSONB)
                        )
                    """),
                    {
                        "tid": team_id,
                        "pid": person_id,
                        "status": status,
                        "body_part": c.get("injury"),
                        "desc": canonical,
                        "rr": ret_round,
                        "snap": snap_date,
                        "url": c.get("url"),
                        "meta": json.dumps({
                            "expected_return_text": return_text,
                            "first_snapshot": snap_date.isoformat(),
                            "last_seen_snapshot": snap_date.isoformat(),
                            "team_nickname": nick,
                        }),
                    },
                )
                inserted += 1

        # Resolve previously-open injuries not present in this snapshot.
        # Fetch all open injuries reported before this snapshot, then close
        # those whose (name, team_nick) key isn't in today's set. Doing the
        # difference in Python keeps the SQL simple.
        open_rows = db.execute(
            text("""
                SELECT injury_id, LOWER(description) AS name,
                       LOWER(COALESCE(metadata_json->>'team_nickname','')) AS nick
                FROM injuries
                WHERE resolved_at IS NULL
                  AND reported_at < :snap
                  AND source = 'nrl.com/casualty-ward'
            """),
            {"snap": snap_date},
        ).fetchall()
        to_resolve = [
            r.injury_id for r in open_rows
            if (r.name, r.nick) not in seen_keys_today
        ]
        if to_resolve:
            db.execute(
                text("UPDATE injuries SET resolved_at = :snap WHERE injury_id = ANY(:ids)"),
                {"snap": snap_date, "ids": to_resolve},
            )
            resolved += len(to_resolve)

    db.commit()
    logger.info("phase_injuries: inserted=%d resolved=%d", inserted, resolved)
    return {
        "archives_read": archives_read,
        "archives_failed": archives_failed,
        "injuries_inserted": inserted,
        "injuries_resolved": resolved,
    }
