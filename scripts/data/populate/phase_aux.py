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


def _scrub_nuls(value: Any) -> Any:
    """Recursively strip NULL bytes from strings inside nested structures.

    Postgres TEXT columns reject embedded NULL bytes server-side; Postgres
    JSONB also rejects the JSON escape form (backslash u followed by four
    zeros) that json.dumps emits when it encounters a NULL char in a string.
    Historical nrl.com payloads occasionally carry them (observed in 1999
    ladder `streak` field). Stripping NULL bytes from the source dict before
    json.dumps means the resulting JSON has no such escape and the JSONB
    cast succeeds.
    """
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return {k: _scrub_nuls(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_nuls(v) for v in value]
    return value


def _strip_nuls(row: dict[str, Any]) -> dict[str, Any]:
    """Top-level NULL-byte scrub for an upsert row dict.

    Delegates to :func:`_scrub_nuls` so nested values inside json-dumped
    payloads are also covered. The JSONB cast at the upsert site rejects
    the NULL-byte JSON escape, so the source dict must be scrubbed before
    json.dumps emits any.
    """
    return _scrub_nuls(row)


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

def _extract_standing_rows(
    payload: dict[str, Any],
    *,
    key: str,
    competition: int,
    season: int,
    round_no: int,
    team_map: dict[str, str],
) -> list[dict[str, Any]]:
    """Pure projection of one /ladder/data archive into team_standings rows.

    One row per `positions[]` entry. No DB, no I/O — the caller UPSERTs the
    returned dicts. `ladder_position` falls back to the 1-based enumerate
    index when the upstream omits `position` (it does today). The 22 metrics
    are read from the space-keyed `stats` object exactly as the upsert binds.
    """
    rows: list[dict[str, Any]] = []
    for idx, pos in enumerate(payload.get("positions") or [], start=1):
        # Scrub the source dict first so the raw_payload json.dumps below
        # doesn't emit any embedded NULL-byte escapes (Postgres JSONB
        # rejects them).
        pos = _scrub_nuls(pos)
        stats = pos.get("stats") or {}
        nick = pos.get("teamNickname") or ""
        team_id = team_map.get(nick.lower())
        rows.append(_strip_nuls({
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
        }))
    return rows


def populate_team_standings(
    db: Session,
    *,
    competition: int = 111,
    commit: bool = True,
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

        for row in _extract_standing_rows(
            payload,
            key=key,
            competition=competition,
            season=season,
            round_no=round_no,
            team_map=team_map,
        ):
            res = db.execute(upsert_sql, row)
            if res.scalar():
                inserted += 1
            else:
                updated += 1

    if commit: db.commit()
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

def _extract_leader_rows(
    payload: dict[str, Any],
    *,
    key: str,
    competition: int,
    season: int,
    team_map: dict[str, str],
    player_map: dict[int, str],
) -> list[dict[str, Any]]:
    """Pure projection of one /stats/data archive into stat_leaderboards rows.

    Walks both `playerStats[]` and `teamStats[]` blocks and flattens
    `<scope>Stats[].groups[].leaders[]` into one row per leader. No DB, no
    I/O — the caller UPSERTs the returned dicts.

    The `leader_value` float-coercion (string-or-None → float-or-None with
    `""` → None and unparseable → None), the team_nickname lower-case
    lookup via `team_map`, the `teamName` fallback when `teamNickName` is
    missing, and the `playerId → person_id` lookup via `player_map` (only
    for `scope='player'`) all live here. `raw_payload` is the full leader
    JSON dump preserved per-row.
    """
    rows: list[dict[str, Any]] = []
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
                    rows.append({
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
                    })
    return rows


def populate_stat_leaderboards(
    db: Session,
    *,
    competition: int = 111,
    commit: bool = True,
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

        for row in _extract_leader_rows(
            payload,
            key=key,
            competition=competition,
            season=season,
            team_map=team_map,
            player_map=player_map,
        ):
            res = db.execute(upsert_sql, row)
            if res.scalar():
                inserted += 1
            else:
                updated += 1

    if commit: db.commit()
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


def _casualty_to_row(
    c: dict[str, Any],
    *,
    team_map: dict[str, str],
    people_lookup: dict[tuple[str, str], str],
) -> dict[str, Any] | None:
    """Pure projection of one casualty entry into the derived fields the
    injuries state machine works with. No DB, no I/O.

    Returns ``None`` for a skip (no name, or no team nickname) — exactly the
    original inner-loop guard. The `status` is intentionally NOT computed here
    (it depends on the current-round DB lookup); the caller derives it via
    `_bucket_status`. The returned `key_today` is the (name, nick) dedup key
    the state machine adds to today's seen-set.
    """
    fn = (c.get("firstName") or "").strip()
    ln = (c.get("lastName") or "").strip()
    nick = (c.get("teamNickname") or "").strip()
    if not (fn or ln) or not nick:
        return None
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
    return {
        "canonical": canonical,
        "team_nickname": nick,
        "team_id": team_id,
        "person_id": person_id,
        "body_part": c.get("injury"),
        "expected_return_text": return_text,
        "expected_return_round": ret_round,
        "url": c.get("url"),
        "key_today": (canonical.lower(), nick.lower()),
    }


def populate_injuries(
    db: Session,
    *,
    competition: int = 111,
    commit: bool = True,
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
            parsed = _casualty_to_row(c, team_map=team_map, people_lookup=people_lookup)
            if parsed is None:
                continue
            canonical = parsed["canonical"]
            nick = parsed["team_nickname"]
            team_id = parsed["team_id"]
            person_id = parsed["person_id"]
            return_text = parsed["expected_return_text"]
            ret_round = parsed["expected_return_round"]

            seen_keys_today.add(parsed["key_today"])

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
                # Update expected return if changed. Build the jsonb patch in
                # Python and merge with `||` — same pattern the INSERT below
                # uses for `metadata_json` (`CAST(:meta AS JSONB)`). The
                # alternative — `jsonb_build_object(...)` with bound `:text` /
                # `:snap` — fails on psycopg under prepared-statement binding
                # because variadic `"any"` can't infer parameter types
                # (`could not determine data type of parameter $2`).
                db.execute(
                    text("""
                        UPDATE injuries
                        SET expected_return_round = :rr,
                            metadata_json = metadata_json || CAST(:patch AS JSONB)
                        WHERE injury_id = :iid
                    """),
                    {
                        "rr": ret_round,
                        "patch": json.dumps({
                            "expected_return_text": return_text,
                            "last_seen_snapshot": snap_date.isoformat(),
                        }),
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
                        "body_part": parsed["body_part"],
                        "desc": canonical,
                        "rr": ret_round,
                        "snap": snap_date,
                        "url": parsed["url"],
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

    if commit: db.commit()
    logger.info("phase_injuries: inserted=%d resolved=%d", inserted, resolved)
    return {
        "archives_read": archives_read,
        "archives_failed": archives_failed,
        "injuries_inserted": inserted,
        "injuries_resolved": resolved,
    }
