---
tags: [area/architecture]
---

# AWS Architecture — Jeromelu V1

This is the practical AWS shape for Jeromelu V1. We deliberately picked the cheapest realistic AWS deployment that keeps the site online: a single Lightsail VM running everything via Docker Compose, with CloudFront/Route 53/S3 around it. Target run-rate is ~$12.50/mo (Sydney pricing — we sit on `small_3_2` at $12/mo; was on `micro_3_2` at $7/mo until 2026-05-12 when the 1 GB box OOM'd under compose rolls).

If load grows past what one Lightsail instance can serve, the migration target is ECS Fargate behind an ALB — see "Future scale path" at the bottom.

> **Provisioning:** as of 2026-04-29 the AWS resources described below are being
> adopted into Terraform under [`infra/terraform/`](../../infra/terraform/README.md).
> See the IaC document set:
> [overview](../operations/iac-overview.md) (decisions),
> [migration plan](../operations/iac-migration-plan.md) (project plan),
> [runbook](../operations/iac-runbook.md) (execution checklist).

## Why Lightsail (not Fargate) for V1

The previous V0 architecture used VPC + NAT Gateway + ALB + ECS Fargate + RDS. That setup ran ~$140/mo even at zero traffic, because NAT ($53), ALB ($18), Fargate 24/7 ($32), and RDS 24/7 ($21) are all fixed idle costs.

Lightsail collapses all of those into a single $12/mo VM with a free static IP and 3 TB egress included. We give up multi-AZ, auto-scaling, and managed Postgres backups in exchange for a ~12× cost reduction. Backups are handled by a nightly `pg_dump` to S3.

## Topology

```
Internet
  │
  ▼
Route 53 (jeromelu.ai zone)
  │
  ├── jeromelu.ai, www.jeromelu.ai → CloudFront → Lightsail static IP (HTTPS)
  └── api.jeromelu.ai             → Lightsail static IP (HTTPS, direct)

Lightsail instance ($12/mo, 2 GB RAM, 2 vCPU, 60 GB SSD, 3 TB egress)
  ├── caddy           (reverse proxy + auto Let's Encrypt TLS)
  ├── web             (Next.js, port 3000, image from ECR)
  ├── api             (FastAPI, port 8000, image from ECR)
  └── postgres        (pgvector/pg16, local Docker volume)

S3 buckets
  ├── jeromelu-raw-transcripts    (raw YouTube transcripts)
  ├── jeromelu-clean-documents    (cleaned + processed)
  └── jeromelu-public-assets      (+ /backups/postgres for nightly pg_dump)

ECR
  ├── jeromelu/web
  └── jeromelu/api
```

## Components

### Compute — Amazon Lightsail
- Single instance, ap-southeast-2a, Ubuntu 22.04, `small_3_2` ($12/mo) plan.
- Static public IP attached (free while attached).
- Firewall: 22 (SSH from operator IP), 80, 443 from `0.0.0.0/0`.
- Runs `docker compose -f docker/docker-compose.prod.yml up -d`.
- Snapshots: weekly manual snapshot, $0.05/GB-mo.

### Edge — Amazon CloudFront
- Free plan (1 TB egress + 10M requests/mo always-free).
- Distribution `E2G6FL11A3JP8F`, custom origin = Lightsail static IP over HTTPS.
- Origin certificate: Let's Encrypt via Caddy on the instance.
- Sits in front of `jeromelu.ai` and `www.jeromelu.ai` only. `api.jeromelu.ai` skips CloudFront (low value for a stateful API).
- WAF included via the free plan.

### DNS — Route 53
- Hosted zone `jeromelu.ai` ($0.50/mo).
- A-records: `jeromelu.ai` and `www.jeromelu.ai` alias to CloudFront; `api.jeromelu.ai` alias/A to Lightsail static IP.
- TTL 60s on production records to allow fast failover.

### TLS — Caddy + ACM
- Caddy on the Lightsail box auto-provisions Let's Encrypt certs for `jeromelu.ai`, `www.jeromelu.ai`, and `api.jeromelu.ai` via HTTP-01.
- ACM certificate in `us-east-1` is still required by CloudFront for the `jeromelu.ai`/`*.jeromelu.ai` viewer cert (kept).
- The `ap-southeast-2` ACM cert (originally for the ALB) is no longer in use — slated for deletion.

### Database — Postgres on Lightsail
- `pgvector/pgvector:pg16` container with a named Docker volume on the instance's local SSD.
- Migrations run on container init via `packages/db/docker-entrypoint-initdb.sh`.
- **Backups:** `scripts/pg-backup.sh` runs via cron at 02:30 Sydney → `s3://jeromelu-public-assets/backups/postgres/jeromelu-<ts>.sql.gz`. S3 lifecycle deletes after 14 days.
- **DR:** restore = pull most recent dump from S3 → `gunzip | psql` into the container. Tested as part of cutover (Phase 2).

### Object Storage — S3 (unchanged from V0)
- `jeromelu-raw-transcripts`, `jeromelu-clean-documents`, `jeromelu-public-assets`.
- All `ap-southeast-2`, public access blocked, SSE-S3.

### Container Registry — ECR
- Two repos in V1: `jeromelu/web`, `jeromelu/api`.
- `worker-*` repos kept for now but unused; pruned in Phase 5.
- Lifecycle: keep last 10 tagged images, delete untagged after 14 days.

### Secrets — Parameter Store SecureString
- DB password, OpenAI key, admin key, AWS access keys for the instance role.
- Migrated from Secrets Manager (~$1.20/mo saved).
- The Lightsail box pulls these at deploy time into `/opt/jeromelu/.env` via `aws ssm get-parameters-by-path`.

### CI/CD — GitHub Actions
- `.github/workflows/deploy.yml`:
  1. Detect changed paths (api / web / db only — see the workflow header for what is *not* in scope, e.g. `services/gpu`).
  2. Build + push `web` / `api` images to ECR (tagged with git SHA + `latest`).
  3. Run `scripts/lightsail-deploy.sh` on the Lightsail box via a **self-hosted GitHub Actions runner** installed there (label `jeromelu-prod`). No inbound SSH from GitHub — the runner connects outbound. See [`docs/ops/ci-cd.md`](../ops/ci-cd.md) for the full pipeline overview.
  4. Invalidate CloudFront if `web` changed.
  5. `db` changes trigger a notify-only `migrate` job; the operator applies migrations from the box.
- Secrets needed: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`. The old SSH-based secrets (`LIGHTSAIL_HOST`, `LIGHTSAIL_USER`, `LIGHTSAIL_SSH_KEY`) are no longer used.

### IAM
- One IAM user (`jeromelu-cicd`) with: `ECR push/pull`, `CloudFront create-invalidation`, `S3 read/write` on the three buckets, `SSM GetParameter*`.
- One instance role attached to the Lightsail box: same S3 + SSM permissions, no ECR (instance pulls via long-lived access key in `.env`, since Lightsail doesn't support EC2 instance roles directly).

### Observability
- Container logs to `journald` via Docker's `journald` log driver.
- Operator tails via `make prod-logs`.
- No CloudWatch agent in V1 — rely on Lightsail's built-in instance metrics dashboard.
- Alarms: skipped for V1; revisit when there are real users.

## What we do NOT run on AWS in V1

| Component | V0 plan | V1 reality |
|---|---|---|
| ALB | Fronted ECS services | Removed. Caddy on Lightsail is the proxy. |
| NAT Gateway | For private subnets | Removed. Single instance lives in a Lightsail-managed network with public IP. |
| RDS | Managed Postgres | Replaced by Postgres container + S3 backups. |
| ECS Fargate | All services | Replaced by Docker Compose on Lightsail. |
| Worker services | 4 workers on Fargate | Not running. When needed, run as compose profiles or cron jobs on the same instance, or revive on Lambda/Fargate per-job. |
| Temporal | Workflow orchestration | Not running in V1. Local dev only. |
| Secrets Manager | Secrets store | Replaced by Parameter Store SecureString. |
| KMS CMK | Customer-managed key | Removed. AWS-managed keys used everywhere. |
| WAF (standalone) | Web ACL on ALB | Replaced by CloudFront free-plan WAF. |
| X-Ray / CloudTrail | Tracing & audit | Skipped for V1. |

## Cost estimate

| Line item | $/mo |
|---|---|
| Lightsail instance (`small_3_2`: 2 GB RAM, 3 TB egress included) | 12.00 |
| Lightsail static IP (free while attached) | 0.00 |
| Lightsail snapshots (1 weekly × ~5 GB) | ~0.25 |
| Route 53 hosted zone | 0.50 |
| S3 storage (3 buckets, low GB) | <0.20 |
| S3 lifecycle backups (14 d × ~5 MB/d) | ~0.01 |
| ECR storage (2 repos × ~500 MB) | ~0.10 |
| CloudFront | 0.00 (free plan) |
| ACM | 0.00 |
| Parameter Store (Standard) | 0.00 |
| CloudWatch Logs (none in V1) | 0.00 |
| **Total** | **~$12.50–13.00/mo** |

Tax (~10% AU GST) brings the bill to ~$14.00/mo all-in. Egress beyond the 3 TB included in the Lightsail plan is $0.09/GB, which would matter only with substantial real traffic.

## Future scale path (when V1 outgrows Lightsail)

Trigger to migrate: sustained CPU/RAM > 70% on the `small_3_2` ($12) plan after a bump to the next Lightsail tier, OR clear need for multi-AZ HA.

Migration target:
1. Move Postgres back to RDS or Aurora Serverless v2 (min 0 ACU).
2. Move web + api back to ECS Fargate behind an ALB.
3. Reintroduce VPC private subnets + NAT (or VPC endpoints to keep cost down).
4. Reintroduce Secrets Manager if rotation matters.
5. Restore worker services on Fargate or run as Lambda.

The image format, ECR repos, GitHub Actions structure, and CloudFront distribution all carry over — only the deploy target changes. Estimated rebuild cost: 2–3 days.

## File map

| File | Purpose |
|---|---|
| `infra/terraform/` | Terraform source for all adopted AWS resources. |
| `infra/terraform/README.md` | IaC runbook + per-resource adoption status. |
| `docs/operations/iac-overview.md` | Why Terraform, what is/isn't managed, migration roadmap. |
| `docker/docker-compose.prod.yml` | Production stack (postgres, caddy, web, api). |
| `docker/Caddyfile` | TLS + reverse proxy config. |
| `scripts/lightsail-deploy.sh` | Pull images and restart on the Lightsail box. |
| `scripts/pg-backup.sh` | Cron'd nightly Postgres dump → S3. |
| `.github/workflows/deploy.yml` | CI: build → push to ECR → deploy via self-hosted runner on the Lightsail box. |
| `Makefile` | `deploy-prod`, `prod-shell`, `prod-logs`. |
| `docs/operations/aws-setup-guide.md` | One-time provisioning runbook (manual fallback / historical). |
| `docs/operations/aws-resource-inventory.md` | Live inventory of provisioned AWS resources. |
