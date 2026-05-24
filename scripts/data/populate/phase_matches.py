"""Phase 2b — extract matches from scout/nrlcom/match-centre/* archives.

One row per (source='nrl_com', season, grade, external_match_id). Idempotent
upsert keyed on the `uq_matches_source_external` partial unique index.

`grade` is hardcoded to 'nrl' for competition=111. NRLW (161) would be
'nrlw', NSW Cup ('nsw_cup'), QLD Cup ('qld_cup'), etc.

Team resolution: JOIN teams ON nrlcom_team_id (populated by phase_identity).
Venue resolution: fuzzy match on venues.name. If no venue match, leaves
venue_id NULL — the `venues` table can be seeded later from any unmatched
strings.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ._s3_walk import list_keys, read_json_concurrent

logger = logging.getLogger(__name__)


_KEY_RE = re.compile(
    r"scout/nrlcom/match-centre/(?P<comp>\d+)/(?P<season>\d{4})/round-(?P<round>\d+)/(?P<slug>[^/]+)\.json$"
)


# Map nrl.com matchState → matches.status enum
_STATUS_MAP = {
    "Upcoming": "scheduled",
    "InProgress": "live",
    "Live": "live",
    "FullTime": "final",
    "Postponed": "postponed",
    "Cancelled": "cancelled",
    "Forfeit": "forfeit",
}


# Competition-id → grade enum
_GRADE_MAP = {
    111: "nrl",
    161: "nrlw",
    113: "nsw_cup",
    114: "qld_cup",
    156: "jersey_flegg",
    155: "mal_meninga",
}


def _build_team_id_map(db: Session) -> dict[int, str]:
    """nrlcom_team_id → team_id (str)."""
    rows = db.execute(text(
        "SELECT team_id, nrlcom_team_id FROM teams WHERE nrlcom_team_id IS NOT NULL"
    )).fetchall()
    return {nid: str(tid) for tid, nid in rows}


def _build_venue_id_map(db: Session) -> dict[str, str]:
    """Lower-cased venue name → venue_id (str)."""
    rows = db.execute(text("SELECT venue_id, name FROM venues")).fetchall()
    return {(name or "").lower(): str(vid) for vid, name in rows}


def _normalize_status(state: str | None) -> str:
    return _STATUS_MAP.get(state or "", "scheduled")


def _extract_one(
    payload: dict[str, Any],
    key: str,
    team_map: dict[int, str],
    venue_map: dict[str, str],
) -> dict[str, Any] | None:
    m = _KEY_RE.search(key)
    if not m:
        return None
    competition = int(m.group("comp"))
    season = int(m.group("season"))
    round_no = int(m.group("round"))

    grade = _GRADE_MAP.get(competition, "nrl")

    match_id_ext = str(payload.get("matchId") or "").strip()
    if not match_id_ext:
        return None

    home_team_nrlcom = (payload.get("homeTeam") or {}).get("teamId")
    away_team_nrlcom = (payload.get("awayTeam") or {}).get("teamId")
    home_team_id = team_map.get(int(home_team_nrlcom)) if home_team_nrlcom else None
    away_team_id = team_map.get(int(away_team_nrlcom)) if away_team_nrlcom else None
    if not home_team_id or not away_team_id:
        return None  # skip until team identity backfilled
    if home_team_id == away_team_id:
        return None  # ck_matches_distinct_teams

    venue_name = (payload.get("venue") or "").strip()
    venue_id = venue_map.get(venue_name.lower()) if venue_name else None

    home_score = (payload.get("homeTeam") or {}).get("score")
    away_score = (payload.get("awayTeam") or {}).get("score")
    if home_score is None or away_score is None:
        home_score = None
        away_score = None

    # nrl.com gives 0 attendance for unknowns — keep NULL in that case
    attendance = payload.get("attendance")
    if attendance is not None and int(attendance) == 0:
        attendance = None

    referee_name = None
    officials = payload.get("officials") or []
    for o in officials:
        if (o.get("position") or "").lower() == "referee":
            fn = (o.get("firstName") or "").strip()
            ln = (o.get("lastName") or "").strip()
            referee_name = f"{fn} {ln}".strip() or None
            break

    return {
        "source": "nrl_com",
        "external_match_id": match_id_ext,
        "season": season,
        "round": round_no,
        "round_label": payload.get("roundTitle"),
        "grade": grade,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "venue_id": venue_id,
        "kickoff_at": payload.get("startTime"),
        "status": _normalize_status(payload.get("matchState")),
        "home_score": home_score,
        "away_score": away_score,
        "weather": payload.get("weather"),
        "referee_name": referee_name,
        "broadcast": None,
        "attendance": attendance,
        "ground_conditions": payload.get("groundConditions"),
        "is_magic_round": False,
        "is_rep_weekend": False,
        "metadata_json_str": _metadata_blob(payload),
    }


def _metadata_blob(payload: dict[str, Any]) -> str:
    """Stash a small set of high-signal fields into metadata_json.

    We deliberately don't store the whole payload — that's what S3 is for.
    """
    import json
    keep = {
        "competition": (payload.get("competition") or {}).get("competitionId"),
        "venueCity": payload.get("venueCity"),
        "matchMode": payload.get("matchMode"),
        "hasExtraTime": payload.get("hasExtraTime"),
        "segmentCount": payload.get("segmentCount"),
        "segmentDuration": payload.get("segmentDuration"),
    }
    return json.dumps({k: v for k, v in keep.items() if v is not None})


def populate_matches(
    db: Session,
    *,
    seasons: list[int] | None = None,
    competition: int = 111,
    commit: bool = True,
) -> dict[str, Any]:
    team_map = _build_team_id_map(db)
    venue_map = _build_venue_id_map(db)
    logger.info("phase_matches: team_map=%d teams, venue_map=%d venues",
                len(team_map), len(venue_map))

    keys = list_keys(f"scout/nrlcom/match-centre/{competition}/")
    if seasons:
        season_strs = {f"/{s}/" for s in seasons}
        keys = [k for k in keys if any(s in k for s in season_strs)]
    logger.info("phase_matches: %d match-centre archives to scan", len(keys))

    rows: list[dict[str, Any]] = []
    archives_read = 0
    archives_failed = 0
    skipped_no_team = 0
    for key, payload, err in read_json_concurrent(keys, max_workers=16):
        if err is not None or payload is None:
            archives_failed += 1
            continue
        archives_read += 1
        row = _extract_one(payload, key, team_map, venue_map)
        if row is None:
            skipped_no_team += 1
            continue
        rows.append(row)

    logger.info(
        "phase_matches: parsed %d rows (%d archives read, %d failed, %d skipped)",
        len(rows), archives_read, archives_failed, skipped_no_team,
    )

    inserted = 0
    updated = 0
    venue_misses: set[str] = set()
    for row in rows:
        # Track venues we failed to resolve, for follow-up seeding.
        if row["venue_id"] is None:
            # We don't have the venue name here anymore — could plumb through.
            pass
        result = db.execute(
            text("""
                INSERT INTO matches (
                    source, external_match_id, season, round, round_label, grade,
                    home_team_id, away_team_id, venue_id, kickoff_at, status,
                    home_score, away_score, weather, referee_name, broadcast,
                    attendance, ground_conditions, is_magic_round, is_rep_weekend,
                    metadata_json, last_synced_at
                )
                VALUES (
                    :source, :external_match_id, :season, :round, :round_label, :grade,
                    :home_team_id, :away_team_id, :venue_id, :kickoff_at, :status,
                    :home_score, :away_score, :weather, :referee_name, :broadcast,
                    :attendance, :ground_conditions, :is_magic_round, :is_rep_weekend,
                    CAST(:metadata_json_str AS JSONB), NOW()
                )
                ON CONFLICT (source, season, grade, external_match_id)
                  WHERE external_match_id IS NOT NULL
                DO UPDATE SET
                    round = EXCLUDED.round,
                    round_label = EXCLUDED.round_label,
                    venue_id = COALESCE(EXCLUDED.venue_id, matches.venue_id),
                    kickoff_at = EXCLUDED.kickoff_at,
                    status = EXCLUDED.status,
                    home_score = EXCLUDED.home_score,
                    away_score = EXCLUDED.away_score,
                    weather = EXCLUDED.weather,
                    referee_name = COALESCE(EXCLUDED.referee_name, matches.referee_name),
                    attendance = EXCLUDED.attendance,
                    ground_conditions = EXCLUDED.ground_conditions,
                    metadata_json = matches.metadata_json || EXCLUDED.metadata_json,
                    last_synced_at = NOW()
                RETURNING (xmax = 0) AS inserted
            """),
            row,
        )
        was_insert = result.scalar()
        if was_insert:
            inserted += 1
        else:
            updated += 1
    if commit: db.commit()

    logger.info("phase_matches: inserted=%d updated=%d", inserted, updated)
    return {
        "archives_read": archives_read,
        "archives_failed": archives_failed,
        "matches_parsed": len(rows),
        "matches_inserted": inserted,
        "matches_updated": updated,
        "skipped_no_team_match": skipped_no_team,
    }
