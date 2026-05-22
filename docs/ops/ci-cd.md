---
tags: [area/operations]
---

# CI/CD pipeline

Single source of truth for what GitHub Actions does in this repo, end to end.
Four workflows live under `.github/workflows/`:

| Workflow | Trigger | What it does |
|---|---|---|
| `deploy.yml` | push to `master`, `workflow_dispatch` | Build api/web images → push to ECR → restart compose stack on Lightsail → invalidate CloudFront. |
| `tests.yml` | PR / push to `master` | `pytest tests/unit` + `tsc --noEmit` on `services/web`. Runs unconditionally — does NOT gate `deploy.yml` (yet). |
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
- **Tests + web typecheck** — run in `tests.yml` (see below). Not yet a hard gate on `deploy.yml`, but failures still show as red status checks on the commit.

If a new service should ride this pipeline, add a path filter to `detect-changes`, a matrix entry to `build-and-push`, and update this document.

---

## `tests.yml` — unit tests + web typecheck

Runs on every PR and every push to `master`. Two jobs in parallel:

1. **`unit`** — `pytest tests/unit` against `requirements-test.txt`. Lightweight by design: the ML stack (torch, pyannote, deepgram, insightface, opencv) is deliberately excluded. See `tests/README.md` for tier layout.
2. **`web-typecheck`** — `tsc --noEmit` on `services/web`. Runs **unconditionally** (no paths-filter), because the Docker build in `deploy.yml` IS gated by paths-filter — a broken TS import landing in a non-web commit would otherwise stay invisible until the next web-touching commit. This job surfaces the failure at the originating commit. ~1-2 min.

Neither job currently gates `deploy.yml`. Promote to a hard gate by adding `needs: [unit, web-typecheck]` on `deploy-lightsail` once they prove stable.

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

Runs at 22:00 UTC (08:00 AEST). Generates an HTML+plaintext email with:

- Month-to-date AWS spend total, by-service breakdown, and a linear month-end projection.
- Prior month's total (for quick comparison).
- Running resources: Lightsail bundle + state, SageMaker endpoint instance type + desired/current count + autoscaling min/max, and S3 bucket list.

Uses the existing `jeromelu-cicd` GitHub Actions secrets — the IAM policy is extended in `infra/terraform/iam.tf` with `ce:GetCostAndUsage`, a handful of describe-* perms, and scoped `ses:SendEmail`. SES sender + recipient identities live in `infra/terraform/ses.tf`.

### One-time setup after the first `terraform apply`

`aws_ses_email_identity.kris` triggers AWS to send a verification email to `kristopher.lopez@gmail.com`. **Click the link in that inbox once.** Until you do, the workflow fails on `SendEmail` with `Email address is not verified`. After clicking, the identity stays verified indefinitely.

The domain identity (`jeromelu.ai`) auto-verifies once Route53 propagates the DKIM CNAMEs (~5-15 min). Terraform's `aws_ses_domain_identity_verification` blocks `apply` until SES confirms — so if `terraform apply` finishes, DKIM is good.

### Testing without waiting for cron

Trigger the workflow manually: **Actions → Daily cost report → Run workflow**. Or `gh workflow run cost-report.yml`.

---

## Lightsail cron schedule

GitHub Actions only handles `cost-report.yml`. Everything else recurring runs as Linux cron on the Lightsail box itself. The schedule is checked in at [`scripts/cron.d/jeromelu`](../../scripts/cron.d/jeromelu) and installed to `/etc/cron.d/jeromelu` by [`scripts/lightsail-deploy.sh`](../../scripts/lightsail-deploy.sh) on every deploy. Do not hand-edit `/etc/cron.d/jeromelu` — edit the source and redeploy.

| When (UTC / AEST) | Job | What it does |
|---|---|---|
| `0 23 * * *` / 09:00 | `scout-refresh.sh channel-stats` | POSTs to `/api/admin/scout/refresh-channel-stats`. Snapshots subscriber/video/view counts into `channel_metrics`. ~3 YouTube quota units. |
| `15 23 * * *` / 09:15 | `scout-refresh.sh videos` | POSTs to `/api/admin/scout/refresh-videos`. Enumerates new videos per channel + snapshots `video_metrics`. ~750 quota units. Staggered 15 min after channel-stats to avoid DB-connection contention. |
| `30 16 * * *` / 02:30 | `pg-backup.sh` | Streams `pg_dump` to `s3://jeromelu-public-assets/backups/postgres/`. 30-day S3 lifecycle retention. |
| `30 0 * * *` / 10:30 | `cron-report.sh` → `cron_report.py` | Sends the daily cron-health digest email (see below). Runs *after* all other jobs so it can report on the trailing 24h. |

All jobs run as the `ubuntu` user — the deploy user, member of the `docker` group, owner of `/opt/jeromelu` and `~/.aws/credentials`. AEST clock times are nominal — during AEDT each job fires an hour later in local time. Box stays in UTC.

Per-job log files under `/var/log/jeromelu/`:

| Log file | Producer |
|---|---|
| `scout-refresh.log` | both scout-refresh runs; one line per run with timestamp + HTTP status + response body |
| `pg-backup.log` | pg-backup runs; one line per successful run |
| `cron-report.log` | cron-report runs; full text version of each digest sent |

---

## `cron-report.sh` — daily cron-health digest email

Sister to the GHA cost report. Where `cost-report.yml` covers AWS spend, the cron report covers whether the scheduled jobs we depend on actually ran in the trailing 24h and what they produced.

Lands at 00:30 UTC = **10:30 AEST**, late enough for the worst-case `videos` refresh (kicked off 23:15 UTC, can take ~45 min) to have completed.

Each row is one of:

| Status | Means |
|---|---|
| `✓ ok` | Run landed in the expected window AND exited clean AND wrote rows to its destination table/object |
| `⚠ warn` | Run landed but something is off — non-clean exit, suspiciously zero rows, or status couldn't be determined (e.g. missing `GITHUB_TOKEN` for the cost-report row) |
| `✗ fail` | No evidence of a run in the 25h window OR the run exited non-zero / non-2xx |

### Why on the box, not GHA

The digest needs to read Postgres (to count what each job actually wrote) and `/var/log/jeromelu/*.log` (to know exit status). Running from GHA would force us to expose a new admin endpoint or push job summaries to S3 first — needless indirection.

Trade: if the Lightsail box itself is down, no digest arrives. That is the dead-man's switch — **no morning email means check the box**. The Lightsail dashboard is the external monitor.

### How the rows are determined

| Job | "Did it run?" | "What it did" |
|---|---|---|
| GHA cost-report | GitHub Actions REST API — most recent run of `cost-report.yml` | Workflow conclusion (success/failure/in_progress) |
| Scout: channel-stats | `scout-refresh.log` — latest `channel-stats` line, parse `status=` and `curl_rc=` | DB: total + distinct rows in `channel_metrics` over 24h |
| Scout: videos | Same file, `videos` lines | DB: total + distinct rows in `video_metrics` over 24h + count of new `sources(source_type='video')` rows |
| pg-backup | S3 `list_objects_v2` on `s3://jeromelu-public-assets/backups/postgres/` — latest object's `LastModified` | S3 key + size |

Zero rows on a successful run is **suspicious** for channel-stats and videos (every run snapshots every existing entity, so zero rows means the work didn't land) — those get `⚠ warn`. Zero *new* videos on a clean videos run is fine — most days there are no new uploads.

### Required env

Lives in `/opt/jeromelu/.env`, sourced by `scripts/cron-report.sh`:

| Var | Purpose | Required? |
|---|---|---|
| `POSTGRES_USER`, `POSTGRES_DB` | `docker exec ... psql` into the postgres container | Already present for the rest of the stack |
| `GITHUB_TOKEN` | Fine-grained PAT with `actions:read` on this repo. Lets the digest query GHA API for cost-report run status. | Optional — without it the cost-report row degrades to `⚠ warn` (status unknown) rather than failing the whole report |

### IAM

The `jeromelu-instance` user gets `ses:SendEmail` scoped to the existing SES identities — see the `SESSendCronReport` statement in [`infra/terraform/iam.tf`](../../infra/terraform/iam.tf). Same SES sender (`reports@jeromelu.ai`) and recipient (`kristopher.lopez@gmail.com`) as the GHA cost report — no new SES identity setup needed.

### Python deps

The script needs `boto3` (everything else is stdlib). On the box it lives in a dedicated venv at `/opt/jeromelu/.venv-ops`, bootstrapped by `lightsail-deploy.sh` on first deploy and re-used thereafter. Kept separate from any service venv so a future api image rebuild can't pull deps out from under cron.

### Testing without waiting for cron

```bash
ssh jeromelu-prod
. /opt/jeromelu/.env
/opt/jeromelu/.venv-ops/bin/python /opt/jeromelu/scripts/cron_report.py
```

Prints the plaintext digest to stdout, then `---sending---`, then `sent OK` once SES accepts it. To dry-run without actually sending, comment the `send_email(...)` call in `main()` — there is no `--dry-run` flag.

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

- [`docs/architecture/12-aws-architecture.md`](../architecture/12-aws-architecture.md) — AWS topology the pipeline deploys onto.
- [`docs/operations/aws-setup-guide.md`](../operations/aws-setup-guide.md) — one-time provisioning runbook (Phase L8 covers CI secrets).
- [`docs/operations/aws-resource-inventory.md`](../operations/aws-resource-inventory.md) — live IAM / ECR / CloudFront resource inventory.
- [`docs/operations/iac-overview.md`](../operations/iac-overview.md) / [`iac-runbook.md`](../operations/iac-runbook.md) — Terraform decisions and apply procedure.
- [`infra/terraform/README.md`](../../infra/terraform/README.md) — per-resource adoption status.
- [`scripts/lightsail-deploy.sh`](../../scripts/lightsail-deploy.sh) — the deploy script the runner invokes.
