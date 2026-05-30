"""Phase 2d — extract player_match_stats from miner/nrlcom/match-centre/* archives.

One row per (match, player). Idempotent UPSERT on the
uq_player_match_stats_match_player unique index (nrlcom_match_id, nrlcom_player_id).

Mapping: nrl.com camelCase keys → migration 056 snake_case columns. The
upstream player block has 58 stat fields; we model all of them plus
jersey_number, position, is_on_field from the per-team players[] list
(joined back by playerId).

Forensic capture: the whole upstream player dict is stored under raw_payload
so any column we forget to map can be derived without re-fetching.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ._s3_walk import list_keys, read_json_concurrent

logger = logging.getLogger(__name__)


# camelCase upstream → snake_case column.
# Order doesn't matter functionally; grouped for review.
_FIELD_MAP: dict[str, str] = {
    # time
    "minutesPlayed": "minutes_played",
    "stintOne": "stint_one",
    # scoring
    "points": "points",
    "tries": "tries",
    "tryAssists": "try_assists",
    "conversions": "conversions",
    "conversionAttempts": "conversion_attempts",
    "goalConversionRate": "goal_conversion_rate",
    "goals": "goals",
    "penaltyGoals": "penalty_goals",
    "fieldGoals": "field_goals",
    "onePointFieldGoals": "one_point_field_goals",
    "twoPointFieldGoals": "two_point_field_goals",
    "fantasyPointsTotal": "fantasy_points_total",
    # run / attack
    "allRuns": "all_runs",
    "allRunMetres": "all_run_metres",
    "postContactMetres": "post_contact_metres",
    "hitUps": "hit_ups",
    "hitUpRunMetres": "hit_up_run_metres",
    "dummyHalfRuns": "dummy_half_runs",
    "dummyHalfRunMetres": "dummy_half_run_metres",
    "dummyPasses": "dummy_passes",
    "passes": "passes",
    "passesToRunRatio": "passes_to_run_ratio",
    "receipts": "receipts",
    "lineBreaks": "line_breaks",
    "lineBreakAssists": "line_break_assists",
    "tackleBreaks": "tackle_breaks",
    "lineEngagedRuns": "line_engaged_runs",
    # kicking
    "kicks": "kicks",
    "kickMetres": "kick_metres",
    "kickReturnMetres": "kick_return_metres",
    "kicksDefused": "kicks_defused",
    "kicksDead": "kicks_dead",
    "bombKicks": "bomb_kicks",
    "grubberKicks": "grubber_kicks",
    "crossFieldKicks": "cross_field_kicks",
    "forcedDropOutKicks": "forced_drop_out_kicks",
    "fortyTwentyKicks": "forty_twenty_kicks",
    "twentyFortyKicks": "twenty_forty_kicks",
    # defence
    "tacklesMade": "tackles_made",
    "missedTackles": "missed_tackles",
    "ineffectiveTackles": "ineffective_tackles",
    "tackleEfficiency": "tackle_efficiency",
    "intercepts": "intercepts",
    "offloads": "offloads",
    "oneOnOneSteal": "one_on_one_steal",
    "oneOnOneLost": "one_on_one_lost",
    "playTheBallTotal": "play_the_ball_total",
    "playTheBallAverageSpeed": "play_the_ball_average_speed",
    # discipline
    "handlingErrors": "handling_errors",
    "errors": "errors",
    "penalties": "penalties",
    "ruckInfringements": "ruck_infringements",
    "offsideWithinTenMetres": "offside_within_ten_metres",
    "sinBins": "sin_bins",
    "sendOffs": "send_offs",
    "onReport": "on_report",
}


def _build_team_id_map(db: Session) -> dict[int, str]:
    rows = db.execute(text(
        "SELECT team_id, nrlcom_team_id FROM teams WHERE nrlcom_team_id IS NOT NULL"
    )).fetchall()
    return {nid: str(tid) for tid, nid in rows}


def _build_match_id_map(db: Session, seasons: list[int] | None) -> dict[str, tuple[str, str]]:
    """external_match_id → (match_id, data_coverage). See phase_team_lists."""
    q = (
        "SELECT match_id, external_match_id, data_coverage "
        "FROM matches WHERE source='nrl_com' AND external_match_id IS NOT NULL"
    )
    if seasons:
        q += f" AND season IN ({','.join(str(s) for s in seasons)})"
    rows = db.execute(text(q)).fetchall()
    return {ext: (str(mid), dc) for mid, ext, dc in rows}


def _build_player_id_map(db: Session) -> dict[int, str]:
    rows = db.execute(text(
        "SELECT person_id, nrlcom_player_id FROM people WHERE nrlcom_player_id IS NOT NULL"
    )).fetchall()
    return {nid: str(pid) for pid, nid in rows}


def _build_player_meta_map(payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Build playerId → {jersey, position, is_on_field, team_side} from
    the team rosters in the match-centre archive.
    """
    meta: dict[int, dict[str, Any]] = {}
    for side in ("homeTeam", "awayTeam"):
        team = payload.get(side) or {}
        is_home = (side == "homeTeam")
        nrl_team_id = team.get("teamId")
        for p in team.get("players") or []:
            pid = p.get("playerId")
            if pid is None:
                continue
            meta[int(pid)] = {
                "jersey_number": p.get("number"),
                "position": p.get("position"),
                "is_on_field": p.get("isOnField"),
                "is_home": is_home,
                "nrlcom_team_id": int(nrl_team_id) if nrl_team_id else None,
            }
    return meta


def _extract_stat_rows(
    payload: dict[str, Any],
    key: str,
    match_id: str,
    team_map: dict[int, str],
    player_map: dict[int, str],
) -> list[dict[str, Any]]:
    """Pure projection of one match-centre archive into player_match_stats rows.

    One row per player in `stats.players.{homeTeam,awayTeam}[]`. Identity is
    resolved via the passed-in maps; jersey/position/on-field come from the
    roster meta (`_build_player_meta_map`). No S3, no DB — mirrors the
    `phase_matches._extract_one` template so it's unit-testable.
    """
    match_ext = str(payload.get("matchId") or "").strip()
    player_meta = _build_player_meta_map(payload)
    stats_block = (payload.get("stats") or {}).get("players") or {}

    rows: list[dict[str, Any]] = []
    for side_key in ("homeTeam", "awayTeam"):
        for s in stats_block.get(side_key) or []:
            nrlcom_player_id = s.get("playerId")
            if nrlcom_player_id is None:
                continue
            meta = player_meta.get(int(nrlcom_player_id)) or {}
            person_id = player_map.get(int(nrlcom_player_id))
            team_id = team_map.get(meta.get("nrlcom_team_id"))

            row = {
                "match_id": match_id,
                "nrlcom_match_id": match_ext,
                "nrlcom_player_id": int(nrlcom_player_id),
                "person_id": person_id,
                "team_id": team_id,
                "nrlcom_team_id": meta.get("nrlcom_team_id"),
                "is_home": meta.get("is_home", side_key == "homeTeam"),
                "jersey_number": meta.get("jersey_number"),
                "position": meta.get("position"),
                "is_on_field": meta.get("is_on_field"),
                "raw_payload": json.dumps(s, default=str),
                "s3_archive_key": key,
            }
            for src, dst in _FIELD_MAP.items():
                row[dst] = s.get(src)
            rows.append(row)
    return rows


def populate_player_match_stats(
    db: Session,
    *,
    seasons: list[int] | None = None,
    competition: int = 111,
    commit: bool = True,
) -> dict[str, Any]:
    team_map = _build_team_id_map(db)
    match_map = _build_match_id_map(db, seasons)
    player_map = _build_player_id_map(db)
    logger.info(
        "phase_stats: lookups — %d teams, %d matches, %d players",
        len(team_map), len(match_map), len(player_map),
    )

    keys = list_keys(f"miner/nrlcom/match-centre/{competition}/")
    if seasons:
        season_strs = {f"/{s}/" for s in seasons}
        keys = [k for k in keys if any(s in k for s in season_strs)]
    logger.info("phase_stats: %d match-centre archives to scan", len(keys))

    archives_read = 0
    archives_failed = 0
    rows_inserted = 0
    rows_updated = 0
    matches_unmatched = 0
    matches_fixture_only_skipped = 0
    players_no_meta = 0

    insert_cols = (
        "match_id, nrlcom_match_id, nrlcom_player_id, person_id, team_id, "
        "nrlcom_team_id, is_home, jersey_number, position, is_on_field, "
        + ", ".join(_FIELD_MAP.values())
        + ", raw_payload, s3_archive_key"
    )
    placeholders = (
        ":match_id, :nrlcom_match_id, :nrlcom_player_id, :person_id, :team_id, "
        ":nrlcom_team_id, :is_home, :jersey_number, :position, :is_on_field, "
        + ", ".join(f":{c}" for c in _FIELD_MAP.values())
        + ", CAST(:raw_payload AS JSONB), :s3_archive_key"
    )
    update_cols = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in (
            "match_id", "person_id", "team_id", "nrlcom_team_id", "is_home",
            "jersey_number", "position", "is_on_field",
            *_FIELD_MAP.values(),
            "raw_payload", "s3_archive_key",
        )
    ) + ", updated_at = NOW()"

    upsert_sql = text(f"""
        INSERT INTO player_match_stats ({insert_cols})
        VALUES ({placeholders})
        ON CONFLICT (nrlcom_match_id, nrlcom_player_id)
        DO UPDATE SET {update_cols}
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
        match_id, data_coverage = match_map[match_ext]
        if data_coverage == "fixture_only":
            # Parent-coverage gate (defensive); see phase_team_lists.
            matches_fixture_only_skipped += 1
            continue

        # Diagnostic: players in the stats block missing from the roster meta.
        player_meta = _build_player_meta_map(payload)
        stats_block = (payload.get("stats") or {}).get("players") or {}
        for side_key in ("homeTeam", "awayTeam"):
            for s in stats_block.get(side_key) or []:
                pid = s.get("playerId")
                if pid is not None and int(pid) not in player_meta:
                    players_no_meta += 1

        for row in _extract_stat_rows(payload, key, match_id, team_map, player_map):
            res = db.execute(upsert_sql, row)
            if res.scalar():
                rows_inserted += 1
            else:
                rows_updated += 1

        if archives_read % 50 == 0:
            if commit: db.commit()  # checkpoint so a crash doesn't lose 408 archives' work

    if commit: db.commit()
    logger.info(
        "phase_stats: inserted=%d updated=%d matches_unmatched=%d "
        "fixture_only_skipped=%d players_no_meta=%d",
        rows_inserted, rows_updated, matches_unmatched,
        matches_fixture_only_skipped, players_no_meta,
    )
    return {
        "archives_read": archives_read,
        "archives_failed": archives_failed,
        "rows_inserted": rows_inserted,
        "rows_updated": rows_updated,
        "matches_unmatched": matches_unmatched,
        "matches_fixture_only_skipped": matches_fixture_only_skipped,
        "players_no_meta": players_no_meta,
    }
