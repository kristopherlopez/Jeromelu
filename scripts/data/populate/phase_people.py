"""Phase 1.5 — populate `people` from every source we have.

The original phase_identity only *updates* existing `people` rows with
their nrlcom_player_id. It never inserts new rows. As a result, anyone
who played NRL pre-2025 but isn't on the current SC roster has no
people row, so pre-2025 player_match_stats / match_team_lists /
match_timeline carry NULL person_id.

This phase fixes that by walking every source that emits a profile ID
and ensuring `people` has exactly one row per distinct human.

Sources scanned, in priority order:

  1. nrl.com match-centre — `homeTeam.players[].playerId`
                            `homeTeam.coaches[].profileId`
                            `officials[].profileId`
     (one profile-id space; metadata_json.role_class distinguishes
      player / coach / referee)

  2. nrl.com players-roster — name + team-nickname only (no profile id).
     Used only to enrich biographical fields (image_url) on rows we
     already inserted via source #1.

(Sources we deliberately skip)
  - supercoach players-cf: already the primary writer for people via
    `scout/supercoach_roster/`. No new inserts here.
  - nrlsupercoachstats: synthetic name-hash IDs. Not safe as an
    identity primary key.
  - casualty-ward: no profile id. Only useful for enrichment.

Idempotency
  - Unique constraint `uq_people_nrlcom_player_id` guarantees one row
    per `nrlcom_player_id`.
  - For each candidate, the resolver tries in order:
      a) match by nrlcom_player_id → already exists, no-op
      b) match by canonical_name + current-team against an existing
         people row that doesn't yet have an nrlcom_player_id → UPDATE
         that row (merge IDs)
      c) INSERT new row, slug = firstname-lastname or fallback
         firstname-lastname-{profileId} on collision

Re-runs only insert net-new profile ids. Safe to schedule daily.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ._s3_walk import list_keys, read_json_concurrent

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    s = (name or "").lower().strip()
    s = re.sub(r"[^a-z0-9\s-]+", "", s)
    s = re.sub(r"\s+", "-", s)
    return s.strip("-")


def _normalize_name(name: str) -> str:
    n = (name or "").lower().strip()
    n = re.sub(r"[^a-z0-9\s'-]+", " ", n)
    n = re.sub(r"\s+", " ", n)
    return n


def _team_nick_norm(nick: str) -> str:
    return (nick or "").lower().strip()


def _build_team_id_map(db: Session) -> dict[int, str]:
    """nrlcom_team_id → team_id."""
    rows = db.execute(text(
        "SELECT team_id, nrlcom_team_id FROM teams WHERE nrlcom_team_id IS NOT NULL"
    )).fetchall()
    return {nid: str(tid) for tid, nid in rows}


def _build_team_nick_to_team_id(db: Session) -> dict[str, str]:
    """Lower-cased nickname / slug / alias → team_id (for non-FK resolution)."""
    rows = db.execute(text(
        "SELECT team_id, slug, short_name, aliases FROM teams WHERE grade='nrl'"
    )).fetchall()
    out: dict[str, str] = {}
    for tid, slug, short, aliases in rows:
        tid_s = str(tid)
        out[_team_nick_norm(slug)] = tid_s
        if short:
            out[_team_nick_norm(short)] = tid_s
        for a in (aliases or []):
            out[_team_nick_norm(a)] = tid_s
    return out


def _build_existing_indices(db: Session) -> tuple[
    dict[int, str],
    dict[tuple[str, str], str],
    dict[str, str],
]:
    """Build three lookups against the current `people` state:

    - by_nrlcom: nrlcom_player_id → person_id
    - by_name_team: (norm_name, norm_team) → person_id  (current team via SCD-2)
    - by_slug: slug → person_id  (for slug-collision detection)
    """
    rows = db.execute(text("""
        SELECT
            p.person_id, p.canonical_name, p.aliases, p.slug,
            p.nrlcom_player_id,
            t.slug AS team_slug, t.short_name AS team_short
        FROM people p
        LEFT JOIN people_attributes pa
            ON pa.person_id = p.person_id AND pa.effective_to IS NULL
        LEFT JOIN teams t ON t.team_id = pa.team_id
    """)).fetchall()
    by_nrlcom: dict[int, str] = {}
    by_name_team: dict[tuple[str, str], str] = {}
    by_slug: dict[str, str] = {}
    for r in rows:
        pid = str(r.person_id)
        if r.nrlcom_player_id is not None:
            by_nrlcom[int(r.nrlcom_player_id)] = pid
        if r.slug:
            by_slug[r.slug] = pid
        team_keys = ["", _team_nick_norm(r.team_slug), _team_nick_norm(r.team_short)]
        for n in [r.canonical_name, *(r.aliases or [])]:
            if not n:
                continue
            nn = _normalize_name(n)
            for tk in team_keys:
                by_name_team.setdefault((nn, tk), pid)
    return by_nrlcom, by_name_team, by_slug


def _harvest_candidates(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Pull (profileId, name parts, team nickname, role_class, image) tuples
    from one match-centre archive.
    """
    out: list[dict[str, Any]] = []
    for side in ("homeTeam", "awayTeam"):
        team = payload.get(side) or {}
        nick = team.get("nickName") or ""
        nrl_team_id = team.get("teamId")
        for p in team.get("players") or []:
            pid = p.get("playerId")
            if not pid:
                continue
            out.append({
                "nrlcom_player_id": int(pid),
                "first_name": (p.get("firstName") or "").strip(),
                "last_name": (p.get("lastName") or "").strip(),
                "team_nickname": nick,
                "nrlcom_team_id": int(nrl_team_id) if nrl_team_id else None,
                "role_class": "player",
                "image_url": p.get("headImage"),
                "url": p.get("url"),
            })
        for c in team.get("coaches") or []:
            pid = c.get("profileId")
            if not pid:
                continue
            out.append({
                "nrlcom_player_id": int(pid),
                "first_name": (c.get("firstName") or "").strip(),
                "last_name": (c.get("lastName") or "").strip(),
                "team_nickname": nick,
                "nrlcom_team_id": int(nrl_team_id) if nrl_team_id else None,
                "role_class": "coach",
                "image_url": c.get("headImage"),
                "url": c.get("url"),
            })
    for o in payload.get("officials") or []:
        pid = o.get("profileId")
        if not pid:
            continue
        out.append({
            "nrlcom_player_id": int(pid),
            "first_name": (o.get("firstName") or "").strip(),
            "last_name": (o.get("lastName") or "").strip(),
            "team_nickname": "",
            "nrlcom_team_id": None,
            "role_class": "referee",
            "image_url": o.get("headImage"),
            "url": o.get("url"),
        })
    return out


def populate_people_history(
    db: Session,
    *,
    competition: int = 111,
) -> dict[str, Any]:
    """Walk every match-centre archive across every season and ensure a
    `people` row exists for every distinct profileId we see.

    Returns counts so the caller can verify net-new vs no-op.
    """
    team_id_by_nrlcom = _build_team_id_map(db)
    team_id_by_nick = _build_team_nick_to_team_id(db)
    by_nrlcom, by_name_team, by_slug = _build_existing_indices(db)
    logger.info(
        "phase_people: lookups — %d teams by nrlcom id, %d by nickname; "
        "existing people: %d with nrlcom_id, %d slugs",
        len(team_id_by_nrlcom), len(team_id_by_nick), len(by_nrlcom), len(by_slug),
    )

    keys = list_keys(f"scout/nrlcom/match-centre/{competition}/")
    logger.info("phase_people: %d match-centre archives to scan", len(keys))

    # Distinct-by-nrlcom-id, keeping the FIRST (most-recent walk-order)
    # row per id. Most recent typically has freshest image_url and name.
    candidates: dict[int, dict[str, Any]] = {}
    archives_read = 0
    archives_failed = 0
    for key, payload, err in read_json_concurrent(keys, max_workers=16):
        if err is not None or payload is None:
            archives_failed += 1
            continue
        archives_read += 1
        for cand in _harvest_candidates(payload):
            existing = candidates.get(cand["nrlcom_player_id"])
            if existing is None:
                candidates[cand["nrlcom_player_id"]] = cand
            else:
                # Upgrade: prefer a candidate with a richer image_url or
                # a non-empty last_name.
                if not existing.get("image_url") and cand.get("image_url"):
                    existing["image_url"] = cand["image_url"]
                if not existing.get("last_name") and cand.get("last_name"):
                    existing["last_name"] = cand["last_name"]
    logger.info(
        "phase_people: harvested %d distinct profile ids from %d archives (%d failed)",
        len(candidates), archives_read, archives_failed,
    )

    inserted = 0
    updated_id_only = 0
    skipped_existing = 0
    skipped_no_name = 0
    skipped_unresolved = 0
    processed = 0

    # Commit-per-iteration instead of SAVEPOINTs. Each candidate is its own
    # transaction so a unique-constraint failure on one doesn't poison the
    # rest. SQLAlchemy's Session.begin_nested() turns out to be unreliable
    # when ON CONFLICT DO NOTHING fires without RETURNING — it marks the
    # outer transaction as needing rollback.
    for nrlcom_id, c in candidates.items():
        processed += 1
        if processed % 100 == 0:
            logger.info(
                "  phase_people: %d / %d processed  (ins=%d merge=%d skip=%d)",
                processed, len(candidates), inserted, updated_id_only, skipped_existing,
            )

        if nrlcom_id in by_nrlcom:
            skipped_existing += 1
            continue

        first = c["first_name"]
        last = c["last_name"]
        canonical = f"{first} {last}".strip()
        if not canonical:
            skipped_no_name += 1
            continue
        name_norm = _normalize_name(canonical)

        # Case B — name matches an existing person who has no nrlcom_id yet
        team_norm = _team_nick_norm(c["team_nickname"])
        candidate_person_id = (
            by_name_team.get((name_norm, team_norm))
            or by_name_team.get((name_norm, ""))
        )

        try:
            did_merge = False
            if candidate_person_id:
                row = db.execute(
                    text("SELECT nrlcom_player_id FROM people WHERE person_id = :pid"),
                    {"pid": candidate_person_id},
                ).first()
                if row and row[0] is None:
                    conflict = db.execute(
                        text("""
                            SELECT 1 FROM people
                            WHERE nrlcom_player_id = :nid AND person_id <> :pid
                        """),
                        {"nid": nrlcom_id, "pid": candidate_person_id},
                    ).first()
                    if not conflict:
                        db.execute(
                            text("""
                                UPDATE people
                                SET nrlcom_player_id = :nid,
                                    image_url = COALESCE(image_url, :img),
                                    metadata_json = metadata_json
                                        || jsonb_build_object('nrlcom_url', CAST(:url AS TEXT))
                                WHERE person_id = :pid
                            """),
                            {"nid": nrlcom_id, "img": c.get("image_url"),
                             "url": c.get("url"), "pid": candidate_person_id},
                        )
                        db.commit()
                        by_nrlcom[nrlcom_id] = candidate_person_id
                        updated_id_only += 1
                        did_merge = True

            if did_merge:
                continue

            # Case C — INSERT. Try the base slug first; if it's taken
            # (slug_in_by_slug) try the suffixed slug. Pre-check rather
            # than relying on ON CONFLICT DO NOTHING (which interferes
            # with Session transaction tracking).
            slug_base = _slugify(canonical) or f"nrlcom-{nrlcom_id}"
            slug = slug_base if slug_base not in by_slug else f"{slug_base}-{nrlcom_id}"
            if slug in by_slug:
                # Both slugs collide — unusual. Skip and log.
                skipped_unresolved += 1
                if skipped_unresolved <= 10:
                    logger.warning(
                        "phase_people: slug-collide both attempts nrlcom_id=%s name=%s",
                        nrlcom_id, canonical,
                    )
                continue

            row = db.execute(
                text("""
                    INSERT INTO people (
                        canonical_name, slug, image_url, nrlcom_player_id, metadata_json
                    )
                    VALUES (
                        :name, :slug, :img, :nid,
                        jsonb_build_object(
                            'role_class', CAST(:role_class AS TEXT),
                            'nrlcom_url', CAST(:url AS TEXT),
                            'source', 'nrlcom/match-centre'
                        )
                    )
                    RETURNING person_id
                """),
                {
                    "name": canonical, "slug": slug,
                    "img": c.get("image_url"), "nid": nrlcom_id,
                    "role_class": c["role_class"], "url": c.get("url"),
                },
            ).first()
            db.commit()
            if row:
                by_nrlcom[nrlcom_id] = str(row[0])
                by_slug[slug] = str(row[0])
                inserted += 1
        except Exception:
            db.rollback()
            if inserted + updated_id_only + skipped_unresolved < 20:
                logger.exception(
                    "phase_people: failed nrlcom_id=%s name=%s",
                    nrlcom_id, canonical,
                )
            skipped_unresolved += 1

    logger.info(
        "phase_people: inserted=%d  updated_id_only=%d  skipped_existing=%d  "
        "skipped_no_name=%d  skipped_unresolved=%d",
        inserted, updated_id_only, skipped_existing, skipped_no_name, skipped_unresolved,
    )
    return {
        "archives_read": archives_read,
        "archives_failed": archives_failed,
        "distinct_profile_ids": len(candidates),
        "inserted": inserted,
        "updated_id_only": updated_id_only,
        "skipped_existing": skipped_existing,
        "skipped_no_name": skipped_no_name,
        "skipped_unresolved": skipped_unresolved,
    }


def reresolve_person_ids(db: Session) -> dict[str, int]:
    """Fill in NULL person_id columns now that more people rows exist.

    Idempotent — only touches NULLs.
    """
    counts: dict[str, int] = {}
    for table, fk_col in (
        ("player_match_stats", "person_id"),
        ("match_timeline", "person_id"),
        ("match_team_lists", "player_id"),
    ):
        # match_team_lists uses player_id; others use person_id. Both
        # reference people.person_id and resolve via people.nrlcom_player_id.
        sql = text(f"""
            UPDATE {table} t
            SET {fk_col} = p.person_id
            FROM people p
            WHERE p.nrlcom_player_id = t.nrlcom_player_id
              AND t.{fk_col} IS NULL
        """) if table != "match_team_lists" else None
        if sql is None:
            # match_team_lists doesn't carry nrlcom_player_id — it was
            # filled at insert time from the player_map lookup. Skip.
            counts[table] = 0
            continue
        res = db.execute(sql)
        counts[table] = res.rowcount or 0
    db.commit()
    logger.info("reresolve_person_ids: %s", counts)
    return counts
