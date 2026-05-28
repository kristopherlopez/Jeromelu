"""Phase 2b — extract matches from scout/nrlcom/{match-centre,draw}/* archives.

Era-aware projection per [Scout Phase 5](../../docs/build/PLAN.md). One row per
(source='nrl_com', season, grade, external_match_id) — idempotent upsert keyed
on the `uq_matches_source_external` partial unique index.

Two source archives feed this phase:
  - `scout/nrlcom/match-centre/{comp}/{season}/round-{NN}/{slug}.json` —
    full or partial detail; identity `external_match_id = payload.matchId`.
  - `scout/nrlcom/draw/{comp}/{season}/round-{NN}.json` — fixture list;
    identity `external_match_id = <slug from matchCentreUrl>`.

Each match-centre archive's row gets `data_coverage` derived from its shape:
  'full'              — has stats.players (post-FullTime modern matches)
  'lineups+timeline'  — has homeTeam.players but no stats.players (pre-finish
                        or partial-shape modern matches)
  'timeline_only'     — has timeline but no team rosters (1990-1999 partial)

Each draw fixture that lacks a corresponding match-centre archive gets a
'fixture_only' row — used for 1908-1989 history where nrl.com match-centre
data simply doesn't exist (no `matchCentreUrl`).

The two code paths emit disjoint identity-namespaces (`payload.matchId` for
match-centre, slug for draw-only) — the walker pre-builds the set of known
match-centre slugs and skips draw fixtures whose archive already exists,
so a future re-run after match-centre backfill upserts cleanly via slug.

Trust hierarchy on conflict: match-centre data always wins over draw-only.
A re-extract from match-centre on an existing match-centre row updates per
the EXCLUDED columns. A draw-only `fixture_only` row never downgrades an
existing match's `data_coverage`.

`grade` is hardcoded to 'nrl' for competition=111. NRLW (161) would be 'nrlw'.

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

_DRAW_KEY_RE = re.compile(
    r"scout/nrlcom/draw/(?P<comp>\d+)/(?P<season>\d{4})/round-(?P<round>\d+)\.json$"
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


def _derive_data_coverage(payload: dict[str, Any]) -> str:
    """Derive `data_coverage` for a match-centre archive from its shape.

    Era-band detection by content, not year — defensive against odd years
    where the upstream payload's shape varies inside an era band.
    """
    stats_block = (payload.get("stats") or {}).get("players") or {}
    has_stats = bool(
        stats_block.get("homeTeam") or stats_block.get("awayTeam")
    )
    if has_stats:
        return "full"
    home_players = (payload.get("homeTeam") or {}).get("players") or []
    away_players = (payload.get("awayTeam") or {}).get("players") or []
    if home_players or away_players:
        return "lineups+timeline"
    timeline = payload.get("timeline") or []
    if timeline:
        return "timeline_only"
    # Match-centre archive with no stats, no rosters, no timeline. Rare —
    # treat as the weakest coverage we can; should never collide with a
    # draw-only fixture_only row because the slugs are disjoint.
    return "fixture_only"


def _extract_one(
    payload: dict[str, Any],
    key: str,
    team_map: dict[int, str],
    venue_map: dict[str, str],
) -> dict[str, Any] | None:
    """Project a match-centre archive into a `matches` row.

    Returns None for archives we can't usefully project (no matchId, no
    resolvable home/away team, or both teams resolve to the same team).
    """
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
        "data_coverage": _derive_data_coverage(payload),
        "metadata_json_str": _metadata_blob(payload),
    }


def _slug_from_match_centre_url(url: str | None) -> str | None:
    """Parse the trailing slug from a matchCentreUrl.

    Examples:
        '/draw/nrl-premiership/2026/round-13/sharks-v-sea-eagles/'
            → 'sharks-v-sea-eagles'
        '' or None → None
    """
    if not url:
        return None
    parts = url.rstrip("/").rsplit("/", 1)
    if len(parts) >= 1 and parts[-1] and "/" not in parts[-1]:
        return parts[-1]
    return None


def _draw_external_id(
    fixture: dict[str, Any], *, season: int, round_no: int
) -> str | None:
    """Derive a stable external_match_id for a draw-only fixture.

    Preference order:
      1. Slug from `matchCentreUrl` (modern fixtures — same slug the future
         match-centre archive would use).
      2. Synthetic from teams + round + season (pre-1990 fixtures where
         `matchCentreUrl` is absent).
    """
    slug = _slug_from_match_centre_url(fixture.get("matchCentreUrl"))
    if slug:
        return slug
    home = (fixture.get("homeTeam") or {}).get("nickName") or ""
    away = (fixture.get("awayTeam") or {}).get("nickName") or ""
    home_s = home.strip().lower().replace(" ", "-").replace("'", "")
    away_s = away.strip().lower().replace(" ", "-").replace("'", "")
    if home_s and away_s:
        return f"{home_s}-v-{away_s}-r{round_no:02d}-{season}"
    return None


def _extract_from_draw_fixture(
    fixture: dict[str, Any],
    *,
    season: int,
    round_no: int,
    competition: int,
    team_map: dict[int, str],
    venue_map: dict[str, str],
) -> dict[str, Any] | None:
    """Project a single draw fixture into a `matches` row.

    Emits `data_coverage='fixture_only'`. Returns None if teams can't
    resolve (unknown nrlcom_team_id) or if the home/away teams are the
    same (degenerate guard).
    """
    grade = _GRADE_MAP.get(competition, "nrl")

    home_team_nrlcom = (fixture.get("homeTeam") or {}).get("teamId")
    away_team_nrlcom = (fixture.get("awayTeam") or {}).get("teamId")
    home_team_id = team_map.get(int(home_team_nrlcom)) if home_team_nrlcom else None
    away_team_id = team_map.get(int(away_team_nrlcom)) if away_team_nrlcom else None
    if not home_team_id or not away_team_id:
        return None
    if home_team_id == away_team_id:
        return None

    ext_id = _draw_external_id(fixture, season=season, round_no=round_no)
    if not ext_id:
        return None

    venue_name = (fixture.get("venue") or "").strip()
    venue_id = venue_map.get(venue_name.lower()) if venue_name else None

    home_score = (fixture.get("homeTeam") or {}).get("score")
    away_score = (fixture.get("awayTeam") or {}).get("score")
    if home_score is None or away_score is None:
        home_score = None
        away_score = None

    return {
        "source": "nrl_com",
        "external_match_id": ext_id,
        "season": season,
        "round": round_no,
        "round_label": fixture.get("roundTitle"),
        "grade": grade,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "venue_id": venue_id,
        "kickoff_at": fixture.get("startTime") or fixture.get("clock", {}).get("kickOffTimeLong"),
        "status": _normalize_status(fixture.get("matchState")),
        "home_score": home_score,
        "away_score": away_score,
        "weather": None,
        "referee_name": None,
        "broadcast": None,
        "attendance": None,
        "ground_conditions": None,
        "is_magic_round": False,
        "is_rep_weekend": False,
        "data_coverage": "fixture_only",
        "metadata_json_str": _draw_metadata_blob(fixture),
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


def _draw_metadata_blob(fixture: dict[str, Any]) -> str:
    """Small metadata blob for draw-only fixtures.

    Records `matchCentreUrl` so the row can later be linked to a backfilled
    match-centre archive (and the slug source can be re-derived).
    """
    import json
    keep = {
        "venueCity": fixture.get("venueCity"),
        "matchMode": fixture.get("matchMode"),
        "matchCentreUrl": fixture.get("matchCentreUrl"),
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

    # 1. Walk match-centre archives — modern matches with full/partial shape.
    mc_keys = list_keys(f"scout/nrlcom/match-centre/{competition}/")
    if seasons:
        season_strs = {f"/{s}/" for s in seasons}
        mc_keys = [k for k in mc_keys if any(s in k for s in season_strs)]
    logger.info("phase_matches: %d match-centre archives to scan", len(mc_keys))

    # Build the set of (season, round, slug) tuples we've already seen via
    # match-centre — used to suppress duplicate draw-only projections in
    # the same run.
    mc_slugs: set[tuple[int, int, str]] = set()
    for k in mc_keys:
        m = _KEY_RE.search(k)
        if m:
            mc_slugs.add((int(m.group("season")), int(m.group("round")), m.group("slug")))

    rows: list[dict[str, Any]] = []
    archives_read = 0
    archives_failed = 0
    skipped_no_team = 0
    for key, payload, err in read_json_concurrent(mc_keys, max_workers=16):
        if err is not None or payload is None:
            archives_failed += 1
            continue
        archives_read += 1
        row = _extract_one(payload, key, team_map, venue_map)
        if row is None:
            skipped_no_team += 1
            continue
        rows.append(row)

    # 2. Walk draw archives — pre-1990 fixtures and any modern (season,round)
    # whose match-centre archive isn't (yet) in S3.
    draw_keys = list_keys(f"scout/nrlcom/draw/{competition}/")
    if seasons:
        season_strs = {f"/{s}/" for s in seasons}
        draw_keys = [k for k in draw_keys if any(s in k for s in season_strs)]
    logger.info("phase_matches: %d draw archives to scan", len(draw_keys))

    draw_rows_emitted = 0
    draw_archives_read = 0
    draw_archives_failed = 0
    draw_skipped_mc_exists = 0
    draw_skipped_no_team = 0
    for key, payload, err in read_json_concurrent(draw_keys, max_workers=16):
        if err is not None or payload is None:
            draw_archives_failed += 1
            continue
        draw_archives_read += 1
        dm = _DRAW_KEY_RE.search(key)
        if not dm:
            continue
        season = int(dm.group("season"))
        round_no = int(dm.group("round"))
        for fixture in payload.get("fixtures") or []:
            # If a match-centre archive for this fixture already exists this
            # run, the match-centre projection wins and we skip the draw-only
            # emission. Slug derivation matches _slug_from_match_centre_url
            # so both paths agree.
            slug = _slug_from_match_centre_url(fixture.get("matchCentreUrl"))
            if slug and (season, round_no, slug) in mc_slugs:
                draw_skipped_mc_exists += 1
                continue
            row = _extract_from_draw_fixture(
                fixture,
                season=season,
                round_no=round_no,
                competition=competition,
                team_map=team_map,
                venue_map=venue_map,
            )
            if row is None:
                draw_skipped_no_team += 1
                continue
            rows.append(row)
            draw_rows_emitted += 1

    logger.info(
        "phase_matches: parsed %d rows total (mc: %d read, %d failed, %d skipped; "
        "draw: %d read, %d failed, %d emitted, %d skip-mc-exists, %d skip-no-team)",
        len(rows), archives_read, archives_failed, skipped_no_team,
        draw_archives_read, draw_archives_failed, draw_rows_emitted,
        draw_skipped_mc_exists, draw_skipped_no_team,
    )

    inserted = 0
    updated = 0
    for row in rows:
        # On conflict (existing match): match-centre values win; a draw-only
        # `fixture_only` row never downgrades a higher-coverage existing row.
        result = db.execute(
            text("""
                INSERT INTO matches (
                    source, external_match_id, season, round, round_label, grade,
                    home_team_id, away_team_id, venue_id, kickoff_at, status,
                    home_score, away_score, weather, referee_name, broadcast,
                    attendance, ground_conditions, is_magic_round, is_rep_weekend,
                    data_coverage, metadata_json, last_synced_at
                )
                VALUES (
                    :source, :external_match_id, :season, :round, :round_label, :grade,
                    :home_team_id, :away_team_id, :venue_id, :kickoff_at, :status,
                    :home_score, :away_score, :weather, :referee_name, :broadcast,
                    :attendance, :ground_conditions, :is_magic_round, :is_rep_weekend,
                    :data_coverage, CAST(:metadata_json_str AS JSONB), NOW()
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
                    data_coverage = CASE
                        WHEN EXCLUDED.data_coverage = 'fixture_only' THEN matches.data_coverage
                        ELSE EXCLUDED.data_coverage
                    END,
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
        "draw_archives_read": draw_archives_read,
        "draw_archives_failed": draw_archives_failed,
        "draw_rows_emitted": draw_rows_emitted,
        "draw_skipped_mc_exists": draw_skipped_mc_exists,
        "draw_skipped_no_team": draw_skipped_no_team,
        "matches_parsed": len(rows),
        "matches_inserted": inserted,
        "matches_updated": updated,
        "skipped_no_team_match": skipped_no_team,
    }
