# Scout Phase 5 — Historical backfill + standard-data-model conformance

**Date:** 2026-05-28 · **Status:** 🟡 In flight (2/10 tasks shipped) · **Plan:** [Scout Phase 5](../PLAN.md#2026-05-28-scout-phase-5--historical-backfill--standard-data-model-conformance)

**TL;DR** — Phase 5 lands historical NRL data (draw 1908+, match-centre 1990+, ladder 1996+, stats 2013+, SC stats 2018+) into the canonical DB schema. The load-bearing constraint is "all the data needs to conform to a standard data model" — era variance is reconciled by NULLs + a new `matches.data_coverage` column ('full' / 'lineups+timeline' / 'timeline_only' / 'fixture_only'), never by alternate tables or JSONB blobs. D8 strict-parse stays modern-only; backfill bypasses it via a new `archive_only=true` route flag. Era-tolerance lives in extractors, not in models. 10 tasks: 4 code (37-40), 4 operator backfills (41-44), 1 DB sweep (45), 1 closure (46).

---

## What was completed

### TASK-37 — Migration 071 (matches.data_coverage) + era-aware populate_matches + parent-coverage gate (`da5423d`)
Migration `071_matches_data_coverage.sql` (note: number is **071** not the spec's 061 — 061..070 already exist; planner missed; next-free was the only correct choice). Adds `matches.data_coverage text NOT NULL DEFAULT 'full'` with `CHECK (data_coverage IN ('full', 'lineups+timeline', 'timeline_only', 'fixture_only'))` and a partial index `idx_matches_data_coverage WHERE data_coverage <> 'full'` (not in spec — additive, cheap, supports the Phase 5 era-banded verification queries in TASK-45). Applied via `make migrate`; 5292 existing local-dev `matches` rows defaulted to `'full'`.

`scripts/data/populate/phase_matches.py` substantively rewritten:
- New `_derive_data_coverage(payload)` — 4-band content-based ladder: `stats.players` present → `'full'`; team rosters present → `'lineups+timeline'`; `timeline` present → `'timeline_only'`; else degenerate `'fixture_only'` fallback (the non-downgrade CASE in the upsert prevents this from poisoning existing rows).
- New `_extract_from_draw_fixture(fixture, *, season, round_no, competition, team_map, venue_map)` — projects a single draw fixture into a `matches` row with `data_coverage='fixture_only'`. **Spec deviation, documented:** spec said `external_match_id` from `fixture.matchId` (string) but draw fixtures have `matchId: null`. Implementer derives from `matchCentreUrl` slug (e.g., `'sharks-v-sea-eagles'`) with a synthetic team-based fallback for pre-1990 fixtures lacking the URL (e.g., `'old-home-v-old-away-r01-1908'`). Documented in module docstring + `_draw_external_id` helper.
- New `_slug_from_match_centre_url(url)` + `_draw_external_id(fixture, ...)` helpers.
- New `_DRAW_KEY_RE` for parsing draw S3 keys.
- `_extract_one` extended to emit `data_coverage` from the payload shape.
- `populate_matches` walker now lists both `scout/nrlcom/match-centre/{comp}/` and `scout/nrlcom/draw/{comp}/` prefixes. Pre-builds `mc_slugs: set[tuple[int, int, str]]` from match-centre keys, then skips draw fixtures whose slug is in the set — slug-disjoint identity scheme guarantees no upsert collisions.
- UPSERT SQL extended with `data_coverage` column and a non-downgrade rule: `data_coverage = CASE WHEN EXCLUDED.data_coverage = 'fixture_only' THEN matches.data_coverage ELSE EXCLUDED.data_coverage END`.

Parent-coverage gate in `phase_team_lists.py`, `phase_stats.py`, `phase_timeline.py`: `_build_match_id_map` now returns `dict[str, tuple[str, str]]` of `(match_id, data_coverage)`; per-archive loop skips matches whose `data_coverage == 'fixture_only'`. Defensive (slug namespaces are disjoint so the gate is a no-op in practice); guards against archive-arrival-order surprises. Each child phase now reports `matches_fixture_only_skipped` in its return dict.

11 new unit tests in `test_phase_matches.py` cover the data_coverage ladder, slug derivation, synthetic-id fallback, draw key regex, and the walker's mc_slugs skip-gate contract.

**Proof:**
- `pytest tests/unit/scripts/data/populate/test_phase_matches.py -v` → **16 passed** (was 5; +11 new).
- `pytest tests/unit/scripts/data/populate/` → **54 passed** (was 43 per Phase 4.5 TASK-34 baseline).
- `pytest tests/unit/` → **366 passed, 0 failed** (was 355; +11). Zero regression.
- `test_dry_run_flag` signature-coverage → 12 passed; `commit: bool` plumbing intact on all four touched phase functions.
- `bash packages/db/migrate.sh --status` → `071_matches_data_coverage.sql` shows applied.
- `psql -c "..."` on local: column exists with default `'full'::text`; CHECK constraint visible with all 4 values; partial index visible (`btree (data_coverage) WHERE data_coverage <> 'full'::text`); `SELECT data_coverage, COUNT(*) FROM matches GROUP BY 1` → 5292 rows / `full`.
- End-to-end: `python -m scripts.data.populate_db_from_s3 --phase matches --dry-run --seasons 2026` → exit 0; `parsed 204 rows total (mc: 204 read, 0 failed, 0 skipped; draw: 27 read, 0 failed, 0 emitted, 204 skip-mc-exists, 0 skip-no-team)`; `inserted=0 updated=204`; `--dry-run rolling back all changes`. Post-run DB unchanged.
- `git diff --stat HEAD` covered exactly the 6 expected files; `services/web/.claude/` untracked dir left alone via explicit pathspec staging.

**adversarial-reviewer: PASS WITH CONCERNS** — 7 non-blocking concerns, all sanctioned by spec/precedent: (C1) migration renumber 061→071 documented; (C2) `_derive_data_coverage` degenerate fallback chooses `'fixture_only'` rather than `'full'`, defensible via slug-disjoint design + non-downgrade upsert + dedicated unit test pin; (C3) `_extract_from_draw_fixture` slug identity scheme documented as spec impossibility resolution; (C4) `idx_matches_data_coverage` partial index added beyond spec — small/cheap/useful; (C5) pre-existing inline `import json` style in `_metadata_blob`/`_draw_metadata_blob` unchanged from HEAD — pattern matches sibling code, not regressed; (C6) untracked `services/web/.claude/.simplify-ok` honoured via explicit pathspec; (C7) `data-lineage/matches.md` doc update deferred to TASK-46 per plan's deliberate split. **/simplify:** not run (`[skip-simplify]` per Phase 4 convention; pure additive era-aware refactor).

### TASK-38 — archive_only=true mode on 4 nrl.com routes (draw, match-centre, ladder, stats) (`5e6a95e`)
Added `archive_only: bool = Query(default=False)` to the four nrl.com archive-only route endpoints, threaded into the inner `run_*` functions. When `True`: S3 capture still happens (it's before the parse); `Model.model_validate` is **skipped entirely** (NOT try/caught); response carries `validated:false, validation_skipped:true`. When `False` (default): existing daily-cron behaviour unchanged.

**Spec-text vs spec-test reconciliation:** TASKS.md:34 used a literal `try: model_validate(); except ValidationError: ...` pattern, but its own case-2 unit test (line 47-48) demanded `validated:false` on a valid payload — only the unconditional-skip variant could satisfy that. PLAN.md:50 corroborated with "the strict-parse is skipped entirely". Implementer chose unconditional skip; spec-test was load-bearing over spec-text.

Match-centre is the structural odd one out: the per-match strict-parse runs inside the walker loop with `try/except ValidationError → validation_failures.append(...)` (non-aborting). The new `if not archive_only:` guard wraps that inner block — when the flag is on, `validation_failures` stays empty (no per-match parse runs). Envelope-level `validated:false, validation_skipped:true` are set after the walk.

13 unit tests across 4 new test files: `test_archive_only_true_skips_validation_on_drift`, `test_archive_only_true_modern_payload_still_archives`, `test_archive_only_default_false_unchanged_modern` per route (draw also has a 4th `archive_response_called_under_archive_only` check). Mocking pattern: `_FakeRun` stand-in for `DeterministicScoutRun`; patch the module-level `fetch_*`, `archive_response`, `start_deterministic_run`. Match-centre additionally patches `fetch_match_centre` + `time.sleep` to skip the 1-second per-match rate-limit.

**Proof:**
- `pytest tests/unit/api/scout/nrlcom_*/test_archive_only.py -v` → **13 passed** (exceeds ≥12 bar; 4+3+3+3).
- `pytest tests/unit/api/scout/` → **86 passed** (was 73 per Phase 4.5 TASK-32 baseline; +13).
- `pytest tests/unit/` → **379 passed** (was 366 after TASK-37; +13). Zero regression.
- Route imports clean post-edit: `python -c "import app.scout.{nrlcom_draw,nrlcom_match_centre,nrlcom_ladder,nrlcom_stats}.routes"` → all four `ok`.
- `git diff --stat HEAD~` shows exactly: 4 modified routes + 4 new test files = 8 files. `services/web/.claude/` untracked left alone via explicit pathspec.

**Live curl verification deferred** per the **Phase 4.5 TASK-30 precedent** (`/openapi.json` confirmed the API on :8000 is a pre-TASK-38 process — implementer chose not to restart to avoid disrupting the user's session). The unit tests cover the same response-shape contract end-to-end; live confirmation picks up at the TASK-45 prod sweep or any subsequent API restart.

**adversarial-reviewer: PASS WITH CONCERNS** — 4 non-blocking concerns, all sanctioned: (C1) doc updates batched to TASK-46 per plan's deliberate split; (C2) live-curl deferred per Phase 4.5 TASK-30 precedent; (C3) match-centre default-path assertion form noted as unusual but sound on inspection (`"validated" not in response or response.get("validated") is None`); (C4) spec interpretation question — implementer chose unconditional-skip per the case-2 test demand; PLAN.md corroborates. **/simplify:** not run (`[skip-simplify]` per Phase 4 convention).

---

## How we know it's done (running)
Phase 5 is in flight. After TASK-37: the canonical schema has the `data_coverage` column; the era-aware projection logic exists and is unit-tested; the walker correctly handles the slug-disjoint identity scheme end-to-end against real S3 (verified via dry-run). 9 tasks remain (38-46): three more code tasks, four operator backfills, the extractor sweep, and the docs closure.

## Decisions & deviations
- **Migration number 071 (not 061).** Planner missed that 061..070 already exist. Implementer chose next-free. Future references to "the Phase 5 migration" should read 071.
- **`_derive_data_coverage` degenerate fallback = `'fixture_only'` (not `'full'`).** Spec wording "default still 'full'" was about the column-default in the migration, not the function's no-stats/no-rosters/no-timeline edge case. Implementer chose `'fixture_only'` because the non-downgrade CASE prevents poisoning existing rows; pinned by `test_data_coverage_derivation_thresholds`.
- **Draw `external_match_id` = slug, not `fixture.matchId`.** Spec wording was impossible (draw fixtures have `matchId: null`). Slug from `matchCentreUrl` for modern fixtures; synthetic `{home}-v-{away}-r{NN}-{season}` for pre-1990. Two teams with identical nicknames in pre-1908 archives would collide (extremely unlikely; acceptable).
- **Slug-disjoint identity scheme.** Match-centre keeps using `payload.matchId` (e.g., `'20261111210'`); draw-only uses slug. Walker pre-builds `mc_slugs` set so draw-only rows are only emitted for fixtures lacking a corresponding match-centre archive — no upsert collisions possible. The trust hierarchy (match-centre wins) is enforced by the non-downgrade CASE in the UPSERT.
- **Extra partial index `idx_matches_data_coverage` added.** Small/cheap; supports the TASK-45 verification queries that group by `data_coverage`. Not in spec; flagged in reviewer concerns; accepted.

## Outstanding
- ☐ TASK-38 through TASK-46 (9 remaining tasks). See [TASKS.md](../TASKS.md).
- ☐ Documentation sweep for `matches.data_coverage` deferred to TASK-46 (per the plan's deliberate split — all Phase 5 doc changes coalesce at closure once row counts are known).

## Lessons learned
- **Always enumerate the migrations folder before assigning a number in a plan.** The planner used "061" by counting +1 from Phase 4.5's `060_stat_leaderboards.sql` without checking what came after. Six other migrations (`061_sc_editorial_seed.sql` through `070_dedup_metrics_snapshots.sql`) had landed since. Implementer caught it at task pickup; cost was a one-line proof-note. Adding this as an open question for META.
- **Spec wording can be plainly impossible against the data.** "External_match_id from fixture.matchId" sounded fine until the implementer inspected the actual draw fixture and found `matchId: null`. The right move was to derive an unambiguous correct interpretation (slug-from-URL) and document it, not block on ambiguity — there was no ambiguity, just a planner-side data-shape miss.
- **psql isn't on PATH in Git Bash on Windows.** The user has PostgreSQL 17 installed at `C:\Program Files\PostgreSQL\17\bin\psql.exe` but `make migrate` (which runs `bash packages/db/migrate.sh`) fails with `psql: command not found`. Worked around with `PATH="/c/Program Files/PostgreSQL/17/bin:$PATH" bash packages/db/migrate.sh`. Adding to META environment section.

## Commits
- `4458a24` planner kickoff — Phase 5 plan + 10 tasks queued
- `da5423d` TASK-37 — migration 071 + era-aware populate_matches + parent-coverage gate
- `1dc4cee` TASK-37 checkoff — run report + META psql/Windows note
- `5e6a95e` TASK-38 — archive_only=true mode on 4 nrl.com routes (this checkoff)
