# Jaromelu — AWS Resource Inventory

Track all created AWS resources here. Updated as infrastructure is provisioned.

> **2026-04-25 — V1 architecture switched from ECS/Fargate to Lightsail.** Phases 1–9 below reflect the original V0 build. Resources marked **DECOMMISSIONED 2026-04-25** are slated for deletion as part of the cutover (see Phase 11). Phase 11 lists the live V1 resources.

---

## Phase 1 — Networking Foundation

### Step 1.1 — VPC (COMPLETE)

| Resource | ID / Value |
|----------|------------|
| VPC | `jeromelu-vpc` — CIDR `10.0.0.0/16` |
| Public subnet 1 | ap-southeast-2a |
| Public subnet 2 | ap-southeast-2b |
| Private subnet 1 | ap-southeast-2a |
| Private subnet 2 | ap-southeast-2b |
| Internet Gateway | `igw-0927b99dac1731a77` |
| NAT Gateway | `nat-0ebe6638ebe58e8ce` (1 AZ) — **DECOMMISSIONED 2026-04-25** (Phase 11) |
| S3 Gateway Endpoint | `vpce-0cf3ea6da9fdf4300` |

### Step 1.2 — Security Groups (COMPLETE)

| Resource | ID | Inbound | Outbound |
|----------|----|---------|----------|
| `jeromelu-alb-sg` | `sg-07f576d4ce99ee90b` | HTTP/80 from 0.0.0.0/0, HTTPS/443 from 0.0.0.0/0 | All traffic |
| `jeromelu-app-sg` | `sg-0fc05899987c60da7` | TCP/3000 from alb-sg, TCP/8000 from alb-sg | All traffic |
| `jeromelu-worker-sg` | `sg-07b938985a1c88680` | None | All traffic |
| `jeromelu-db-sg` | `sg-02c8e33ecca48185b` | TCP/5432 from app-sg, TCP/5432 from worker-sg | None |

VPC: `vpc-0dfbe4160b1d408ef`

---

## Phase 2 — Domain, DNS & Certificates

### Step 2.1 — Route 53 Hosted Zone (COMPLETE)

| Resource | Value |
|----------|-------|
| Domain | `jeromelu.ai` |
| Hosted zone ID | `Z0304833VPJJKDFO86WO` |
| NS 1 | `ns-1048.awsdns-03.org` |
| NS 2 | `ns-372.awsdns-46.com` |
| NS 3 | `ns-1723.awsdns-23.co.uk` |
| NS 4 | `ns-858.awsdns-43.net` |

### Step 2.2 — Namecheap Nameserver Transfer

| Status | ___ |
|--------|-----|

### Step 2.3 — ACM Certificates (COMPLETE)

| Resource | ARN |
|----------|-----|
| Certificate (us-east-1, CloudFront) | `arn:aws:acm:us-east-1:111424988703:certificate/361488ce-fcf5-46ed-8f98-ab25d21c7f0e` |
| Certificate (ap-southeast-2, ALB) | `arn:aws:acm:ap-southeast-2:111424988703:certificate/f270cfe9-d799-4d99-b9c1-1bb93b79fa11` |

Domains: `jeromelu.ai`, `*.jeromelu.ai` — DNS validated via Route 53.

---

## Phase 3 — Data Layer

### Step 3.1 — RDS PostgreSQL (COMPLETE — **DECOMMISSIONED 2026-04-25**)

> Replaced by `pgvector/pg16` container on Lightsail. Final snapshot retained for 30 days (see Phase 11).


| Resource | Value |
|----------|-------|
| Instance ID | `jeromelu-db` |
| Endpoint | `jeromelu-db.cul8lqlvhn3c.ap-southeast-2.rds.amazonaws.com` |
| Port | `5432` |
| Engine version | PostgreSQL 16.6-R3 |
| Instance class | `db.t4g.micro` |
| Storage | gp3, 20 GiB, autoscale to 100 GiB |
| Master username | `jeromelu_admin` |
| Master password | Stored in Secrets Manager (`jeromelu/db-credentials`) |
| Initial database | `jeromelu` |
| Subnet group | `default-vpc-0dfbe4160b1d408ef` |
| Security group | `jeromelu-db-sg` |
| Encryption | aws/rds KMS key |

### Step 3.2 — S3 Buckets (COMPLETE)

| Bucket | Versioning | Encryption |
|--------|------------|------------|
| `jeromelu-raw-transcripts` | Enabled | SSE-S3 |
| `jeromelu-clean-documents` | Disabled | SSE-S3 |
| `jeromelu-public-assets` | Disabled | SSE-S3 |

All buckets: public access blocked, ap-southeast-2.

---

## Phase 4 — Secrets & Configuration

### Step 4.1 — Secrets Manager (COMPLETE — **DECOMMISSIONED 2026-04-25**)

> Migrated to Parameter Store SecureString (Phase 11). Saves ~$1.20/mo.


| Secret | ARN |
|--------|-----|
| `jeromelu/db-credentials` | `arn:aws:secretsmanager:ap-southeast-2:111424988703:secret:jeromelu/db-credentials` |
| `jeromelu/openai-api-key` | `arn:aws:secretsmanager:ap-southeast-2:111424988703:secret:jeromelu/openai-api-key` |
| `jeromelu/app-secrets` | `arn:aws:secretsmanager:ap-southeast-2:111424988703:secret:jeromelu/app-secrets` |

Note: `jeromelu/openai-api-key` has a placeholder value — replace with real key before deployment.

### Step 4.2 — Parameter Store (COMPLETE)

| Parameter | Value |
|-----------|-------|
| `/jeromelu/env` | `production` |
| `/jeromelu/region` | `ap-southeast-2` |
| `/jeromelu/db-name` | `jeromelu` |
| `/jeromelu/s3-raw-bucket` | `jeromelu-raw-transcripts` |
| `/jeromelu/s3-clean-bucket` | `jeromelu-clean-documents` |
| `/jeromelu/s3-assets-bucket` | `jeromelu-public-assets` |
| `/jeromelu/feature/chat-enabled` | `true` |
| `/jeromelu/feature/contrarian-mode` | `true` |
| `/jeromelu/feature/publishing-paused` | `false` |

---

## Phase 5 — Container Registry (ECR) (COMPLETE)

| Repository | Encryption | Lifecycle Rules |
|------------|------------|-----------------|
| `jeromelu/web` | AES-256 | Untagged >14d, keep last 10 |
| `jeromelu/api` | AES-256 | Untagged >14d, keep last 10 |
| `jeromelu/worker-ingestion` | AES-256 | Untagged >14d, keep last 10 |
| `jeromelu/worker-extraction` | AES-256 | Untagged >14d, keep last 10 |
| `jeromelu/worker-decision` | AES-256 | Untagged >14d, keep last 10 |
| `jeromelu/worker-publishing` | AES-256 | Untagged >14d, keep last 10 |

Tag immutability enabled, scan on push enabled.

---

## Phase 6 — IAM Roles

| Role | ARN |
|------|-----|
| `jeromelu-ecs-execution-role` | COMPLETE — managed: `AmazonECSTaskExecutionRolePolicy` + inline: `jeromelu-execution-secrets` |
| `jeromelu-app-task-role` | COMPLETE — inline: `jeromelu-app-permissions` |
| `jeromelu-cicd-deploy-role` | ___ |

---

## Phase 7 — ECS Cluster & Services (COMPLETE — **DECOMMISSIONED 2026-04-25**)

> All ECS services + cluster + ALB + target groups deleted as part of Lightsail cutover. ECR images retained.


| Resource | Value |
|----------|-------|
| ECS Cluster | `jeromelu` (Fargate) |
| Service: web | `jeromelu-web` (desired: 1) |
| Service: api | `jeromelu-api` (desired: 1) |
| Service: worker-ingestion | `jeromelu-worker-ingestion` (desired: 0) |
| Service: worker-extraction | `jeromelu-worker-extraction` (desired: 0) |
| Service: worker-decision | `jeromelu-worker-decision` (desired: 0) |
| Service: worker-publishing | `jeromelu-worker-publishing` (desired: 0) |
| ALB | `jeromelu-alb` — COMPLETE |
| ALB DNS name | `jeromelu-alb-943756887.ap-southeast-2.elb.amazonaws.com` |
| ALB hosted zone ID | `Z1GM3OXH4ZPM65` |
| Target group (web) | `jeromelu-web-tg` (IP, HTTP:3000) |
| Target group (api) | `jeromelu-api-tg` (IP, HTTP:8000) |

---

## Phase 8 — CloudFront (COMPLETE)

| Resource | Value |
|----------|-------|
| Distribution ID | `E2G6FL11A3JP8F` |
| Distribution domain | `d2rchevv847e7k.cloudfront.net` |
| Plan | Free |
| WAF | Enabled (included in plan) |

---

## Phase 9 — Security (COMPLETE)

| Resource | Value |
|----------|-------|
| WAF Web ACL | Enabled via CloudFront free plan (Phase 8) |
| KMS Key | Alias: `jeromelu-master-key`, Key ID: `23a1e42f-ac32-4e3b-bd11-3f8e5c0335cc` — **DECOMMISSIONED 2026-04-25** (scheduled for deletion, 7-day waiting period) |

---

## Phase 10 — DNS Records (COMPLETE)

| Record | Type | Target |
|--------|------|--------|
| `jeromelu.ai` | A (Alias) | `d2rchevv847e7k.cloudfront.net` |
| `www.jeromelu.ai` | A (Alias) | `d2rchevv847e7k.cloudfront.net` |
| `api.jeromelu.ai` | A (Alias) | `dualstack.jeromelu-alb-943756887.ap-southeast-2.elb.amazonaws.com` — **REPOINTED 2026-04-25** to Lightsail static IP (Phase 11) |

---

## Phase 11 — Lightsail Migration (V1 — 2026-04-25)

V0 architecture replaced by a single Lightsail VM running Docker Compose. See `docs/architecture/12-aws-architecture.md` for the rationale and topology.

### 11.1 — Lightsail Instance (PENDING)

| Resource | Value |
|----------|-------|
| Instance name | `jeromelu-prod` |
| Plan | $5/mo (1 GB RAM, 2 vCPU burst, 40 GB SSD, 2 TB egress) |
| Blueprint | Ubuntu 22.04 LTS |
| Region / AZ | ap-southeast-2a |
| Static IP | `___` (attach after launch) |
| SSH key pair | `jeromelu-prod` (ED25519, fingerprint `___`) |
| Firewall | TCP 22 from operator IP, TCP 80 + 443 from 0.0.0.0/0 |

### 11.2 — IAM (PENDING)

| Resource | Value |
|----------|-------|
| User | `jeromelu-cicd` — keys stored in GitHub Actions secrets |
| Permissions | ECR push/pull (web, api), CloudFront create-invalidation on `E2G6FL11A3JP8F`, S3 read/write on the 3 jeromelu buckets, SSM `GetParameter*` on `/jeromelu/*` |

### 11.3 — Parameter Store (PENDING — replaces Secrets Manager)

| Parameter | Type |
|-----------|------|
| `/jeromelu/postgres-password` | SecureString |
| `/jeromelu/openai-api-key` | SecureString |
| `/jeromelu/admin-key` | SecureString |
| `/jeromelu/instance-aws-access-key-id` | SecureString |
| `/jeromelu/instance-aws-secret-access-key` | SecureString |

### 11.4 — RDS Final Snapshot (PENDING)

| Resource | Value |
|----------|-------|
| Snapshot ID | `jeromelu-db-pre-lightsail-2026-04-25` |
| Source instance | `jeromelu-db` |
| Retain until | 2026-05-25 (30 days post-cutover) |

### 11.5 — DNS Cutover (PENDING)

| Record | Was | Will be |
|--------|-----|---------|
| `jeromelu.ai`, `www.jeromelu.ai` | CloudFront alias | CloudFront alias (origin updated to Lightsail static IP) |
| `api.jeromelu.ai` | ALB alias | A record → Lightsail static IP |

### 11.6 — CloudFront Origin Update (PENDING)

| Distribution | Origin was | Origin will be |
|--------------|-----------|----------------|
| `E2G6FL11A3JP8F` | `jeromelu-alb-943756887.ap-southeast-2.elb.amazonaws.com` (HTTPS) | Lightsail static IP (HTTPS, custom origin) |
