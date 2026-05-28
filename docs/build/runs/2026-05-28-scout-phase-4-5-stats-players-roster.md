# Scout Phase 4.5 — nrl.com stats + players roster (D8 harden, schedule, seed)

**Date:** 2026-05-28 · **Status:** 🟡 In flight (1 of 8 tasks shipped) · **Plan:** Scout Phase 4.5 (active — see [PLAN.md](../PLAN.md))

**TL;DR** — Phase 4.5 is a Phase 4-style hardening replay: both `services/api/app/scout/nrlcom_stats/` and `services/api/app/scout/nrlcom_players_roster/` ingest folders already exist with fetchers / routes / READMEs / make targets; migration `060_stat_leaderboards.sql` is applied; `populate_stat_leaderboards` is shipped and wired into `populate_db_from_s3.py` as `--phase leaderboards`; the lineage + catalogue docs already exist. What's missing is the D8 drift contract, extractor unit tests via pure-function refactor, cron scheduling, and prod seed verification. NRL only (comp 111), season 2026, forward-only — historical backfill stays Phase 5. SC Draft mode and folding `nrlcom_refresh.py` are explicitly scoped out (2026-05-28 planner interview).

---

## What was completed

### TASK-29 — nrlcom-stats: D8 strict models (envelope + 3 nested) + fixture + unit drift tests (`f232c84`)
Added the D8 drift contract for the `nrlcom-stats` pipeline. Captured the live `/stats/data?competition=111&season=2026` response (2026-05-28 — 8 player + 8 team categories, 70 subgroups total, 182 player + 165 team leaders, 460KB) to `tests/fixtures/scout/nrlcom_stats/canonical_response.json`. Created `services/api/app/scout/nrlcom_stats/models.py` with four strict `BaseModel`s (`extra="forbid"`):
- `NrlcomStats` (envelope) — `playerStats: list[StatCategory]`, `teamStats: list[StatCategory]`, plus `filterCompetitions` / `filterSeasons` / `selectedCompetitionId` / `selectedSeasonId` (6 keys observed live).
- `StatCategory` (one of `<scope>Stats[]`) — `title: str` (load-bearing for the `category` DB column), `groups: list[StatSubgroup]`. Clean uniform shape across both scopes.
- `StatSubgroup` (one of `groups[]`) — `title: str` (load-bearing for `subgroup`/`stat_title`), `statId: int | None`, `leaders: list[StatLeader]`, `url: str | None`.
- `StatLeader` (one of `leaders[]`) — single model handles BOTH player-scope and team-scope leaders. The 7 universal keys (`played` / `playerId` / `teamId` / `teamName` / `teamNickName` / `theme` / `value`) are required-present-but-nullable (the `NrlcomDraw.disclaimer` convention). The 4 player-only fields (`firstName` / `lastName` / `headImage` / `bodyImage`) plus `url` default to `None` because they're legitimately absent on team leaders — the same pattern `NrlcomDraw.videoProviders` uses for state-bifurcated keys (`videoProviders: list[dict[str, Any]] | None = None` at `nrlcom_draw/models.py:43`).

**Design deviation from literal spec (documented):** `value` typed `str | None` (stricter than the plan's `float|int|str|None`) — all 347 observed leaders are `str` (e.g. `"134"`); the extractor coerces via `float(leader.get("value"))`; a future numeric `value` would surface as drift, the correct D8 behaviour. Player-only fields use the `= None` default instead of the plan's literal "required-present" wording, because team-scope leaders genuinely omit those keys. Trade-off documented in `StatLeader`'s docstring: drift on a player-only field's rename/removal no longer trips, but `extra="forbid"` still catches new keys and rename/removal of the universal keys still trips.

Added `tests/unit/api/scout/nrlcom_stats/{__init__.py,test_models.py}` (templated on the casualty/ladder unit tests): 4 cases — `test_canonical_fixture_parses` (asserts both player-scope leaders carry `firstName` AND team-scope leaders correctly default it to `None`, proving the bifurcation handling); `test_unknown_top_level_field_raises` (`loot_boxes`); `test_unknown_leader_field_raises` (`is_retired` on the first leader — proves the deepest-level strict-parse fires); `test_missing_required_category_title_raises`. Route wiring deliberately deferred to TASK-30.

**Proof:** `pytest tests/unit/api/scout/nrlcom_stats/test_models.py -v` → **4 passed in 1.73s**; `pytest tests/unit/api/scout/` → **69 passed in 1.85s** (was 65 pre-task; no regression); full unit tier `pytest tests/unit/` → **345 passed** (reviewer cross-verified). `python -c "from app.scout.nrlcom_stats.models import NrlcomStats, StatCategory, StatSubgroup, StatLeader; print('ok')"` → `ok`. Live shape probe before fixture capture confirmed exactly 2 distinct player-leader keysets (11 keys / 12 keys — `url` sometimes missing) and 1 team-leader keyset (8 keys), informing the player-vs-team bifurcation. Route file confirmed untouched (TASK-30 boundary intact). **adversarial-reviewer: PASS WITH CONCERNS** — all non-blocking: (C1) `value: str | None` narrower than literal spec; (C2) player-only field defaults documented with in-repo precedent; (C3) plan's "102 passed" baseline in TASK-29's How-to-verify was inaccurate — the substantive regression check (no regression vs pre-task) is satisfied. **/simplify:** not run (`[skip-simplify]` flag per Phase 4 convention; pure additive D8 contract).

---

## How we know it's done (running)
- Unit drift tests green in CI for `nrlcom_stats` envelope + 3 nested levels. Live drift test (env-flagged `SCOUT_DRIFT_LIVE=1`) lands in TASK-30.

## Decisions & deviations
- **`StatLeader` is a single model, not a `Union[PlayerLeader, TeamLeader]`.** Pydantic discriminated unions need an in-record discriminator; the scope discriminator is at the OUTER list level (`playerStats` vs `teamStats`), not on the leader itself. Single-model with defaulted player-only fields keeps the implementation simple while still firing on new-key drift via `extra="forbid"`. Documented in the model docstring.
- **`value: str | None` is stricter than the spec's `float | int | str | None` union.** Empirical reality: every leader in 347 observed has a string value. The strictness is a D8-aligned choice — a future native-number `value` becomes drift, which is the correct behaviour, not a silent acceptance.

## Outstanding (deferred — operator/time-gated and surfaced infra follow-ups)
- ☐ **TASK-30 → TASK-36:** the remaining 7 tasks of Phase 4.5 (in the queue).
- ☐ Same cross-cutting **extractor scheduling** infra follow-up that Phase 4 surfaced — the daily ingest cron archives to S3 but the DB only refreshes when an operator runs `populate_db_from_s3 --phase leaderboards`. Same gap will apply to `nrlcom_players_roster` (which ships NO DB extractor this phase per scope decision). Durable fix is baking `scripts/` + `packages/shared` into the api image so a scheduled `docker exec jeromelu-api python -m scripts.data.populate_db_from_s3 …` just works — an infra decision for the human/planner. Out of Phase 4.5 scope.

## Lessons learned
_(populated as tasks ship)_

## Commits
`068f37a` (planner kickoff — Phase 4.5 plan + 8 tasks queued, missed at the planner session boundary) · `f232c84` (TASK-29). Bookkeeping commit for TASK-29 checkoff follows.
