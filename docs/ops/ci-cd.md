---
tags: [area/operations]
---

# CI/CD pipeline

Single source of truth for what GitHub Actions does in this repo, end to end.
Four workflows live under `.github/workflows/`:

| Workflow | Trigger | What it does |
|---|---|---|
| `deploy.yml` | **`workflow_run` on `Tests` (master, success only)**, `workflow_dispatch` | Build api/web images → push to ECR → restart compose stack on Lightsail → invalidate CloudFront. Gated on `Tests` success since TASK-51 (2026-05-28); manual dispatch bypasses the gate for emergency deploys. |
| `tests.yml` | PR / push to `master` | 6 parallel jobs: `pytest tests/unit`, `tsc --noEmit` (services/web), `npm run lint` (services/web), `ruff check + format`, `pyright` (packages/shared), `gitleaks` (working tree). All hard-fail. Gates `deploy.yml` via `workflow_run`. |
| `terraform.yml` | PR / push touching `infra/terraform/**` | `fmt -check` + `init` + `validate` + `plan`; comments the plan on PRs. **Apply stays manual.** |
| `cost-report.yml` | `schedule: cron '0 22 * * *'` (22:00 UTC daily), `workflow_dispatch` | Runs `scripts/cost_report.py`: queries Cost Explorer for MTD spend by service + projection, describes the live resources, ships an HTML email via SES from `reports@jeromelu.ai` to `kristopher.lopez@gmail.com`. |

The deploy workflow runs the actual deploy step on a **self-hosted GitHub
Actions runner installed on the Lightsail box itself** — not via SSH from a
GitHub-hosted runner. This keeps port 22 locked to the operator's IP and
removes a moving-target firewall problem.

---

## `deploy.yml` — application deploy

Pipeline stages:

1. **`detect-changes`** — `dorny/paths-filter@v3` flags whether `api`, `web`, `video_worker`, `db`, or `deploy_only` paths changed. Sets job-level outputs that gate every downstream job. `deploy_only` covers `scripts/lightsail-deploy.sh`, `scripts/cron.d/**`, `docker/docker-compose.prod.yml`, and `docker/Caddyfile` — changes that need a redeploy of the existing images but no new image build.
2. **`build-and-push`** (matrix: api, web, video-worker) — only fires for the service whose paths changed. Builds the Dockerfile and pushes two tags to ECR: `${github.sha}` and `latest`.
3. **`deploy-lightsail`** — runs on the self-hosted runner (`runs-on: [self-hosted, jeromelu-prod]`) when any of `api / web / video_worker / deploy_only` changed. `cd /opt/jeromelu`, `git pull --ff-only`, then runs `scripts/lightsail-deploy.sh`. The script logs into ECR and then rolls api → web → video-worker **one at a time** (`stop` → `pull` → `up -d --no-deps`), pruning between iterations. Serial rollout is mandatory: the box is a 2 GB `small_3_2` and parallel pulls + 2× running containers can still wedge it (memory exhaustion → swap thrash → dockerd hang → runner offline). Brief per-service downtime is the explicit trade.
4. **`invalidate-cdn`** — only on web changes. `aws cloudfront create-invalidation` against distribution `E2G6FL11A3JP8F`.
5. **`migrate`** — **notify-only.** When `db` paths change the job prints instructions to run `packages/db/migrate.sh` from the box manually. No automatic schema changes.

### Path-filter scope

```text
api: services/api/**, packages/shared/**
web: services/web/**
db:  packages/db/**
```

Anything outside those globs does not trigger CI builds or deploys.

### What is NOT in this pipeline

- **`services/gpu`** — the GPU container deploys out-of-band via `services/gpu/build_and_push.sh` + `services/gpu/deploy.py` (different runtime, different cadence — SageMaker Async on `ml.g4dn.xlarge`).
- **Database migrations** — notify-only by design. Apply on the box.

### Tests gate (TASK-51, 2026-05-28)

`deploy.yml` is now gated on `tests.yml` success via the `workflow_run` trigger. Mechanism:

- On every push to `master`, `tests.yml` runs first.
- If **any** job in `tests.yml` fails (pytest, web-typecheck, web-lint, ruff, pyright, gitleaks), `deploy.yml` does **not** start. The triggering commit ships nothing.
- If all 6 jobs pass, `deploy.yml` fires automatically. `workflow_run.head_sha` (used for image tagging) is the SHA `tests.yml` actually validated — not the current default-branch HEAD, which could drift.

**Emergency override.** `workflow_dispatch` on `deploy.yml` runs immediately regardless of `tests.yml` state. The conditional guard in `detect-changes` (`if: github.event_name == 'workflow_dispatch' || github.event.workflow_run.conclusion == 'success'`) lets the manual path through unconditionally. Use only when shipping a hotfix while CI is flaky — every other path goes through the gate.

If a new service should ride this pipeline, add a path filter to `detect-changes`, a matrix entry to `build-and-push`, and update this document.

---

## `tests.yml` — quality gates

Runs on every PR and every push to `master`. **Six parallel jobs** — each is a hard-fail gate, and the workflow's aggregate status gates `deploy.yml` via `workflow_run`.

1. **`unit`** — `pytest tests/unit` against `requirements-test.txt`. Lightweight by design: the ML stack (torch, pyannote, deepgram, insightface, opencv) is deliberately excluded. See `tests/README.md` for tier layout.
2. **`web-typecheck`** — `tsc --noEmit` on `services/web`. Runs **unconditionally** (no paths-filter), because the Docker build in `deploy.yml` IS gated by paths-filter — a broken TS import landing in a non-web commit would otherwise stay invisible until the next web-touching commit. This job surfaces the failure at the originating commit. ~1-2 min.
3. **`web-lint`** — `npm run lint` on `services/web`. Hard-fails on errors; warnings are informational. Several React 19 advisory rules (`react-hooks/refs`, `react-hooks/set-state-in-effect`, `react-hooks/immutability`, `react-hooks/incompatible-library`) are downgraded to `warn` in `services/web/eslint.config.mjs` pending incremental migration. Added by TASK-48.
4. **`ruff`** — `ruff check + format --check` over `services packages scripts tests`. Pins `ruff==0.15.14`. Config in root `pyproject.toml [tool.ruff]`. Added by TASK-47.
5. **`pyright`** — `pyright` over `packages/shared/jeromelu_shared/` (narrow include). Pins `pyright==1.1.409`. Config in `pyproject.toml [tool.pyright]`. Added by TASK-49.
6. **`gitleaks`** — `gitleaks/gitleaks-action@v2` scans the PR diff (or master HEAD) for secrets. Config in `.gitleaks.toml`. Added by TASK-50.

### Quality gates — how to silence a false positive

- **Ruff** — per-file ignore in `pyproject.toml [tool.ruff.lint.per-file-ignores]` for file-scoped issues; inline `# noqa: <RULE>  # <rationale>` for per-line. Never silence without rationale.
- **Pyright** — inline `# pyright: ignore[reportXxx]  # <rationale>` per line. Never silence without rationale; never blanket-ignore a file.
- **ESLint** — per-line `// eslint-disable-next-line <rule>  // <rationale>`, or downgrade the rule severity in `services/web/eslint.config.mjs` if the codebase needs incremental migration (see the React 19 advisory rules for the precedent).
- **Gitleaks** — `[[allowlists]]` entry in `.gitleaks.toml` with a `description` rationale. Narrow regex preferred over path-blanket. Never inline `# gitleaks:allow` comments.

### Local mirror — pre-push hook

A bash hook under `.githooks/pre-push` runs the same `tsc --noEmit` locally if the push range touches `services/web/`. It catches the failure before it hits CI and saves a round-trip.

Enable per clone (one-time):

```bash
git config --local core.hooksPath .githooks
```

The hook is a no-op for pushes that don't touch `services/web/`. If `services/web/node_modules` is missing it prints `npm ci` instructions and exits 1 rather than silently passing. Bypass with `git push --no-verify` (not recommended).

### Why `latest`, not `${github.sha}`, in the deploy step

Path-filter builds only the changed image (api OR web), so a single `${github.sha}` tag will not exist for the unchanged image. The deploy step therefore pulls `:latest`. For rollback, SSH in and run with a pinned tag — see [Rollback](#rollback).

---

## `terraform.yml` — infra plan-on-PR

Runs on every PR (and master push) that touches `infra/terraform/**` or the workflow file itself. Steps:

1. `terraform fmt -check -recursive`
2. `terraform init -input=false`
3. `terraform validate -no-color`
4. `terraform plan -no-color -lock=false -input=false`
5. Posts the plan as a PR comment (truncated at 60k chars).

`-lock=false` is intentional: the plan-only IAM identity has `ReadOnlyAccess` and cannot write the S3 lockfile. Plan is read-only against state, so concurrent plans don't corrupt anything. Local apply (with admin creds) still locks normally.

**Apply is manual** from an operator workstation with admin AWS creds. Auto-apply will stay off until the team is large enough to justify expanding the apply IAM identity. See [`docs/operations/iac-runbook.md`](../operations/iac-runbook.md) for the apply procedure.

---

## `cost-report.yml` — daily spend + inventory email

Documented in [`docs/ops/reports.md`](./reports.md). One-time SES setup notes:

- `aws_ses_email_identity.kris` triggers AWS to send a verification email to `kristopher.lopez@gmail.com` on first apply. **Click the link in that inbox once.** Until you do, the workflow fails on `SendEmail` with `Email address is not verified`.
- The domain identity (`jeromelu.ai`) auto-verifies once Route53 propagates the DKIM CNAMEs (~5-15 min). `aws_ses_domain_identity_verification` blocks `terraform apply` until SES confirms — so if apply finishes, DKIM is good.

Re-run manually: `gh workflow run cost-report.yml`.

---

## Lightsail cron schedule

GitHub Actions only handles `cost-report.yml`. Everything else recurring runs as Linux cron on the Lightsail box itself. The schedule is checked in at [`scripts/cron.d/jeromelu`](../../scripts/cron.d/jeromelu) and installed to `/etc/cron.d/jeromelu` by [`scripts/lightsail-deploy.sh`](../../scripts/lightsail-deploy.sh) on every deploy. Do not hand-edit `/etc/cron.d/jeromelu` — edit the source and redeploy.

| When (UTC / AEST) | Job | What it does |
|---|---|---|
| `30 16 * * *` / 02:30 | `pg-backup.sh` | Streams `pg_dump` to `s3://jeromelu-public-assets/backups/postgres/`. 14-day S3 lifecycle retention. |
| `0 18 * * *` / 04:00 | `scout-refresh.sh nrlcom-draw` | Archives current-round nrl.com draw JSON to S3. |
| `15 18 * * *` / 04:15 | `scout-refresh.sh nrlcom-match-centre` | Archives current-round match-centre JSON to S3. |
| `30 18 * * *` / 04:30 | `scout-refresh.sh nrlcom-casualty-ward` | Archives daily nrl.com casualty-ward snapshot to S3. |
| `45 18 * * *` / 04:45 | `scout-refresh.sh nrlcom-ladder` | Archives current-round nrl.com ladder JSON to S3. |
| `50 18 * * *` / 04:50 | `scout-refresh.sh nrlcom-stats` | Archives nrl.com stat leaderboards to S3. |
| `20 19 * * *` / 05:20 | `scout-populate.sh nrlcom-current` | Projects latest Scout S3 archives into relational DB tables inside `jeromelu-api`; season-aware phases use the current season, identity/re-resolution phases may inspect existing DB rows. |
| `45 22 * * *` / 08:45 | `scout-refresh.sh supercoach-roster` | Archives SuperCoach roster and applies the SCD-2 people/player-attributes refresh. |
| `55 22 * * 0,2,4` / Mon/Wed/Fri 08:55 | `scout-refresh.sh supercoach-stats current` | Resolves SuperCoach `current_round` and upserts current-round `player_rounds`. |
| `0 23 * * *` / 09:00 | `scout-refresh.sh channel-stats` | POSTs to `/api/admin/scout/refresh-channel-stats`. Snapshots subscriber/video/view counts into `channel_metrics`. ~3 YouTube quota units. |
| `15 23 * * *` / 09:15 | `scout-refresh.sh videos` | POSTs to `/api/admin/scout/refresh-videos`. Enumerates new videos per channel + snapshots `video_metrics`. ~750 quota units. Staggered 15 min after channel-stats to avoid DB-connection contention. |
| `30 23 * * 1` / Tue 09:30 | `scout-refresh.sh supercoach-teams` | Enriches `teams.metadata_json.supercoach`. |
| `35 23 * * 1` / Tue 09:35 | `scout-refresh.sh supercoach-settings` | Snapshots SuperCoach classic settings into `sc_settings`. |
| `40 23 * * 1` / Tue 09:40 | `scout-refresh.sh nrlcom-players-roster` | Archives nrl.com player profile listings for all NRL teams. |
| `30 0 * * *` / 10:30 | `cron-report.sh` | Cron-health digest email — see [`reports.md`](./reports.md). |
| `35 0 * * *` / 10:35 | `error-report.sh` | App-error digest email — see [`reports.md`](./reports.md). |
| `0 22 * * 1` / Tue 08:00 | `content-report.sh` | Weekly content digest — see [`reports.md`](./reports.md). |
| `30 22 * * 1` / Tue 08:30 | `disk-report.sh` | Weekly capacity report — see [`reports.md`](./reports.md). |

All jobs run as the `ubuntu` user — the deploy user, member of the `docker` group, owner of `/opt/jeromelu` and `~/.aws/credentials`. AEST clock times are nominal — during AEDT each job fires an hour later in local time. Box stays in UTC.

Per-job log files under `/var/log/jeromelu/`:

| Log file | Producer |
|---|---|
| `scout-refresh.log` | Scout endpoint refreshes; one line per run with timestamp + HTTP status + response body |
| `scout-populate.log` | Scout S3-to-DB projection wrapper; command/status lines plus populate output; consumed by `cron-report.sh` for the `nrlcom-current` row |
| `pg-backup.log` | pg-backup runs; one line per successful run |
| `cron-report.log` · `error-report.log` · `content-report.log` · `disk-report.log` | full text version of each digest sent |

### Python deps for the report scripts

The four report scripts (`*_report.py`) need `boto3` and nothing else. Installed once on the box via `apt-get install python3-boto3` by `lightsail-deploy.sh` on first deploy. Ubuntu's distro version is ~v1.20 — old, but plenty for SES + S3 list_objects. No venv: one system package is simpler than venv + python3-venv.

---

## Self-hosted runner

### Topology

| Piece | Detail |
|---|---|
| Box | Lightsail instance `jeromelu` (Ubuntu 22.04 x86_64) |
| Install path | `/opt/actions-runner` |
| Runs as | system user `ubuntu` (member of `docker` group) |
| Service | systemd unit `actions.runner.kristopherlopez-Jeromelu.jeromelu-prod.service` |
| Labels | `self-hosted`, `linux`, `x64`, `jeromelu-prod` |
| Targeted by | `deploy-lightsail` job in `.github/workflows/deploy.yml` |

The runner runs as `ubuntu` rather than a fresh user because that account already owns `/opt/jeromelu`, has docker socket access, and has working AWS creds for `aws ecr get-login-password`. The deploy already executed under this identity over SSH; the self-hosted runner is the same identity with a different transport. This trade is acceptable because the repo is private and single-author — anyone able to push to `master` already has deploy capability.

### Initial setup

```bash
# 1. Mint a registration token (valid 1 hour) from a local machine with `gh` auth
gh api -X POST repos/kristopherlopez/Jeromelu/actions/runners/registration-token \
  --jq '.token'

# 2. On the box, install and register
ssh jeromelu-prod
sudo mkdir -p /opt/actions-runner && sudo chown ubuntu:ubuntu /opt/actions-runner
cd /opt/actions-runner
curl -fsSL -o runner.tar.gz \
  https://github.com/actions/runner/releases/download/v2.334.0/actions-runner-linux-x64-2.334.0.tar.gz
tar xzf runner.tar.gz && rm runner.tar.gz

./config.sh \
  --url https://github.com/kristopherlopez/Jeromelu \
  --token <TOKEN> \
  --name jeromelu-prod \
  --labels self-hosted,linux,x64,jeromelu-prod \
  --work _work \
  --unattended --replace

sudo ./svc.sh install ubuntu
sudo ./svc.sh start
```

### Operating

| Task | Command |
|---|---|
| Status | `sudo /opt/actions-runner/svc.sh status` |
| Restart | `sudo /opt/actions-runner/svc.sh stop && sudo /opt/actions-runner/svc.sh start` |
| Logs | `sudo journalctl -u actions.runner.kristopherlopez-Jeromelu.jeromelu-prod -f` |
| Confirm online (from anywhere) | `gh api repos/kristopherlopez/Jeromelu/actions/runners` |
| Upgrade | the runner self-updates when GitHub publishes a newer version |

### Removal / re-registration

If the runner needs to be torn down (e.g. moving boxes):

```bash
# On the box
sudo /opt/actions-runner/svc.sh stop
sudo /opt/actions-runner/svc.sh uninstall
cd /opt/actions-runner
./config.sh remove --token <REMOVE_TOKEN>   # mint via gh api .../remove-token
sudo rm -rf /opt/actions-runner
```

---

## IAM identities

Two AWS IAM identities exist solely to serve CI:

| Identity | Used by | Permissions |
|---|---|---|
| `jeromelu-cicd` (IAM user, programmatic) | `deploy.yml` build/push + CloudFront invalidation | ECR push/pull on `jeromelu/web` + `jeromelu/api`; `cloudfront:CreateInvalidation`/`GetInvalidation` on `E2G6FL11A3JP8F`; `s3` r/w on the three project buckets; `ssm:GetParameter*` on `/jeromelu/*`. |
| `jeromelu-terraform-plan` (IAM user, programmatic) | `terraform.yml` plan-on-PR | AWS-managed `ReadOnlyAccess`. Read-only against state; cannot write the S3 lockfile (hence `-lock=false`). |

Live inventory and ARNs: [`docs/operations/aws-resource-inventory.md`](../operations/aws-resource-inventory.md) §11.2.1.

---

## Required GitHub Actions secrets

| Secret | Used by | Source |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | `deploy.yml` | `jeromelu-cicd` access key |
| `AWS_SECRET_ACCESS_KEY` | `deploy.yml` | `jeromelu-cicd` secret |
| `TF_AWS_ACCESS_KEY_ID` | `terraform.yml` | `jeromelu-terraform-plan` access key |
| `TF_AWS_SECRET_ACCESS_KEY` | `terraform.yml` | `jeromelu-terraform-plan` secret |

Set under **Settings → Secrets and variables → Actions**. Rotation procedure in [`docs/operations/iac-runbook.md`](../operations/iac-runbook.md).

The legacy `LIGHTSAIL_HOST` / `LIGHTSAIL_USER` / `LIGHTSAIL_SSH_KEY` secrets from the SSH-deploy era are **no longer used** and can be removed.

---

## Migrations

The `migrate` job in `deploy.yml` is intentionally notify-only — it does not auto-apply schema changes. After CI deploys new code that depends on a migration, apply it from the box:

```bash
ssh jeromelu-prod
cd /opt/jeromelu
set -a; . ./.env; set +a
DATABASE_URL="postgresql://${POSTGRES_USER:-jeromelu_admin}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB:-jeromelu}" \
  bash packages/db/migrate.sh
```

Project convention: always apply via `make migrate` (or `migrate.sh`) — never hand-apply SQL, since tracking goes stale and creates hidden drift.

---

## Rollback

`deploy.yml` deploys `:latest`. To roll back to a specific git SHA:

```bash
ssh jeromelu-prod
IMAGE_TAG=<sha> /opt/jeromelu/scripts/lightsail-deploy.sh
```

The image tag must exist in ECR — only the *changed* service is built per push, so the SHA tag exists only for whichever of api/web changed in that commit. For a coordinated api+web rollback, deploy each side to its own last-good SHA.

---

## Related docs

- [`docs/ops/reports.md`](./reports.md) — every email Jeromelu sends to me (cost, cron, errors, content, capacity).
- [`docs/architecture/09-aws-architecture.md`](../architecture/09-aws-architecture.md) — AWS topology the pipeline deploys onto.
- [`docs/operations/aws-setup-guide.md`](../operations/aws-setup-guide.md) — one-time provisioning runbook (Phase L8 covers CI secrets).
- [`docs/operations/aws-resource-inventory.md`](../operations/aws-resource-inventory.md) — live IAM / ECR / CloudFront resource inventory.
- [`docs/operations/iac-overview.md`](../operations/iac-overview.md) / [`iac-runbook.md`](../operations/iac-runbook.md) — Terraform decisions and apply procedure.
- [`infra/terraform/README.md`](../../infra/terraform/README.md) — per-resource adoption status.
- [`scripts/lightsail-deploy.sh`](../../scripts/lightsail-deploy.sh) — the deploy script the runner invokes.
