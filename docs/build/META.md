# Jaromelu Build META

Non-negotiable process rules and project invariants for the implementer session. Read this at session start, every session. When you catch yourself making a mistake the rules here would have prevented, the rule wins.

When you find a mistake that isn't captured here, add it (or surface it to the human to add). Simon Last's tip #8: spend 20%+ of your time on the meta — every avoided mistake compounds across all future tasks.

---

## Process rules

### Git & commit discipline

- After every change, **commit and push to `main` immediately**. Don't batch.
- **Session-scoped staging only.** Never `git add -A` or `git add .`. Stage explicit pathspecs for files this session created or modified.
- Before committing, run `git diff --cached --stat` to verify the index. If a file you didn't touch is staged, unstage it.
- If a file you need to commit has been modified by another session (unexpected diff), **flag to the human** before staging.
- Never `--no-verify`, never skip hooks. If a hook fails, fix the cause; don't bypass.
- Never `git push --force` to `main`. Never `git reset --hard` without explicit human OK.

### Documentation discipline

Every task that changes code MUST update the affected docs in the same changeset:
- `README.md` if entry points change
- `docs/` pages for affected subsystems
- Inline docstrings for public functions
- `CLAUDE.md` only for new invariants (rare)

If a plan doesn't list which docs change, treat that as a planner bug and add a Concern in proof notes.

### Background execution

Background execution is **pre-approved by default** for any task that is already in `TASKS.md` and matches its `What` block. This overrides the global "ask before backgrounding" rule for this repository and this session only.

Ad-hoc background commands outside the queue still require human approval.

### Failure handling

- Stuck 3+ iterations on the same error → STOP. Add a `[BLOCKED: reason]` tag to the task and pick the next unblocked one. Don't grind.
- If a task is ambiguous, don't improvise the spec. Tag `[BLOCKED: spec unclear — <question>]`.
- Don't fix tangential bugs you spot during a task. Add a new task for them (or hand to `issue-triager`).

### Status updates

During long-running work (builds, deploys, polls), report only on **phase transitions** or errors. Don't echo routine progress lines.

### Run reports — the durable record (completion condition)

`PLAN.md` and `TASKS.md` are **working documents that get reused** — they hold only active/future plans and the live queue, never the history. The durable account of completed work lives in **`docs/build/runs/`**, one report per plan/initiative (`YYYY-MM-DD-<slug>.md`), written as a status update to the human: what **each task** delivered (not just a count), how it was verified, decisions/deviations, what's outstanding, and lessons learned. Git history is the immutable log; the run report is the readable one.

**Producing the run report is a completion condition for every run** — a plan is not "done" until its report exists and reflects every task.

Ritual:
1. When a plan's first task is checked off, create its report under `docs/build/runs/` and add a row to `docs/build/runs/README.md` (newest first).
2. As each task passes review and is checked off, record what it delivered (files, proof, commit SHA) in the report — then **remove the task from `TASKS.md`**. TASKS.md keeps no completed-task graveyard.
3. When all the plan's tasks are done, set the report status to Shipped (note any deferred verification), and **remove the plan from `PLAN.md`'s "Active plan"**.
4. Promote any reusable lessons to the invariants / "Known bugs and pitfalls" sections below.

---

## Project invariants

### Database migrations

Always apply migrations via `make migrate`. Never hand-apply SQL with `psql` shortcuts — tracking goes stale and creates hidden drift. Tests run against migrated schemas, not snapshots.

**Running migrations on prod manually.** `deploy.yml` documents `ssh jeromelu-prod 'cd /opt/jeromelu && bash packages/db/migrate.sh'`, but run bare it defaults to `localhost:5440` (dev) and fails `connection refused`. The box's `.env` has no `DATABASE_URL` (it's set in `docker-compose.prod.yml` to the container host `postgres:5432`, unreachable from the host shell). Postgres is published to host loopback at `127.0.0.1:5432`. So the working invocation is:
`ssh jeromelu-prod 'cd /opt/jeromelu && set -a && . ./.env && set +a && DATABASE_URL="postgresql://jeromelu_admin:${POSTGRES_PASSWORD}@127.0.0.1:5432/jeromelu" bash packages/db/migrate.sh'`. Read-only checks against prod can also use `docker exec jeromelu-postgres psql -U jeromelu_admin -d jeromelu`. `VACUUM (FULL)` is maintenance, not a migration — run it via `docker exec` per `docs/operations/metrics-dedup-runbook.md`, not `migrate.sh`.

### Infrastructure (AWS)

New AWS resources go through Terraform in `infra/terraform/`. Never `aws` CLI to provision as a shortcut. The agent writes the Terraform; the human runs `apply`.

### Heavy ML deps stay isolated

`pyannote`, `torch`, GPU-bound code stays in `services/gpu` or workers, behind RPC. The API container stays lean — lazy imports don't fix image bloat because pip runs at build time. Split helpers into `*_helpers.py` so CI and unit tests run without the GPU stack.

### Scout scrapers need endpoint-drift tests

Every scraper module ships with a fixture-backed test that fails on upstream schema change. **The agent does not auto-adapt** to schema drift — the human decides the fix. Tests catch drift; humans respond.

### Naming conventions

- Agent-scoped working tables use `<agent>_<thing>` (e.g. `scout_candidates`, not `discovered_sources`).
- Voice cluster labels live in `source_speakers.cluster_label`; reads coalesce `cluster_label, speaker_label`.

### Agent audit pattern

Every Claude-Agent-SDK agent uses `jeromelu_shared.agent_audit` for run id, bounds, cost, and the 3-layer audit trail. New agents must wire this in.

### V1 scope is NRL commentary, not SuperCoach gameplay

SuperCoach gameplay decisions are V2. V1 builds NRL views from YouTube transcripts and structured data. Don't drift scope without explicit human sign-off.

### Lineup moves external

Speaker ID (voice + face + fusion) is being moved out of this repo. End state: an API call returns a speaker-attributed transcript. Don't invest in in-repo Lineup paths.

### Temporal not in production

Lightsail `micro_3_2` runs api/web/postgres/caddy only. New prod workers use simpler patterns (cron + container, not Temporal).

### `data/sources.yaml` is interim

DB is system of record. The yaml is local-dev seed only — don't write features that read from it in prod.

---

## Known bugs and pitfalls

### `populate_db_from_s3 --dry-run` — FIXED 2026-05-24 (Phase 3.5 / TASK-18)

Previously broken: every phase committed internally before the outer rollback ran, so the flag silently wrote. Fixed by threading `commit: bool = True` through every phase function (the final commit AND the per-50-archive checkpoint commits are now `if commit: db.commit()`); the orchestrator passes `commit=not args.dry_run` and rolls back at the end. `--dry-run` now computes counts and writes nothing. A signature test (`tests/unit/scripts/data/populate/test_dry_run_flag.py`) guards against the `commit` param regressing.

### Video worker section-seek + JPEG-YUV

`yt-dlp` section files rebase to `start_time=0`. `ffmpeg` JPEG needs `-pix_fmt yuvj420p` (not `yuv420p`).

### Pyannote bulk enrollment

For >10 spans against one source, pre-convert m4a → WAV once instead of ffmpeg-cropping per span.

### SQLAlchemy streamed-loop commits

When helpers internally commit inside a streaming loop, commit per iteration so dirty attribute changes don't get dropped.

### Transitive untracked imports

If a file you edit imports from an `??` untracked file, your local build passes but CI fails at module resolution. Flag at commit time.

### Worker local dev

`video-worker` published `8001:8000`, `~/.aws` mounted, `S3_AUDIO_BUCKET=jeromelu-raw-audio` (the pre-2026-05-10 bug).

### On-box admin API calls need `--resolve`

The Lightsail box cannot hairpin-NAT to its own public IP — a `curl` to `https://api.jeromelu.ai` *from the box itself* just times out. Admin endpoints invoked on the box (one-time seeds, manual refreshes) must route to loopback: `curl --resolve api.jeromelu.ai:443:127.0.0.1 ...` (the same trick `scripts/scout-refresh.sh` already uses). Calls from outside (local machine, CI) hit the public IP normally.

### Prod secrets come from the box, not SSM

The human IAM user (`kristopher.lopez`) has `ssm:DescribeParameters` but **not** `ssm:GetParameter` on `/jeromelu/*` — `aws ssm get-parameter` returns `ParameterNotFound` (not `AccessDenied`). Only the instance role reads the SecureStrings. To get a prod secret (e.g. `ADMIN_KEY`), SSH the box — `aws lightsail get-instance-access-details --instance-name jeromelu --region ap-southeast-2` for temp creds — and read `/opt/jeromelu/.env`. Don't burn a cycle on SSM.

---

## Environment

- **OS**: Windows 11; default shell PowerShell. Use PowerShell syntax for new commands.
- **Python venvs**: Git Bash uses `.venv/Scripts/activate` (not `.venv/bin/activate`).
- **API**: FastAPI + uvicorn on port 8000, venv at `services/api/.venv`.
- **Infra**: Docker Compose at `docker/docker-compose.yml`.
- **Make targets**: `up`, `down`, `api`, `web`, `db-shell`, `logs`, `clean`, `migrate`, `test`, `test-eval`.
- **`make migrate` on Windows**: requires `psql` on PATH. PostgreSQL 17/18 installers put it at `C:\Program Files\PostgreSQL\<ver>\bin\psql.exe` but Git Bash doesn't pick it up automatically. Workaround: `PATH="/c/Program Files/PostgreSQL/17/bin:$PATH" bash packages/db/migrate.sh`. Don't fall back to `docker exec psql` — that bypasses `schema_migrations` tracking and creates drift (META invariant).

---

## Open questions

_(implementer adds questions here when stuck; human resolves and migrates them into rules above)_

---

## Source

Project invariants distilled from `~/.claude/projects/C--Users-krist-ClaudeProjects-Jeromelu/memory/` (feedback_*.md, project_*.md). When in doubt, check the source memories — they include "Why" and "How to apply" context. This file is the authoritative copy for the implementer session.
