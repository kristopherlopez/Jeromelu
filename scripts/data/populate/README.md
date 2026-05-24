# `scripts/data/populate/` — S3 → DB extractors

Projects the `scout/*` archives in S3 into the relational tables. Day-to-day,
the Scout pipelines + their attached extractors keep the DB current; this
package is the **backfill driver** that re-projects the historical backlog of
archives, and the place the per-table extraction logic lives.

## Orchestrator

`scripts/data/populate_db_from_s3.py` runs phases in FK-dependency order:

```
identity → people → rounds → matches → team_lists → stats → timeline
         → standings → leaderboards → injuries → reresolve → attributes
```

Each phase is **idempotent** (UPSERT on a natural key), so re-running is safe.

```
python -m scripts.data.populate_db_from_s3 --phase all      --seasons 2026
python -m scripts.data.populate_db_from_s3 --phase matches   --seasons 2026 --competition 111
python -m scripts.data.populate_db_from_s3 --phase matches   --seasons 2026 --dry-run
```

## The nrl.com match-centre phases (Phase 3.5)

Read `scout/nrlcom/match-centre/{comp}/{season}/round-{NN}/{slug}.json`; resolve
identity via `teams.nrlcom_team_id` / `people.nrlcom_player_id` /
`matches.external_match_id`; UPSERT.

| Phase module | Writes | Pure extractor (test seam) |
|---|---|---|
| `phase_matches.py` | `matches` | `_extract_one(payload, key, team_map, venue_map)` |
| `phase_team_lists.py` | `match_team_lists` (players; coaches via `_ensure_coach_person`) | `_extract_player_list_rows(payload, match_id, team_map, player_map)` |
| `phase_stats.py` | `player_match_stats` | `_extract_stat_rows(payload, key, match_id, team_map, player_map)` |
| `phase_timeline.py` | `match_timeline` + `match_officials` | `_extract_timeline_rows(...)`, `_extract_official_rows(...)` |

The pure `_extract_*` functions take a parsed payload + identity maps and return
`list[dict]` rows — **no S3, no DB** — so they're unit-tested in
`tests/unit/scripts/data/populate/test_phase_*.py` against the checked-in
match-centre fixtures (`tests/fixtures/scout/nrlcom_match_centre/`). The phase's
`populate_*` function builds the maps from the DB, calls the pure extractor, and
UPSERTs the rows.

## `--dry-run`

Fixed 2026-05-24 (was the META known-bug — phases committed internally before
the outer rollback, so the flag silently wrote). Every phase now takes
`commit: bool = True` and guards each `db.commit()` (final + per-50 checkpoints)
with `if commit:`; the orchestrator passes `commit=not args.dry_run` and rolls
back at the end. `--dry-run` now computes counts and writes nothing.

## Runtime (how to actually run it)

⚠️ **The prod box has no standalone Python env with these deps** (`sqlalchemy`,
`psycopg`, `pydantic`, `httpx`, `boto3` + `jeromelu_shared`). The historical
runs were driven from a dev machine over an SSH tunnel to the loopback-only DB.
For an on-box run, the deps live in the `jeromelu-api` container — stage the
scripts in and exec there:

```bash
docker exec jeromelu-api mkdir -p /runtmp
docker cp /opt/jeromelu/scripts  jeromelu-api:/runtmp/scripts
docker cp /opt/jeromelu/packages jeromelu-api:/runtmp/packages
docker exec -w /runtmp -e PYTHONPATH=/runtmp/packages/shared jeromelu-api \
    python -m scripts.data.populate_db_from_s3 --phase all --seasons 2026
docker exec jeromelu-api rm -rf /runtmp   # ephemeral
```

This works but is a one-off. A **reproducible runtime is an open follow-up** —
preferred fix: bake `scripts/` + `packages/shared` into the api image (or a
managed ops venv) so future backfills/cron don't depend on `docker cp`.
