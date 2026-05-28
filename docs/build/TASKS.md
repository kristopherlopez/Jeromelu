# Jaromelu Task Queue

Persistent queue for the long-lived implementer session. The implementer reads top-down, completes one task at a time, dispatches `adversarial-reviewer` against the diff + task + plan, and only checks off after the review passes.

## Format

Each task is a level-3 heading with three labelled blocks:

- **What** — exactly what to do. References a section of `PLAN.md`.
- **How to verify** — concrete checks. Commands, files, expected output. Bar: "if satisfied exactly as written, the result is trustworthy."
- **Proof notes** — an optional in-flight scratchpad only. The **authoritative** proof record is the task's entry in the active run report under [`docs/build/runs/`](./runs/), written **at checkoff (after the review passes)**.

**Proof timing (important for reviewers):** under the run-report ritual, proof is recorded into the run report *at checkoff*, which is downstream of the review. So an **empty Proof-notes block at review time is expected and is NOT a blocker** — the reviewer verifies the diff against the spec and runs the **How to verify** checks itself; proof recording is a post-pass step.

Mark as `[x]` only after `adversarial-reviewer` passes. Once it passes, record what the task delivered in the active run report under [`docs/build/runs/`](./runs/) and **remove it from this file** — TASKS.md holds only the live queue, not a completed-task graveyard (see the run-report ritual in [META.md](./META.md)).

### Tags

Prefix the title with optional tags in square brackets:

- `[P0]`, `[P1]`, `[P2]`, `[P3]` — severity (from `issue-triager`)
- `[BLOCKED: reason]` — implementer hit a wall; needs human input

---

## Open tasks

### TASK-48: [BLOCKED: eslint-violation-volume — 50 files, 34 errors + 24 warnings] ESLint CI job + `lint-web` Make target

**BLOCKED 2026-05-28 by implementer.** Baseline `npm run lint` on master HEAD surfaces 58 problems (34 errors, 24 warnings) across 50 files — over the spec's 20-file BLOCKED threshold. Surfacing per the spec's "STOP and tag `[BLOCKED]`" instruction.

**Audit (eslint via `services/web/eslint.config.mjs` → `eslint-config-next/core-web-vitals` + `eslint-config-next/typescript`):**
| Rule | Count | Severity |
|---|---|---|
| `react/no-unescaped-entities` | 13 | error — JSX with literal `'`/`"`/`&`/`<` etc. |
| `@next/next/no-img-element` | 13 | warning — `<img>` should be Next.js `<Image>` |
| `react-hooks/refs` | 12 | error — modern React rules around refs |
| `@typescript-eslint/no-unused-vars` | 8 | warning |
| `react-hooks/set-state-in-effect` | 6 | error — `setState` inside `useEffect` |
| `react-hooks/immutability` | 3 | error |
| `react-hooks/exhaustive-deps` | 2 | warning |
| `react-hooks/incompatible-library` | 1 | error |

Codebase pre-dates these rules being enforced — `npm run lint` has never run in CI, and `eslint-config-next/core-web-vitals` ships with stricter `react-hooks/*` rules than the codebase was written against.

**Remediation menu (human decision required):**
1. **Tune the config to match what the codebase ships today** — recommended path:
   - Downgrade `react-hooks/set-state-in-effect`, `react-hooks/refs`, `react-hooks/immutability`, `react-hooks/incompatible-library` from `error` → `warn` in `services/web/eslint.config.mjs`. These are advisory rules from React 19's stricter hook compiler; the codebase needs an incremental migration, not a hard gate.
   - Keep `react/no-unescaped-entities` as error and fix the 13 occurrences manually — it's a 30-min mechanical fix (single-quote → `&#39;` etc.).
   - Add CI with `--max-warnings=0` once the 13 errors are fixed; warnings become informational.
   - Net work: ~1h. Preserves the load-bearing "hard-fail in CI" property for new error-severity findings.
2. **Fix all 50 files** — keep config as-is, refactor every `<img>` → `<Image>`, every `setState`-in-effect, every ref-handling pattern. ~6–10h of careful React work + risk of behaviour regressions in the wiki/scout UI that none of the unit tests cover.
3. **Ship `npm run lint || true`** — overrides the plan's "hard-fail day 1" pre-confirmed pick. Lowest friction; violates the plan's load-bearing constraint.

**Recommended:** option 1. The `react-hooks/*` advisory rules pre-suppose a React 19 strict-mode codebase posture that Jaromelu hasn't adopted yet. Downgrading them to `warn` is the standard incremental-migration pattern. Fixing the 13 `react/no-unescaped-entities` errors is mechanical and bounded.

**To unblock:** human picks an option (or proposes a variant) and updates this task's What block. Implementer can then proceed.

**What.** Per [PLAN.md "Engineering quality hardening — Tier 1"](./PLAN.md#2026-05-28-engineering-quality-hardening--tier-1-ruff--pyright--eslint--gitleaks--deploy-gating) Interface §. ESLint is already configured (`services/web/eslint.config.mjs`) and `npm run lint` works — this task wires it into CI and adds the Make target.

**What.** Per [PLAN.md "Engineering quality hardening — Tier 1"](./PLAN.md#2026-05-28-engineering-quality-hardening--tier-1-ruff--pyright--eslint--gitleaks--deploy-gating) Interface §. ESLint is already configured (`services/web/eslint.config.mjs`) and `npm run lint` works — this task wires it into CI and adds the Make target.

Concrete changes:
1. **Run `cd services/web && npm run lint` locally on master first** to baseline. If it fails on master HEAD, fix the violations as part of this task (small repo; expected to be a handful at most). If the violation count is >20 files, STOP and tag `[BLOCKED: eslint-violation-volume — N files affected]` and surface to the human (could indicate eslint config drift since CI never ran it).
2. **Add `web-lint` job to `.github/workflows/tests.yml`** alongside the existing `web-typecheck`:
   ```yaml
     web-lint:
       name: npm run lint (services/web)
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v6
         - uses: actions/setup-node@v6
           with:
             node-version: "20"
             cache: npm
             cache-dependency-path: services/web/package-lock.json
         - name: Install deps
           run: npm ci
           working-directory: services/web
         - name: Lint
           run: npm run lint
           working-directory: services/web
   ```
3. **Update `Makefile`**: add the `lint-web` target per PLAN.md "Interface §". Update the umbrella `lint` target added in TASK-47 to also `$(MAKE) lint-web`. Update `.PHONY:` to include `lint-web`.

**How to verify.**
- `make lint-web` exits 0 locally on master.
- The PR opened with this task FAILs CI when an unused import is added to `services/web/src/app/page.tsx` (or any `.tsx` file), and PASSES CI on the revert. Capture the failing run URL + the passing run URL.
- `git diff --stat` is bounded to `.github/workflows/tests.yml`, `Makefile`, and (at most) any files touched to clear initial ESLint violations.
- The Actions UI shows a `npm run lint (services/web)` job in green on the merge commit.

**Proof notes.**

---

### TASK-51: Deploy gating — flip `deploy.yml` to `workflow_run` trigger; verify gate end-to-end

**What.** Per [PLAN.md "Engineering quality hardening — Tier 1"](./PLAN.md#2026-05-28-engineering-quality-hardening--tier-1-ruff--pyright--eslint--gitleaks--deploy-gating) Interface §. After TASK-47–50 are merged and the new CI jobs are observably green on master, gate `deploy.yml` on `tests.yml` success via the `workflow_run` trigger. Verify the gate works in production.

**Prerequisite:** TASK-47, TASK-48, TASK-49, TASK-50 are checked off AND have produced at least one green `tests.yml` run on master HEAD. **If any of those CI jobs is currently failing intermittently on master, do NOT proceed — surface to the human first.** Confirm via the Actions UI before starting.

Concrete changes:
1. **Modify `.github/workflows/deploy.yml`:**
   - Replace the `on:` block:
     ```yaml
     on:
       workflow_run:
         workflows: [Tests]
         types: [completed]
         branches: [master]
       workflow_dispatch:
     ```
   - Add the conditional guard to `detect-changes` (the upstream job everything else `needs:`):
     ```yaml
       detect-changes:
         runs-on: ubuntu-latest
         if: >-
           github.event_name == 'workflow_dispatch' ||
           github.event.workflow_run.conclusion == 'success'
         ...
     ```
   - Replace every occurrence of `${{ github.sha }}` inside the workflow with `${{ github.event.workflow_run.head_sha || github.sha }}`. (`workflow_run` triggers run in default-branch context; `github.sha` defaults to the branch HEAD, which can drift from the SHA that tests.yml actually validated. The fallback handles `workflow_dispatch`.) Spot the two locations: the matrix `docker build … -t $IMAGE:${{ github.sha }}` step and any other `github.sha` reference in the file.
2. **Update `docs/ops/ci-cd.md`:**
   - Modify the `deploy.yml` row in the trigger table from `push to master, workflow_dispatch` to `workflow_run on Tests (master), workflow_dispatch`.
   - Update the "What is NOT in this pipeline" entry for "Tests + web typecheck" — flip the negation: the gate now exists; document the `workflow_run` mechanism and how to override via `workflow_dispatch` for emergency deploys.
   - Add a new "Quality gates" subsection covering Ruff / Pyright / web-lint / Gitleaks — what each catches, how to silence a false positive.
3. **Dry-run verification ON MASTER** (operator step, run after the PR is merged):
   - **3a. Red-Tests → no-deploy.** Push a commit to master that intentionally breaks Ruff (or any other CI gate — Pyright is convenient). Wait for `Tests` workflow to finish red. Confirm via Actions UI that `Build & Deploy` did NOT start. Revert the breaking change with a follow-up commit; wait for `Tests` green; confirm `Build & Deploy` then runs.
   - **3b. SHA-tag fidelity.** On the green deploy following the revert, open the `build-and-push` job log. Confirm the `docker build … -t $IMAGE:<sha>` line uses the master HEAD SHA (which under `workflow_run` context comes from `github.event.workflow_run.head_sha`). Cross-reference: `git log --oneline -1` on master after the revert merge.
   - **3c. `workflow_dispatch` override.** From the Actions UI, manually dispatch `Build & Deploy`. Confirm it runs to completion regardless of Tests state. Confirm the image tag in the build log uses `github.sha` (the dispatch-time fallback).

**How to verify.**
- `grep -A 6 "^on:" .github/workflows/deploy.yml` shows the `workflow_run` block + `workflow_dispatch`.
- `grep "github.sha" .github/workflows/deploy.yml` returns only lines of the form `github.event.workflow_run.head_sha || github.sha`.
- `grep "github.event.workflow_run.conclusion" .github/workflows/deploy.yml` returns ≥1 line (the conditional guard).
- `docs/ops/ci-cd.md` deploy.yml table row updated; new "Quality gates" subsection present.
- Dry-run 3a observation: Actions UI shows the red Tests run with NO downstream Build & Deploy run on its commit. Capture screenshots / URLs into the run-report scratchpad. Then green run on the revert DID trigger Build & Deploy.
- Dry-run 3b observation: SHA in `docker build … -t $IMAGE:<sha>` matches `git rev-parse HEAD` on master at the time of that deploy. Record both into the run-report scratchpad.
- Dry-run 3c observation: `workflow_dispatch` produced a successful Build & Deploy regardless of Tests state. Record the Actions URL.

**Proof notes.**

---

### TASK-52: Closure — engineering-quality-hardening.md Tier 1 ✅; run report → 🟢 Shipped

**What.** Per [PLAN.md "Engineering quality hardening — Tier 1"](./PLAN.md#2026-05-28-engineering-quality-hardening--tier-1-ruff--pyright--eslint--gitleaks--deploy-gating) Documentation updates §. Close the plan: flip Tier 1 items 1–6 to ✅ Shipped; finalize the run report; remove the plan from PLAN.md's "Active plan".

Concrete changes:
1. **`docs/operations/engineering-quality-hardening.md`:**
   - Under each of "1. Python lint and format", "2. Python type checking", "3. Frontend lint in CI", "4. Datetime and timezone invariant", "5. Secret hygiene", "6. Gate deploy on quality checks", add a final paragraph:
     > **Status:** ✅ Shipped 2026-05-28 — see [run report](../build/runs/2026-05-28-eng-quality-tier-1.md).
   - Update "Current Baseline" section to reflect the new state — bullets for: Ruff configured + CI; Pyright configured (narrow: packages/shared/jeromelu_shared); web lint in CI; Gitleaks in CI; deploy gated on tests.yml via workflow_run.
   - "Suggested Implementation Order" section: keep the list — items 1–6 are historical; items 7+ remain as the next-up backlog. Add a one-line header note: "_Items 1–6 shipped 2026-05-28 (see [run report])."
2. **`docs/build/runs/2026-05-28-eng-quality-tier-1.md`** (created at TASK-47 checkoff per META ritual; finalized here):
   - Status: `🟢 Shipped`.
   - Per-task entries (TASK-47 through TASK-52) with: files touched, proof URLs (captured from each task's "How to verify" steps), commit SHA.
   - "Decisions & deviations" section: any choices that deviated from the plan (e.g. allowlist entries that had to be added to `.gitleaks.toml`, pyright ignores that landed in scope, ruff version pin chosen).
   - "Outstanding deferred items": Tier 2 / Tier 3 items from the backlog that this plan did NOT address (list 7–17).
   - "Lessons learned": surface any process learnings — promote to META.md "Known bugs and pitfalls" if they're durable.
   - "Commits" list (oneline format from `git log`).
3. **`docs/build/runs/README.md`:**
   - Add a new top row (newest first) for this run.
4. **`docs/build/PLAN.md`:**
   - Remove the entire `### 2026-05-28: Engineering quality hardening — Tier 1 …` section from "Active plan". Phase 5's section stays (it's still active).
5. **`docs/build/TASKS.md`:**
   - Confirm TASK-47 through TASK-52 are all already removed via their individual checkoffs. The file should not contain a graveyard of completed Tier 1 tasks.

**How to verify.**
- `git diff --stat` covers exactly: `docs/operations/engineering-quality-hardening.md`, `docs/build/runs/2026-05-28-eng-quality-tier-1.md`, `docs/build/runs/README.md`, `docs/build/PLAN.md`, `docs/build/TASKS.md`. No code files.
- `grep -c "✅ Shipped 2026-05-28" docs/operations/engineering-quality-hardening.md` returns **6** (one per Tier 1 item).
- `grep -A 1 "## Active plan" docs/build/PLAN.md` no longer shows the "Engineering quality hardening — Tier 1" heading.
- `head -5 docs/build/runs/README.md` shows the new row as the newest.
- `grep "🟢 Shipped" docs/build/runs/2026-05-28-eng-quality-tier-1.md` returns ≥1 line.
- The run report's per-task entries cite the actual commit SHAs from `git log --oneline -20` (TASK-47 through TASK-52).
- `grep "TASK-4[7-9]\|TASK-5[0-2]" docs/build/TASKS.md` returns zero matches (every Tier 1 task has been removed via its own checkoff).

**Proof notes.**

---

### TASK-41: Operator backfill — `nrlcom-draw` 1908–2026 (on prod box via loopback)

**What.** Per [PLAN.md "Scout Phase 5"](./PLAN.md#2026-05-28-scout-phase-5--historical-backfill--standard-data-model-conformance) Tasks list. **Operator task** — runs the hardened backfill driver against prod from the prod box via the Phase 4.5 loopback procedure.

Procedure (run on the Lightsail box, per the `docker cp scripts → /runtmp/scripts` precedent — note the trailing-slash gotcha lesson from Phase 4.5 lessons-learned):
1. SSH the box (`make prod-shell` or `ssh jeromelu-prod`).
2. `mkdir /runtmp` and `docker cp scripts jeromelu-api:/runtmp/` (trailing slash matters — lands `scripts/` *folder* under `/runtmp/`).
3. Read `ADMIN_KEY` from `/opt/jeromelu/.env`.
4. Inside the API container, run a `tmux` or `screen` session so the long-running backfill survives SSH disconnects:
   ```bash
   docker exec -it jeromelu-api bash -c "
     cd /runtmp && python -m scripts.data.scout_backfill \
       --source nrlcom-draw \
       --season-from 1908 --season-to 2026 \
       --round-from 1 --round-to 30 \
       --competition 111 \
       --api https://api.jeromelu.ai \
       --admin-key \$ADMIN_KEY \
       --archive-only --resume \
       --rate-limit 1.0 2>&1 | tee /runtmp/backfill_nrlcom-draw_$(date +%Y%m%d_%H%M).log
   "
   ```
   On-box `curl` must hit the loopback — the API container itself can resolve `api.jeromelu.ai` via Docker DNS to the internal nginx proxy, so the `--resolve` trick is only needed for `curl` from the host shell. **Verify before starting:** `docker exec jeromelu-api curl -s -o /dev/null -w "%{http_code}\n" https://api.jeromelu.ai/api/health` returns 200; if not, fall back to the host-shell `curl --resolve` approach and re-shape the script invocation accordingly (BLOCKED tag if the container can't reach the API).
5. Wall-clock: 1908–2026 × ~26 rounds at 1 req/sec ≈ 1h. Expect 502s for seasons/rounds that don't exist (early years had fewer rounds, finals structure varied) — recorded in failure log, not fatal.
6. After completion, clean up `/runtmp` on the container: `docker exec jeromelu-api rm -rf /runtmp/scripts /runtmp/backfill_*.log` (copy the log down first if useful).

**How to verify.**
- `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/draw/111/ --recursive | wc -l` ≥ **2700**.
- `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/draw/111/ --recursive | awk -F/ '{print $5}' | sort -u | wc -l` ≥ **115** (distinct season folders — 1908–2026 ≈ 119 with some empty).
- `psql` (read via `docker exec jeromelu-postgres psql -U jeromelu_admin -d jeromelu -c "..."`):
  - `SELECT COUNT(*) FROM agent_runs WHERE detail_json->>'pipeline'='nrlcom-draw' AND started_at > <backfill_start_ts> AND status='complete'` matches the driver's successes count (record both in the run report scratchpad).
  - `SELECT COUNT(*) FROM agent_runs WHERE detail_json->>'pipeline'='nrlcom-draw' AND started_at > <backfill_start_ts> AND status='failed'` matches the driver's failures count.
- Spot-check S3: `aws s3 cp s3://jeromelu-clean-documents/scout/nrlcom/draw/111/1908/round-01.json - | jq '.fixtures | length, .selectedSeasonId, .selectedRoundId'` returns plausible numbers (≥1 fixture; correct season/round).
- The driver's final summary log section records: successes count, failures count, first 20 failure lines. **Copy this verbatim into the run report scratchpad on this task's checkoff.**

**Proof notes.**

---

### TASK-42: Operator backfill — `nrlcom-match-centre` 1990–2026 (on prod box via loopback)

**What.** Per [PLAN.md "Scout Phase 5"](./PLAN.md#2026-05-28-scout-phase-5--historical-backfill--standard-data-model-conformance) Tasks list. **Operator task** — same procedure as TASK-41.

Key differences from TASK-41:
- **Wall-clock**: ~5500 GETs at 1 req/sec ≈ **3–4h**. Use `tmux`/`screen` mandatory.
- **Seasons**: 1990–2026 (pre-1990 has no match-centre URL in the draw fixtures per D12; the walker auto-skips fixtures missing `matchCentreUrl`).
- **Round depth**: `--round-from 1 --round-to 30` (the walker discovers fixtures from the draw; per-round wall-clock varies).
- **Resume granularity**: round-level (per the TASK-40 design — list `scout/nrlcom/match-centre/{comp}/{season}/round-{NN}/` prefix; skip if any keys exist).

Run command (replace the source param in TASK-41's invocation):
```bash
docker exec -it jeromelu-api bash -c "
  cd /runtmp && python -m scripts.data.scout_backfill \
    --source nrlcom-match-centre \
    --season-from 1990 --season-to 2026 \
    --round-from 1 --round-to 30 \
    --competition 111 \
    --api https://api.jeromelu.ai \
    --admin-key \$ADMIN_KEY \
    --archive-only --resume \
    --rate-limit 1.0 2>&1 | tee /runtmp/backfill_nrlcom-match-centre_$(date +%Y%m%d_%H%M).log
"
```

**How to verify.**
- `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/match-centre/111/ --recursive | wc -l` ≥ **4500** (post-2000 has ~200 matches/year × 26 years; pre-2000 mostly empty payloads).
- `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/match-centre/111/ --recursive | awk -F/ '{print $5}' | sort -u | wc -l` ≥ **30** (distinct season folders).
- Pre-2000 spot-check: `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/match-centre/111/1995/ --recursive` returns either a small set of keys (pre-2000 has thin payloads, mostly timeline) OR zero (if 1995 draws had no `matchCentreUrl`). Both acceptable; record actual count.
- Post-2000 spot-check: `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/match-centre/111/2010/ --recursive | wc -l` ≥ 180.
- One specific S3 inspect: `aws s3 cp $(aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/match-centre/111/2010/ --recursive | head -1 | awk '{print "s3://jeromelu-clean-documents/" $4}') - | jq 'keys | length'` returns a reasonable key count (≥4 — `players`/`stats`/`timeline`/`match` for full-shape post-2010).
- Driver final summary (successes / failures / first 20 failure lines) recorded in run report scratchpad.

**Proof notes.**

---

### TASK-43: Operator backfill — short bundle (ladder 1996–2026, stats 2013–2026, SC siblings 2024–2025)

**What.** Per [PLAN.md "Scout Phase 5"](./PLAN.md#2026-05-28-scout-phase-5--historical-backfill--standard-data-model-conformance) Tasks list. **Operator task** — three small backfills bundled because each is fast (under 15 min combined) and the verification cadence is identical.

Three sequential invocations on the prod box (no tmux needed; total wall-clock <20 min):

```bash
# 1. nrl.com ladder — 30 seasons × ~24 rounds avg = ~720 GETs at 1 req/sec ≈ 12 min
docker exec -it jeromelu-api bash -c "
  cd /runtmp && python -m scripts.data.scout_backfill \
    --source nrlcom-ladder --season-from 1996 --season-to 2026 \
    --round-from 1 --round-to 30 --competition 111 \
    --api https://api.jeromelu.ai --admin-key \$ADMIN_KEY \
    --archive-only --resume --rate-limit 1.0 2>&1 | tee /runtmp/backfill_nrlcom-ladder_$(date +%Y%m%d_%H%M).log
"

# 2. nrl.com stats — 14 seasons × 1 endpoint = 14 GETs ≈ 30 sec
docker exec -it jeromelu-api bash -c "
  cd /runtmp && python -m scripts.data.scout_backfill \
    --source nrlcom-stats --season-from 2013 --season-to 2026 \
    --competition 111 \
    --api https://api.jeromelu.ai --admin-key \$ADMIN_KEY \
    --archive-only --resume --rate-limit 1.0 2>&1 | tee /runtmp/backfill_nrlcom-stats_$(date +%Y%m%d_%H%M).log
"

# 3. SC siblings — supercoach-roster + supercoach-teams + supercoach-settings for 2024 and 2025
for src in supercoach-roster supercoach-teams supercoach-settings; do
  docker exec -it jeromelu-api bash -c "
    cd /runtmp && python -m scripts.data.scout_backfill \
      --source $src --season-from 2024 --season-to 2025 \
      --api https://api.jeromelu.ai --admin-key \$ADMIN_KEY \
      --rate-limit 1.0 2>&1 | tee /runtmp/backfill_${src}_$(date +%Y%m%d_%H%M).log
  "
done
```

(SC siblings run WITHOUT `--archive-only` because the 2-season window is modern-shape per D12; `--resume` is a no-op for them per the TASK-40 design.)

**How to verify.**
- `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/ladder/111/ --recursive | wc -l` ≥ **600**.
- `aws s3 ls s3://jeromelu-clean-documents/scout/nrlcom/stats/111/ --recursive | wc -l` = **14** (2013–2026 inclusive).
- `aws s3 ls s3://jeromelu-clean-documents/scout/supercoach/classic/players-cf/ --recursive | wc -l` ≥ **2** (2024 + 2025; daily timestamps may produce more if existing 2025 data was already there).
- `aws s3 ls s3://jeromelu-clean-documents/scout/supercoach/classic/teams/ --recursive | wc -l` ≥ **2** (2024 + 2025 — the existing seed was 2026 only).
- `aws s3 ls s3://jeromelu-clean-documents/scout/supercoach/classic/settings/ --recursive | wc -l` ≥ **2**.
- Each driver invocation reports successes / failures in its final summary — record in run report scratchpad.
- SC siblings: backfilling DOES write to DB (no archive_only flag) — verify `SELECT COUNT(*) FROM sc_settings WHERE season IN (2024, 2025)` ≥ 2 (one per mode × season at minimum).

**Proof notes.**

---

### TASK-44: Operator backfill — `supercoach-stats` 2018–2025 (on prod box via loopback)

**What.** Per [PLAN.md "Scout Phase 5"](./PLAN.md#2026-05-28-scout-phase-5--historical-backfill--standard-data-model-conformance) Tasks list. **Operator task** — same procedure as TASK-41/42.

- **Source**: `supercoach-stats` (the nrlsupercoachstats.com jqGrid endpoint).
- **Seasons**: 2018–2025 (per D12; 2026 already current via cron).
- **Round depth**: `--round-from 0 --round-to 30` (round 0 = Totals per the route docstring; rounds 1–30 = regular rounds; many old years had fewer than 30 rounds → 502s recorded as failures).
- **Wall-clock**: ~250 jqGrid sessions at 1 req/sec ≈ 1–2h (each session is ~3 pages internally to the fetcher).
- **`--archive-only` is mandatory** here because the route writes inline to `player_rounds` — without the flag, every (season, round) would trigger an UPSERT, and 2018 shape may not strict-parse cleanly. TASK-45 runs the new `populate_player_rounds` extractor to write DB rows from S3 after backfill.

```bash
docker exec -it jeromelu-api bash -c "
  cd /runtmp && python -m scripts.data.scout_backfill \
    --source supercoach-stats \
    --season-from 2018 --season-to 2025 \
    --round-from 0 --round-to 30 \
    --api https://api.jeromelu.ai --admin-key \$ADMIN_KEY \
    --archive-only --resume \
    --rate-limit 1.0 2>&1 | tee /runtmp/backfill_supercoach-stats_$(date +%Y%m%d_%H%M).log
"
```

**How to verify.**
- `aws s3 ls s3://jeromelu-clean-documents/scout/nrlsupercoachstats/stats/ --recursive | wc -l` ≥ **200** (~8 seasons × ~28 rounds incl. Totals; actual round counts vary by year). Note the `scout/` prefix — every Scout archive is under that prefix per `archive_response()` (corrected from the original planner-sketch which omitted it).
- `aws s3 ls s3://jeromelu-clean-documents/scout/nrlsupercoachstats/stats/ --recursive | awk -F/ '{print $4}' | sort -u | wc -l` ≥ **8** (distinct season folders 2018–2025; field 4 now because the `scout/` prefix consumes field 1).
- Spot-check 2018: `aws s3 cp s3://jeromelu-clean-documents/scout/nrlsupercoachstats/stats/2018/round-01.json - | jq '.rows | length'` ≥ 200 (canonical SC roster size).
- Driver summary recorded in run report scratchpad.
- **DB verification deferred to TASK-45** — this task only proves S3 capture.

**Proof notes.**

---

### TASK-45: Extractor sweep + DB conformance verification across full backfilled S3

**What.** Per [PLAN.md "Scout Phase 5"](./PLAN.md#2026-05-28-scout-phase-5--historical-backfill--standard-data-model-conformance) Tasks list + Verification §end-to-end. **Operator task** — run the (now era-aware) DB extractors across the full backfilled S3, then verify the canonical schema is populated end-to-end.

Steps (run on prod box, in the API container, same `docker cp scripts → /runtmp` pattern):

1. **Pre-flight**: confirm the prod API container has the TASK-37/38/39 code baked in:
   ```bash
   docker exec jeromelu-api python -c "from scripts.data.populate.phase_player_rounds import populate_player_rounds; print('ok')"
   docker exec jeromelu-api python -c "from scripts.data.populate.phase_matches import _extract_from_draw_fixture; print('ok')"
   ```
   Both must print `ok`. If not, deployment hasn't caught up — STOP and BLOCKED until [deploy pipeline path-filter](../../../../C:/Users/krist/.claude/projects/C--Users-krist-ClaudeProjects-Jeromelu/memory/project_deploy_pipeline_path_filter.md) resolves (push a forced-deploy trigger commit).

2. **Run each phase** with explicit wide season range:
   ```bash
   SEASONS=$(seq 1908 2026 | tr '\n' ' ')
   docker exec jeromelu-api python -m scripts.data.populate_db_from_s3 \
     --phase matches --seasons $SEASONS --competition 111 2>&1 | tee /runtmp/populate_matches.log

   docker exec jeromelu-api python -m scripts.data.populate_db_from_s3 \
     --phase team_lists --seasons $SEASONS --competition 111 2>&1 | tee /runtmp/populate_team_lists.log

   docker exec jeromelu-api python -m scripts.data.populate_db_from_s3 \
     --phase stats --seasons $SEASONS --competition 111 2>&1 | tee /runtmp/populate_stats.log

   docker exec jeromelu-api python -m scripts.data.populate_db_from_s3 \
     --phase timeline --seasons $SEASONS --competition 111 2>&1 | tee /runtmp/populate_timeline.log

   docker exec jeromelu-api python -m scripts.data.populate_db_from_s3 \
     --phase standings --competition 111 2>&1 | tee /runtmp/populate_standings.log

   docker exec jeromelu-api python -m scripts.data.populate_db_from_s3 \
     --phase leaderboards --competition 111 2>&1 | tee /runtmp/populate_leaderboards.log

   docker exec jeromelu-api python -m scripts.data.populate_db_from_s3 \
     --phase player_rounds --seasons $SEASONS --competition 111 2>&1 | tee /runtmp/populate_player_rounds.log
   ```

3. **Capture row counts + era distribution** via `psql`:
   ```sql
   SELECT data_coverage, COUNT(*) FROM matches WHERE competition_id=111 GROUP BY 1 ORDER BY 1;
   SELECT COUNT(*) FROM match_team_lists WHERE match_id IN (SELECT id FROM matches WHERE competition_id=111);
   SELECT COUNT(*) FROM player_match_stats WHERE match_id IN (SELECT id FROM matches WHERE competition_id=111);
   SELECT COUNT(*) FROM match_timeline WHERE match_id IN (SELECT id FROM matches WHERE competition_id=111);
   SELECT COUNT(*) FROM stat_leaderboards WHERE competition_id=111;
   SELECT COUNT(*) FROM team_standings WHERE competition_id=111;
   SELECT COUNT(*) FROM player_rounds WHERE season >= 2018;
   ```

4. **Spot-check queries** (each must return non-empty unless marked):
   - `SELECT season, round, status, data_coverage FROM matches WHERE season=1908 AND round=1 LIMIT 5` — non-empty, all `data_coverage='fixture_only'`.
   - `SELECT m.id, COUNT(t.*) AS tl_rows FROM matches m LEFT JOIN match_timeline t ON t.match_id=m.id WHERE m.season BETWEEN 1990 AND 1999 GROUP BY m.id ORDER BY tl_rows DESC LIMIT 5` — at least some matches with timeline rows + `data_coverage='timeline_only'`.
   - `SELECT COUNT(*) FROM player_match_stats WHERE match_id IN (SELECT id FROM matches WHERE season < 2000)` — **MUST be 0** (parent-coverage gate test).
   - `SELECT data_coverage FROM matches WHERE season=2026 ORDER BY id DESC LIMIT 5` — all `'full'` (regression check).
   - `SELECT season, COUNT(*) FROM player_rounds GROUP BY season ORDER BY season` — non-empty for 2018–2026.

5. **Idempotency check**: re-run one phase a second time — log shows `inserted=0` and `updated=N` matching the first run's total.

**How to verify.**
- Each phase log exits 0 with a summary report at the bottom (`done. summary: {...}`).
- Row counts meet PLAN.md's thresholds: `matches.full ≥4500`, `matches.timeline_only ≥800`, `matches.fixture_only ≥2000`; `stat_leaderboards ≥4500`; `team_standings ≥600`; `player_rounds (2018+) ≥150000`.
- All 5 spot-check queries return as specified (including the one that MUST return 0).
- Re-run shows `inserted=0`.
- All counts + spot-check outputs copied verbatim into the run report scratchpad on this task's checkoff.

**Proof notes.**

---

### TASK-46: Phase 5 closure — docs sweep + run report → Shipped

**What.** Per [PLAN.md "Scout Phase 5"](./PLAN.md#2026-05-28-scout-phase-5--historical-backfill--standard-data-model-conformance) Documentation updates §.

Files to update:

1. `docs/agents/crew/scout/roadmap.md`:
   - Phase 5 heading: `### Phase 5 — Historical backfill (one-time, ~5-6 hours operationally) ✅ Shipped (YYYY-MM-DD)`
   - Body: replace the In-design checklist with the actual row counts achieved (per TASK-45 verification), the `data_coverage` distribution table, and a "Deferred (out of scope, surfaced not self-queued)" list (e.g., casualty-ward historical — no upstream support per D12; nrl.com per-team roster historical — same).

2. `docs/agents/crew/scout/charter.md`:
   - D12 row-counts column: update to actuals.
   - Add a "Standard data model — era reconciliation" sub-section under D12 documenting the `matches.data_coverage` decision and the "NULLs + era marker, never alternate tables" principle (cite this plan).

3. `docs/operations/data-lineage/matches.md`:
   - Document the new `data_coverage` column + its CHECK constraint.
   - Era-banded row count breakdown table (one row per coverage value with count + season range).
   - 4 spot-check queries from TASK-45 listed for operator reference.

4. 5 pipeline READMEs (`services/api/app/scout/{nrlcom_draw,nrlcom_match_centre,nrlcom_ladder,nrlcom_stats,supercoach_stats}/README.md`):
   - "Archive-only mode" section: when to use (`archive_only=true` for historical backfill); the response shape (`validated:false, validation_skipped:true`); default behaviour unchanged (daily cron leaves it false).
   - For `nrlcom_match_centre/README.md` specifically: document the 1990–1999 partial-shape expectation and how it surfaces as `data_coverage='timeline_only'` in the matches table.

5. `scripts/data/populate/README.md`:
   - New row in the phase table: `player_rounds` reads `nrlsupercoachstats/stats/*`, writes `player_rounds` (UPSERT on `(player_id, round, season)`), wired via `--phase player_rounds`.

6. `docs/build/runs/2026-05-28-scout-phase-5-historical-backfill.md`:
   - Status: `🟢 Shipped`.
   - Per-task entries with what each delivered (files, proof, commit SHA).
   - Decisions & deviations.
   - Outstanding deferred items.
   - Lessons learned.
   - Commits list.

7. `docs/build/runs/README.md`:
   - Add the new row (newest first).

8. `docs/build/PLAN.md`:
   - Remove the Phase 5 plan from "Active plan" — leave the "Last shipped initiative" pointer updated to this run.

**How to verify.**
- `git diff --stat` covers the 11+ doc files listed above and NO code files.
- `grep -r "Phase 5" docs/agents/crew/scout/roadmap.md docs/agents/crew/scout/charter.md` — every reference reflects ✅ Shipped.
- `docs/build/PLAN.md` "Active plan" section is empty (or shows the next-up plan if one's been started).
- `docs/build/TASKS.md` "Open tasks" section is empty (all Phase 5 tasks removed per the META ritual).
- `docs/build/runs/README.md` top row is the Phase 5 entry.
- The run report's per-task entries match the commit SHAs in `git log --oneline -20` (TASK-37 through TASK-46).
- All TASK-37..TASK-46 entries also removed from TASKS.md (each task's checkoff already did this; verify the file ends with `## Open tasks` empty + `## Completed work` blurb only).

**Proof notes.**

---

### TASK-53: Fix `insights.py` dormant queries — `Claim.subject_entity_id` was removed in migration 036

**What.** Surfaced during TASK-49 (Pyright plumbing). `packages/shared/jeromelu_shared/insights.py` functions `query_round_claims()` (line ~88) and `query_claim_consensus()` (line ~123) reference `Claim.subject_entity_id`, which is not a column on `Claim` per `packages/shared/jeromelu_shared/db/models.py:711–733`. Per `models.py:751–771`, entity links moved to `ClaimAssociation` (polymorphic FK to person_id / team_id / etc.) in migration 036.

These functions are dormant — called only by `scripts/insights/generate_round_tips.py`. Production-side likely hasn't run them since the migration 036 schema change. They would raise `AttributeError` at runtime.

The five attribute accesses are currently suppressed with `# pyright: ignore[reportAttributeAccessIssue]` plus a NOTE comment block above `query_round_claims` pointing to this task.

**Concrete changes:**
1. Rewrite `query_round_claims()` to JOIN through `ClaimAssociation`, grouping by `(person_id, claim_type)` (or `(team_id, claim_type)` depending on what `generate_round_tips.py` expects — inspect the caller for the role values it actually uses). Output shape unchanged: `dict[str, list[dict]]` keyed by `entity_id_str`.
2. Rewrite `query_claim_consensus()` similarly. Output shape unchanged: `dict[str, dict[str, int]]`.
3. Remove the 5 `# pyright: ignore[reportAttributeAccessIssue]` markers + the NOTE block above `query_round_claims`.
4. Add a unit test under `tests/unit/shared/test_insights.py` that builds an in-memory `Claim` + `ClaimAssociation` fixture and exercises both functions — verifies the rewrite is correct.
5. Run `scripts/insights/generate_round_tips.py --round <N> --season 2026` against a dev DB to confirm runtime behaviour is intact.

**How to verify.**
- `make typecheck-python` (Pyright) exits 0 with the `# pyright: ignore` markers removed.
- New unit test `tests/unit/shared/test_insights.py::test_query_round_claims_groups_by_person_id` (and consensus equivalent) passes.
- `make test` exits 0.
- Manual run of `generate_round_tips.py` produces output of the expected shape (a SuperCoach round-tips article without error).
- `git grep -n "subject_entity_id" packages/shared/jeromelu_shared/` returns zero matches.

**Proof notes.**





## Completed work

Completed tasks are not kept here. When a task passes review and is checked off, what it delivered is recorded in the active run report under [`docs/build/runs/`](./runs/) and the task is removed from this file. This queue holds only open/in-flight work.
