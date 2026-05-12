---
tags: [area/operations]
---

# CI/CD pipeline

Single source of truth for what GitHub Actions does in this repo, end to end.
Three workflows live under `.github/workflows/`:

| Workflow | Trigger | What it does |
|---|---|---|
| `deploy.yml` | push to `master`, `workflow_dispatch` | Build api/web images → push to ECR → restart compose stack on Lightsail → invalidate CloudFront. |
| `tests.yml` | PR / push to `master` | `pytest tests/unit` + `tsc --noEmit` on `services/web`. Runs unconditionally — does NOT gate `deploy.yml` (yet). |
| `terraform.yml` | PR / push touching `infra/terraform/**` | `fmt -check` + `init` + `validate` + `plan`; comments the plan on PRs. **Apply stays manual.** |

The deploy workflow runs the actual deploy step on a **self-hosted GitHub
Actions runner installed on the Lightsail box itself** — not via SSH from a
GitHub-hosted runner. This keeps port 22 locked to the operator's IP and
removes a moving-target firewall problem.

---

## `deploy.yml` — application deploy

Pipeline stages:

1. **`detect-changes`** — `dorny/paths-filter@v3` flags whether `api`, `web`, `video_worker`, `db`, or `deploy_only` paths changed. Sets job-level outputs that gate every downstream job. `deploy_only` covers `scripts/lightsail-deploy.sh`, `scripts/cron.d/**`, `docker/docker-compose.prod.yml`, and `docker/Caddyfile` — changes that need a redeploy of the existing images but no new image build.
2. **`build-and-push`** (matrix: api, web, video-worker) — only fires for the service whose paths changed. Builds the Dockerfile and pushes two tags to ECR: `${github.sha}` and `latest`.
3. **`deploy-lightsail`** — runs on the self-hosted runner (`runs-on: [self-hosted, jeromelu-prod]`) when any of `api / web / video_worker / deploy_only` changed. `cd /opt/jeromelu`, `git pull --ff-only`, then runs `scripts/lightsail-deploy.sh`. The script logs into ECR and then rolls api → web → video-worker **one at a time** (`stop` → `pull` → `up -d --no-deps`), pruning between iterations. Serial rollout is mandatory: the box is a 1 GB `micro_3_2` and parallel pulls + 2× running containers wedge it (memory exhaustion → swap thrash → dockerd hang → runner offline). Brief per-service downtime is the explicit trade.
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
