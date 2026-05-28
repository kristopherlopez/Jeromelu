# Jaromelu Build Plan

This document holds active and historical plan docs that drive the persistent task queue in [TASKS.md](./TASKS.md). Plans are written by the `planner` agent (or a planning session) and consumed by the `implementer`.

## What good looks like

A good plan doc is:

- **Self-contained** — readable cold by an implementer with no prior conversation context.
- **Interface-level** — names file paths, types, function signatures, table columns, API shapes, env vars. No "figure out the right shape".
- **End-to-end verifiable** — explicit "how do we know this is done" strategy, runnable from the outside (curl, CLI, screenshot, query).
- **Iterated to high quality** before any task is appended. A plan that ships fuzzy tasks burns implementer time on re-asking.

Plans link to the tasks they spawn. Tasks link back to the plan section they implement.

---

## Active plan

### 2026-05-28: Engineering quality hardening — Tier 1 (Ruff + Pyright + ESLint + Gitleaks + deploy gating)

**Goal:** Convert Tier 1 of [`docs/operations/engineering-quality-hardening.md`](../operations/engineering-quality-hardening.md) (items 1–6) from a backlog of "review caught it" review-concerns into mechanically enforced CI gates, with matching project invariants in [`META.md`](./META.md). After this lands, every PR is checked for: Python lint+format (Ruff), Python typecheck (Pyright, narrow), web lint (ESLint), secrets (Gitleaks), and deploy will refuse to ship on a red `tests.yml` run.

**Constraints (load-bearing):**
- **Hard-fail from day 1, scoped narrow.** Each new CI job ships with a tight include set that's already clean — no `continue-on-error`, no warning-only purgatory. Widening the scope is a follow-up task in a future plan, not a deferred concern in this one.
- **Each enforcement task lands its corresponding META invariant in the same diff.** Rule + enforcement together — never one without the other.
- **Phase-5 backfill (TASK-41–46) is unaffected.** The deploy gating change (TASK-51) is the only behaviour-altering CI change for ops; it lands last, after every signal is green on master.
- **Audit of `datetime.utcnow()` callsites is a non-event.** A repo-wide grep confirmed zero source-tree usages today, so the DTZ rule is green from the moment the config lands — no code refactor in this plan.

**Pre-confirmed picks (locked during planning interview):**
- Type checker: **Pyright** (faster on monorepos; same engine as Pylance for IDE consistency; configured via `[tool.pyright]` in root pyproject).
- Secret scanner: **Gitleaks** (single binary, sensible defaults, no baseline-curation overhead).
- Deploy gating mechanism: **`workflow_run` trigger** on `deploy.yml`. Tests run first; deploy follows only on success. Keeps the two workflows file-separated and the gate explicit.
- Initial Pyright include set: **`packages/shared/jeromelu_shared/`** only. Wider includes (`services/api/app/`, `packages/db/`, key workers) are explicit follow-ups in a future plan — not deferred concerns of this one.

**Interface:**

- **Root `pyproject.toml` (new file):**
  ```toml
  [tool.ruff]
  line-length = 100
  target-version = "py312"
  extend-exclude = [
    ".venv", "**/.venv", "**/node_modules", "**/migrations",
    "data", "scripts/data/scraped_*",
  ]

  [tool.ruff.lint]
  # E/F = pycodestyle + pyflakes, I = isort, B = bugbear,
  # DTZ = datetime-tz invariant, UP = pyupgrade, RUF = ruff-specific.
  select = ["E", "F", "I", "B", "DTZ", "UP", "RUF"]
  ignore = []

  [tool.ruff.lint.per-file-ignores]
  "tests/**/*.py" = ["DTZ", "B011"]  # fixtures may use naive dt; allow assert False
  "**/conftest.py" = ["DTZ"]

  [tool.ruff.format]
  quote-style = "double"

  [tool.pyright]
  include = ["packages/shared/jeromelu_shared"]
  exclude = ["**/.venv", "**/node_modules", "**/__pycache__"]
  pythonVersion = "3.12"
  typeCheckingMode = "standard"
  reportMissingImports = "error"
  reportGeneralTypeIssues = "error"
  ```

- **`requirements-dev.txt` (extend, additive only):**
  ```
  ruff>=0.6,<1
  pyright>=1.1.380,<2
  ```

- **`Makefile` (new targets, appended near the existing `test` block):**
  ```
  # Python lint via Ruff. Hard-fail on any violation. Scope mirrors the
  # CI ruff job — services, packages, scripts, tests.
  lint-python:
  	ruff check services packages scripts tests
  	ruff format --check services packages scripts tests

  # Python autoformat + import-sort via Ruff. Run before committing.
  format-python:
  	ruff format services packages scripts tests
  	ruff check --fix services packages scripts tests

  # Python typecheck via Pyright. Scope is pinned in pyproject.toml
  # [tool.pyright] (narrow to packages/shared/jeromelu_shared for now).
  typecheck-python:
  	pyright

  # ESLint over services/web (Next.js config, already configured).
  lint-web:
  	cd services/web && npm run lint

  # Umbrella — what CI runs (minus pytest).
  lint:
  	$(MAKE) lint-python
  	$(MAKE) lint-web
  	$(MAKE) typecheck-python
  ```
  Update the `.PHONY:` line at the top of the Makefile to include these targets.

- **`.github/workflows/tests.yml` (extend, 5 new jobs alongside the existing `unit` + `web-typecheck`):**

  | Job | Step | Hard-fail? | Cache |
  |---|---|---|---|
  | `ruff` | `pip install ruff==X.Y.Z` (pinned from `requirements-dev.txt`) → `ruff check services packages scripts tests` → `ruff format --check services packages scripts tests` | Yes | pip |
  | `pyright` | `pip install -r requirements-test.txt -r requirements-dev.txt` (resolves shared package's transitive types) → `pyright` | Yes | pip |
  | `web-lint` | `npm ci` in `services/web` → `npm run lint` | Yes | npm |
  | `gitleaks` | `gitleaks/gitleaks-action@v2` with `GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}` (free for OSS; skip env var if license-free posture) → fail on any finding | Yes | n/a |

  Each job mirrors the existing `unit` / `web-typecheck` shape: `runs-on: ubuntu-latest`, `actions/checkout@v6`, then setup-python or setup-node, then the check. Concurrency / cache-key conventions match the existing jobs.

- **`.gitleaks.toml` (new file, minimal):**
  ```toml
  [extend]
  useDefault = true

  # Allowlist entries get added here only after a first-run scan surfaces
  # false positives (e.g. fixture JSON containing example-format AWS keys).
  # Document each entry inline with a one-line rationale.
  [allowlist]
  description = "Allowlisted false-positives for Jaromelu fixtures."
  paths = []
  regexes = []
  ```

- **`.github/workflows/deploy.yml` (modify trigger to gate on Tests success):**
  ```yaml
  on:
    workflow_run:
      workflows: [Tests]
      types: [completed]
      branches: [master]
    workflow_dispatch:
  ```
  Add to the top of every job (or at minimum `detect-changes`, which everything else `needs:`):
  ```yaml
  if: >-
    github.event_name == 'workflow_dispatch' ||
    github.event.workflow_run.conclusion == 'success'
  ```
  Replace every `${{ github.sha }}` reference inside the workflow with `${{ github.event.workflow_run.head_sha || github.sha }}` so that image-tag SHAs match what `tests.yml` actually validated. The fallback to `github.sha` covers the `workflow_dispatch` path where `workflow_run` context is absent.

- **`docs/build/META.md` (extend with two new invariant subsections under `## Project invariants`):**
  - **`### Datetime / timezone`** — Use timezone-aware datetimes. Store and compare UTC at DB/API boundaries. Never `datetime.utcnow()` — prefer `datetime.now(timezone.utc)`. Pure-data fixtures under `tests/` are exempt. Enforced by Ruff `DTZ` rules; CI fails on violation.
  - **`### Secret hygiene`** — Never commit `.env*`, tokens, API keys, prod credentials, or any high-entropy string that looks like a secret. Redact secrets from logs, issue comments, PR descriptions, and run reports. Enforced by Gitleaks in CI; CI fails on any finding. False positives go in `.gitleaks.toml` with an inline rationale, never inline `# gitleaks:allow` comments.

- **`docs/ops/ci-cd.md` (modify — `tests.yml` and `deploy.yml` sections):**
  - `tests.yml` table row updates to list all 6 jobs.
  - New "Quality gates" subsection naming each tool, what it catches, and how to silence a false positive (per-file-ignore for Ruff; `# pyright: ignore[reportXxx]` for Pyright; `.gitleaks.toml` for secret-scanner; ESLint inline disables for ESLint).
  - `deploy.yml` "What is NOT in this pipeline" entry for "Tests + web typecheck" gets flipped: the gate now exists; describe the `workflow_run` mechanism and how to override via `workflow_dispatch` for emergency deploys.

- **`docs/operations/engineering-quality-hardening.md` (modify):**
  - Tier 1 items 1, 2, 3, 4, 5, 6 each get a `**Status:** ✅ Shipped 2026-05-28 — see [run report](../build/runs/2026-05-28-eng-quality-tier-1.md)` line.
  - Update "Current Baseline" section to reflect: Ruff configured + CI; Pyright configured (narrow); web lint in CI; Gitleaks in CI; deploy gated on tests.yml.
  - Suggested Implementation Order list stays — items 1–6 are now historical; items 7+ remain as the next-up backlog.

**Files touched:**
- `pyproject.toml` (new — root)
- `requirements-dev.txt` (extend)
- `Makefile` (extend `.PHONY` + 5 new targets)
- `.github/workflows/tests.yml` (4 new jobs)
- `.github/workflows/deploy.yml` (trigger + conditional gate + sha references)
- `.gitleaks.toml` (new)
- `docs/build/META.md` (2 new invariant subsections)
- `docs/ops/ci-cd.md` (tests.yml + deploy.yml sections updated; new Quality gates subsection)
- `docs/operations/engineering-quality-hardening.md` (Tier 1 ✅ markers + baseline update)
- `docs/build/runs/2026-05-28-eng-quality-tier-1.md` (run report — created on first checkoff)
- Zero source-code files touched. Confirmed via pre-planning grep: no `datetime.utcnow()` callsites exist; Pyright initial include is `packages/shared/jeromelu_shared/` which is already type-clean modulo whatever the first run surfaces (any fixes there are bounded to <5 files per the implementer's discretion — flagged as a Concern if larger).

**Verification strategy:**

End-to-end (each is a discrete, observable outcome — run AFTER all six tasks ship):
1. **Ruff catches a violation in CI.** On a throwaway branch, add `import os` to a file that doesn't use it, push, observe `ruff` CI job FAIL. Revert. Verify CI on the revert is green.
2. **Pyright catches a type error in CI.** On the same throwaway branch, modify a return-typed function in `packages/shared/jeromelu_shared/scraping/nrl.py` to return a wrong type, push, observe `pyright` CI job FAIL. Revert.
3. **ESLint catches a violation in CI.** Add an unused import to `services/web/src/app/page.tsx`, push, observe `web-lint` CI job FAIL. Revert.
4. **Gitleaks catches a fake secret in CI.** Add the canonical `AKIAIOSFODNN7EXAMPLE` literal to a temp file in the branch, push, observe `gitleaks` CI job FAIL. Revert.
5. **Deploy refuses to run on a red Tests run.** Push commit (2)/(3)/(4) above (any one — the Pyright case is convenient). Open the Actions tab. Confirm `Tests` workflow finishes red; confirm `Build & Deploy` did NOT start (no `workflow_run` trigger because conclusion ≠ success).
6. **Deploy proceeds normally on a green Tests run.** After reverting all of the above, push a tiny no-op commit (a single-character README tweak). Confirm `Tests` runs green; confirm `Build & Deploy` then runs (and either deploys or no-ops via path-filter); confirm the image-tag SHA in the deploy log matches the commit SHA.
7. **Emergency `workflow_dispatch` of deploy.yml still works** even if Tests was red on the latest master push. Verify by manually dispatching once and observing the build proceeds independently of the gating condition.

Tests (local invariants, runnable any time):
- `make lint-python` exits 0 on master.
- `make typecheck-python` exits 0 on master.
- `make lint-web` exits 0 on master.
- `make test` exits 0 on master (no regressions).
- `gitleaks detect --redact --source=. --no-banner --exit-code 1` exits 0 on master (locally, sanity check before merging the gitleaks task).
- `make lint` (the umbrella) chains all three and exits 0.

**Documentation updates:**
- `docs/build/META.md` — new `### Datetime / timezone` and `### Secret hygiene` invariant subsections.
- `docs/ops/ci-cd.md` — tests.yml table row updated to list 6 jobs; new "Quality gates" subsection; deploy.yml section updated to document the `workflow_run` gate + the `workflow_dispatch` override.
- `docs/operations/engineering-quality-hardening.md` — Tier 1 items 1–6 marked ✅ Shipped with run-report link; "Current Baseline" reflects new state.
- `Makefile` — new targets self-document via header comments per existing convention.
- `docs/build/runs/2026-05-28-eng-quality-tier-1.md` — run report (created on first checkoff per META ritual); newest-first row in `docs/build/runs/README.md`.
- `docs/build/PLAN.md` — plan removed from "Active plan" at closure.

**Tasks:**
- TASK-47: Ruff plumbing — root `pyproject.toml [tool.ruff]` + `requirements-dev.txt` + Make targets + CI job + datetime META invariant
- TASK-48: ESLint CI job + `lint-web` Make target
- TASK-49: Pyright plumbing — root `pyproject.toml [tool.pyright]` (scope `packages/shared/jeromelu_shared`) + `requirements-dev.txt` + Make target + CI job
- TASK-50: Gitleaks plumbing — `.gitleaks.toml` + CI job + secret-hygiene META invariant
- TASK-51: Deploy gating — flip `deploy.yml` to `workflow_run` trigger; verify gate via 3-commit dry run (red → no-deploy, revert → deploys, dispatch → deploys)
- TASK-52: Closure — `engineering-quality-hardening.md` Tier 1 items ✅; `ci-cd.md` updated; run report → 🟢 Shipped; PLAN.md "Active plan" cleared

---

### 2026-05-28: Scout Phase 5 — Historical backfill + standard-data-model conformance

**Goal:** Land historical NRL/SuperCoach data in the **canonical DB schema** across every era reachable per [D12](../agents/crew/scout/charter.md#d12-backfill--harvest-history-once) — fixtures back to **1908**, match-centre detail back to **2000** (partial 1990–1999), ladders back to ~**1996**, leaderboards back to **2013**, SC stats back to **2018**, SC roster/teams/settings back to **2024** — with every row obeying the same column contract as modern rows. Era variance is reconciled by NULLs + a new `matches.data_coverage` column; raw shape variance lives in S3 archives; D8 strict-parse stays modern-only to keep daily-cron drift detection load-bearing.

**Constraint (load-bearing — user-set 2026-05-28):** *"all the data needs to conform to a standard data model."* The canonical DB schema is that model. Pre-2000 match-centre lacks lineups/stats/officials; pre-1990 has only fixture data; pre-2013 has no stat leaderboards endpoint. Those gaps land as NULLs in the same modern columns + a `data_coverage` marker on `matches`, **never** as alternate tables, JSONB blobs, or skipped rows. Era-tolerance lives in extractors, not in strict Pydantic models.

**Other constraints:**
- Polite rate-limit: **1 req/sec per origin** (nrl.com, supercoach.com.au, nrlsupercoachstats.com share their own rates).
- Operator-driven; runs on the **prod box via loopback** (Phase 4.5 seed pattern — `docker cp scripts/ jeromelu-api:/runtmp/`, `curl --resolve api.jeromelu.ai:443:127.0.0.1`).
- Idempotency preserved: S3 paths = identity; re-running daily cron over backfilled ranges is a no-op (S3 overwrite, DB upsert).
- **Out of scope per D12:** casualty-ward (current-only), nrl.com per-team roster (`/players/data` — current-only).

**Interface:**

- **Migration `061_matches_data_coverage.sql`:**
  - `ALTER TABLE matches ADD COLUMN data_coverage text NOT NULL DEFAULT 'full';`
  - `ALTER TABLE matches ADD CONSTRAINT matches_data_coverage_chk CHECK (data_coverage IN ('full', 'lineups+timeline', 'timeline_only', 'fixture_only'));`
  - Existing rows default to `'full'` (today's matches table is 2024+ match-centre data).
  - Semantic values per era band:
    - `'full'` — 2000+: matches + match_team_lists + player_match_stats + match_timeline + match_officials all populated.
    - `'lineups+timeline'` — rare partial (2000s payloads occasionally missing stats); future-proofing.
    - `'timeline_only'` — 1990–1999: matches + match_timeline only.
    - `'fixture_only'` — 1908–1989: matches only (from draw archive; no match-centre slug exists).

- **`archive_only=true` query param** on 5 routes (default False — daily cron behaviour unchanged):
  - `POST /api/admin/scout/nrlcom-draw?...&archive_only=true`
  - `POST /api/admin/scout/nrlcom-match-centre?...&archive_only=true`
  - `POST /api/admin/scout/nrlcom-ladder?...&archive_only=true`
  - `POST /api/admin/scout/nrlcom-stats?...&archive_only=true`
  - `POST /api/admin/scout/supercoach-stats?...&archive_only=true`
  - When True: S3 archive still happens; D8 strict-parse wrapped in `try/except ValidationError → detail["validation_skipped"]=True` (no 500); for **SC stats only**, the inline `_upsert_player_rounds` call is also skipped (response carries `upserted=0, validation_skipped=True`).
  - Response field discipline: `validated:false` AND `validation_skipped:true` when the historical path is taken; `validated:true` AND `validation_skipped:false` (the latter omitted or false) on modern path.

- **New extractor `scripts/data/populate/phase_player_rounds.py`:**
  - `populate_player_rounds(db, *, seasons: list[int], commit: bool = True) -> dict[str, Any]`
  - Reads `scout/nrlsupercoachstats/stats/{season}/round-{NN}.json` archives (which carry `{season, round, rows}` per the existing route's S3 payload shape).
  - Pure-function extractor `_extract_player_round_rows(payload, *, season, round) -> list[dict]` per the Phase 4.5 `_extract_leader_rows` pattern.
  - Bulk-upserts to `player_rounds` with the same `ON CONFLICT (player_id, round, season)` rule the inline route uses.
  - Wired into `populate_db_from_s3.py` as `--phase player_rounds`; added to `PHASES` tuple in FK-correct position (after `matches`/`stats`).
  - `--seasons` arg in the orchestrator already accepts arbitrary lists — the default `[2024, 2025, 2026]` is overridden in the verification step.

- **Era-aware `populate_matches` in `scripts/data/populate/phase_matches.py`:**
  - Today: walks `scout/nrlcom/match-centre/*` only.
  - **After:** also walks `scout/nrlcom/draw/*` and emits a `data_coverage='fixture_only'` match for every draw fixture that lacks a corresponding match-centre archive at `scout/nrlcom/match-centre/{comp}/{season}/round-{NN}/{slug}.json`.
  - Detection logic (NOT year-band hard-coded — robust to odd years):
    - Match-centre present → `_extract_one` runs; the returned dict gets `data_coverage='full'` if `stats` is present, `'lineups+timeline'` if `players` is present but `stats` absent, `'timeline_only'` if only `timeline` is present.
    - Match-centre absent → draw-only fixture row with `data_coverage='fixture_only'`. New helper `_extract_from_draw_fixture(fixture, season, round, comp, team_map, venue_map) -> dict` does the projection.
  - For 1990–1999, `populate_team_lists`, `populate_player_match_stats`, `populate_timeline_and_officials`, `populate_player_match_stats` skip matches with `data_coverage NOT IN ('full', 'lineups+timeline')` for the parent FK — no orphan rows.

- **`scripts/data/scout_backfill.py` driver hardening:**
  - New flag `--archive-only` (default False) — appends `archive_only=true` to every POST.
  - New flag `--resume` (default False) — before each POST, HEAD the expected S3 key; skip if present.
  - New flag `--force` (default False) — overrides `--resume`.
  - Per-source S3-key derivation table (module-level constant `S3_KEY_FN`) so resume can compute the expected key from `(source, competition, season, round)`.
    - `nrlcom-draw` → `scout/nrlcom/draw/{comp}/{season}/round-{NN}.json`
    - `nrlcom-ladder` → `scout/nrlcom/ladder/{comp}/{season}/round-{NN}.json`
    - `nrlcom-stats` → `scout/nrlcom/stats/{comp}/{season}.json` (no round)
    - `supercoach-stats` → `nrlsupercoachstats/stats/{season}/round-{NN}.json`
    - `nrlcom-match-centre` (special) → resume operates at round level via S3 LIST (`scout/nrlcom/match-centre/{comp}/{season}/round-{NN}/` prefix non-empty → skip).
    - `supercoach-roster/teams/settings` → resume not implemented (trivial scope, 6 GETs total).
  - Bucket override env: respects `S3_CLEAN_BUCKET` (defaults to `jeromelu-clean-documents` per existing archive code).

- **5 pipeline README updates** under `services/api/app/scout/<pipeline>/README.md` — document the `archive_only=true` mode and when to use it (historical backfill only; daily cron leaves it default-false). For match-centre, document the 1990–1999 partial-shape expectation and how `data_coverage` reflects it.

**Files touched:**
- `packages/db/migrations/061_matches_data_coverage.sql` (new)
- `services/api/app/scout/nrlcom_draw/routes.py`
- `services/api/app/scout/nrlcom_match_centre/routes.py`
- `services/api/app/scout/nrlcom_ladder/routes.py`
- `services/api/app/scout/nrlcom_stats/routes.py`
- `services/api/app/scout/supercoach_stats/routes.py`
- `scripts/data/populate/phase_matches.py` (era-aware projection + new `_extract_from_draw_fixture` helper)
- `scripts/data/populate/phase_team_lists.py` / `phase_stats.py` / `phase_timeline.py` (parent-coverage gate)
- `scripts/data/populate/phase_player_rounds.py` (new)
- `scripts/data/populate_db_from_s3.py` (register `player_rounds` phase)
- `scripts/data/scout_backfill.py` (resume + archive_only flags + key-derivation table)
- `tests/unit/api/scout/{nrlcom_draw,nrlcom_match_centre,nrlcom_ladder,nrlcom_stats,supercoach_stats}/test_archive_only.py` (new × 5)
- `tests/unit/scripts/data/populate/test_phase_matches.py` (era-aware unit tests — augmented)
- `tests/unit/scripts/data/populate/test_phase_player_rounds.py` (new)
- `tests/unit/scripts/data/test_scout_backfill.py` (new — resume + key-derivation tests with mocked S3)
- `docs/agents/crew/scout/roadmap.md` (Phase 5 → ✅ Shipped)
- `docs/agents/crew/scout/charter.md` (D12 status flags + data_coverage decision recorded)
- `docs/operations/data-lineage/matches.md` (new column + era-banded row count breakdown)
- `services/api/app/scout/{nrlcom_draw,nrlcom_match_centre,nrlcom_ladder,nrlcom_stats,supercoach_stats}/README.md` (archive_only mode documented)
- `scripts/data/populate/README.md` (new `--phase player_rounds` row)
- `docs/build/runs/2026-05-28-scout-phase-5-historical-backfill.md` (run report — created on first checkoff per META ritual)

**Verification strategy:**

- **End-to-end (the bar for "done"):**
  - **S3 object counts** per pipeline match D12 expectation ±10%:
    - `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/draw/111/ --recursive | wc -l` ≥ 2700 (1908–2026 × ~25 rounds with rate of empty pre-1920 years)
    - `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/match-centre/111/ --recursive | wc -l` ≥ 4500 (2000–2026 × ~200 matches/year, modulo empty pre-1990s)
    - `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/ladder/111/ --recursive | wc -l` ≥ 600 (~30 seasons × ~24 rounds avg)
    - `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/stats/111/ --recursive | wc -l` = 14 (2013–2026)
    - `aws s3 ls s3://jeromelu-clean-documents/scout/nrlsupercoachstats/stats/ --recursive | wc -l` ≥ 200 (~9 seasons × ~28 rounds incl. Totals)
  - **DB row counts and `data_coverage` distribution:**
    - `SELECT data_coverage, COUNT(*) FROM matches WHERE competition_id=111 GROUP BY data_coverage` shows non-zero rows in `'full'` (≥4500), `'timeline_only'` (≥800 — 1990–1999), `'fixture_only'` (≥2000 — 1908–1989).
    - `SELECT COUNT(*) FROM stat_leaderboards WHERE competition_id=111` ≥ 4500 across 2013–2026.
    - `SELECT COUNT(*) FROM team_standings WHERE competition_id=111` ≥ 600 across covered ladder seasons.
    - `SELECT COUNT(*) FROM player_rounds WHERE season >= 2018` ≥ 150,000.
  - **Spot-checks** (each is a SQL query with an expected non-empty result):
    - `SELECT season, round, status FROM matches WHERE season=1908 AND round=1 ORDER BY id LIMIT 5` → real fixtures, `data_coverage='fixture_only'`, no children in `match_team_lists`.
    - `SELECT m.id, COUNT(t.*) FROM matches m LEFT JOIN match_timeline t ON t.match_id=m.id WHERE m.season BETWEEN 1990 AND 1999 GROUP BY m.id HAVING COUNT(t.*) > 0 LIMIT 5` → matches with timeline rows but `data_coverage='timeline_only'`.
    - `SELECT COUNT(*) FROM player_match_stats WHERE match_id IN (SELECT id FROM matches WHERE season < 2000)` → **0** (no pre-2000 player_match_stats; the parent-coverage gate works).
    - `SELECT data_coverage FROM matches WHERE season=2026 ORDER BY id DESC LIMIT 5` → all `'full'` (regression check — modern path didn't break).
  - **Idempotency check:** re-run `scout-refresh.sh nrlcom-draw` (daily cron path, archive_only NOT set) for the current season+round → returns `validated:true`, `ok:true`; `aws s3 ls` shows the object timestamp updated but the count unchanged.

- **Tests:**
  - Unit (`make test` → all green): per-route archive_only tests (5 files, each ≥3 cases: archive succeeds, validation_skipped=true, default behaviour unchanged); era-aware `populate_matches` tests via 3 small fixtures (match-centre full + match-centre timeline-only + draw-only); `populate_player_rounds` pure-function tests via `_extract_player_round_rows` (mirrors `_extract_leader_rows` pattern); `scout_backfill.py` resume tests with mocked `boto3.head_object`.
  - No new integration tests (live drift tests stay against modern shape — they are NOT historical-shape gates).

**Documentation updates:**
- `docs/agents/crew/scout/roadmap.md` — Phase 5 → ✅ Shipped; what landed; what didn't (deferred list); link to run report.
- `docs/agents/crew/scout/charter.md` — D12 historical-coverage table flipped to show actual S3 row counts post-seed; the data_coverage decision recorded inline under D12 with the standard-data-model rationale.
- `docs/operations/data-lineage/matches.md` — `data_coverage` column documented; era-banded row count breakdown; spot-check queries listed.
- 5 pipeline READMEs (`services/api/app/scout/<pipeline>/README.md`) — `archive_only=true` mode + when to use it.
- `scripts/data/populate/README.md` — new `--phase player_rounds` row in the phase table.
- `docs/build/runs/2026-05-28-scout-phase-5-historical-backfill.md` — run report (created on first task checkoff per META ritual; row added to `docs/build/runs/README.md`).

**Tasks:**
- TASK-37: Migration 061 (`matches.data_coverage`) + era-aware `populate_matches` + parent-coverage gate in child phases + unit tests
- TASK-38: `archive_only=true` mode on 4 nrl.com routes (draw, match-centre, ladder, stats) + unit tests
- TASK-39: `archive_only=true` mode on supercoach-stats route + new `populate_player_rounds` extractor wired into `populate_db_from_s3` + unit tests
- TASK-40: `scout_backfill.py` — `--archive-only` + `--resume` + key-derivation table + unit tests
- TASK-41: Operator backfill — `nrlcom-draw` 1908–2026 on prod box via loopback
- TASK-42: Operator backfill — `nrlcom-match-centre` 1990–2026 on prod box via loopback
- TASK-43: Operator backfill — short bundle: `nrlcom-ladder` 1996–2026 + `nrlcom-stats` 2013–2026 + SC siblings (`supercoach-roster/teams/settings`) 2024–2025
- TASK-44: Operator backfill — `supercoach-stats` 2018–2025 on prod box via loopback
- TASK-45: Extractor sweep across full backfilled S3 + DB conformance verification + spot-checks
- TASK-46: Phase 5 closure — docs sweep (roadmap, charter, 5 READMEs, lineage, populate README) + run report status flip to 🟢 Shipped





## Completed work

Completed plans are **not** archived in this file. When a plan's tasks are all done, its durable record is a run report under [`docs/build/runs/`](./runs/) (see the [index](./runs/README.md)) and the plan is removed from "Active plan" above. This document holds only active/future plans; the run reports are the system of record for what shipped.
