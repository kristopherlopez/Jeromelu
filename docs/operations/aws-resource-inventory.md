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

### 11.1 — Lightsail Instance (COMPLETE 2026-04-25)

| Resource | Value |
|----------|-------|
| Instance name | `jeromelu` (note: Lightsail keypair `jeromelu-prod` already used the `-prod` suffix) |
| Bundle | `micro_3_2` — $7/mo (1 GB RAM, 2 vCPU, 40 GB SSD, 1 TB egress) |
| Blueprint | `ubuntu_22_04` |
| Region / AZ | ap-southeast-2a |
| Static IP | `52.65.91.199` (`jeromelu-ip`, attached) |
| SSH key pair | `jeromelu-prod` (ED25519, fingerprint `SHA256:SC5vIKcmU0jNXOwEU9ywmXTejOTOIhkKea5lV5sSTb4`) |
| Private key location | `~/.ssh/jeromelu-prod` on operator workstation |
| Firewall | TCP 22 from `112.213.139.221/32`, TCP 80 + 443 from `0.0.0.0/0` |
| Bootstrap | Docker 29.4.1, Compose v5.1.3, AWS CLI v2, Git installed via cloud-init |
| Swap | 1 GB at `/swapfile` (persisted in `/etc/fstab`) |
| SSH alias | `jeromelu-prod` (configured in operator's `~/.ssh/config`) |

### 11.2 — IAM (COMPLETE 2026-04-25)

| Resource | ARN | Permissions |
|----------|-----|-------------|
| User `jeromelu-cicd` | `arn:aws:iam::111424988703:user/jeromelu-cicd` | ECR push/pull on `jeromelu/web` + `jeromelu/api`, CloudFront `CreateInvalidation`/`GetInvalidation` on `E2G6FL11A3JP8F`. Inline policy: `jeromelu-cicd-permissions`. Access keys stored in GitHub Actions secrets. |
| User `jeromelu-instance` | `arn:aws:iam::111424988703:user/jeromelu-instance` | ECR pull on `jeromelu/web` + `jeromelu/api`, S3 read/write on the 3 jeromelu buckets, SSM `GetParameter*` on `/jeromelu/*`. Inline policy: `jeromelu-instance-permissions`. Access keys live in `/opt/jeromelu/.env` and `~/.aws/credentials` on the Lightsail box. |

### 11.2.1 — GitHub Actions Secrets (COMPLETE 2026-04-25)

Set on `kristopherlopez/Jeromelu`:

| Secret | Value |
|--------|-------|
| `LIGHTSAIL_HOST` | `52.65.91.199` |
| `LIGHTSAIL_USER` | `ubuntu` |
| `LIGHTSAIL_SSH_KEY` | private half of the `jeromelu-prod` ED25519 keypair |
| `AWS_ACCESS_KEY_ID` | `jeromelu-cicd` access key |
| `AWS_SECRET_ACCESS_KEY` | `jeromelu-cicd` secret |

### 11.2.2 — GitHub Deploy Key (COMPLETE 2026-04-25)

| Field | Value |
|-------|-------|
| Title | `lightsail-prod` |
| Type | read-only |
| Key | `~/.ssh/github_deploy` on Lightsail (ED25519) |
| Repo | `kristopherlopez/Jeromelu` |
| ID | `149626439` |

### 11.3 — Parameter Store SecureStrings (COMPLETE 2026-04-25 — replaces Secrets Manager)

| Parameter | Source |
|-----------|--------|
| `/jeromelu/postgres-password` | from `jeromelu/db-credentials` |
| `/jeromelu/openai-api-key` | from `jeromelu/openai-api-key` (still placeholder — replace before LLM use) |
| `/jeromelu/admin-key` | from `jeromelu/app-secrets.ADMIN_API_KEY` |
| `/jeromelu/session-secret` | from `jeromelu/app-secrets.SESSION_SECRET` |
| `/jeromelu/instance-aws-access-key-id` | new — `jeromelu-instance` user access key |
| `/jeromelu/instance-aws-secret-access-key` | new — `jeromelu-instance` user secret |

Pre-existing non-secret parameters from V0 retained: `/jeromelu/env`, `/jeromelu/region`, `/jeromelu/db-name`, `/jeromelu/s3-{raw,clean,assets}-bucket`, `/jeromelu/feature/{chat-enabled,contrarian-mode,publishing-paused}`.

### 11.4 — RDS Final Snapshot (COMPLETE 2026-04-25)

| Resource | Value |
|----------|-------|
| Snapshot ID | `jeromelu-db-pre-lightsail-2026-04-25` |
| Source instance | `jeromelu-db` |
| Status | available, 100% progress, 20 GB |
| Tags | `purpose=pre-lightsail-cutover`, `retain_until=2026-05-25` |
| Retain until | 2026-05-25 (30 days post-cutover) |

### 11.4.1 — DB Migration Verification (COMPLETE 2026-04-25)

Approach: pg_dump 17.9 ran from inside the live `jeromelu-api` ECS task (already in VPC, has DB credentials), streamed via gzip to `s3://jeromelu-public-assets/migration/jeromelu-pre-lightsail-2026-04-25.sql.gz` (15.5 MiB compressed). Lightsail pulled it via presigned URL, restored into `pgvector/pgvector:pg16` container with the same `jeromelu_admin` password as RDS.

Row count parity verified across all 16 tables:

| Table | RDS | Lightsail |
|---|---|---|
| sources | 215 | 215 |
| source_documents | 215 | 215 |
| source_chunks | 221,634 | 221,634 |
| (13 other tables) | 0 | 0 |

Extensions: `plpgsql`, `uuid-ossp`, `vector 0.8.2` (pgvector) — restored intact.

Single benign error during restore: `unrecognized configuration parameter "transaction_timeout"` — RDS-only `SET` at the head of the dump, ignored by open-source pg16; not data-related.

Migration artifacts in S3 (clean up after cutover verified):
- `s3://jeromelu-public-assets/migration/jeromelu-pre-lightsail-2026-04-25.sql.gz`
- `s3://jeromelu-public-assets/migration/rowcounts.sql`
- `s3://jeromelu-public-assets/migration/rds-rowcount.sh`

### 11.5 — DNS Cutover (COMPLETE 2026-04-25)

| Record | Before | After |
|--------|--------|-------|
| `jeromelu.ai` | CloudFront alias (CloudFront → ALB) | CloudFront alias (CloudFront → `origin.jeromelu.ai` → Lightsail) |
| `www.jeromelu.ai` | CloudFront alias | unchanged — but CloudFront has only `jeromelu.ai` in Aliases, so www returns CF error. Pre-existing, separate fix |
| `api.jeromelu.ai` | ALB alias (Z1GM3OXH4ZPM65) | A → 52.65.91.199 (TTL 60) |
| `origin.jeromelu.ai` | (did not exist) | A → 52.65.91.199 (TTL 60) — used by CloudFront origin |

### 11.6 — CloudFront Origin Update (COMPLETE 2026-04-25)

| Distribution | Origin before | Origin after |
|--------------|---------------|--------------|
| `E2G6FL11A3JP8F` | `jeromelu-alb-943756887.ap-southeast-2.elb.amazonaws.com` (HTTPS-only) | `origin.jeromelu.ai` (**HTTP-only**, see note) |

**Note on HTTP-only origin protocol:** CloudFront's HTTPS handshake to Caddy was failing (502 Bad Gateway). Diagnosis pointed at TLSv1.2 + ECDSA-only cipher rejection from CF's edge. Switched origin protocol to `http-only` as a pragmatic fix. User-facing TLS is unchanged — CloudFront still terminates HTTPS via the us-east-1 ACM cert. Only the CloudFront edge ↔ Lightsail hop is plaintext over public internet. **Backlog:** force Caddy to issue RSA certs (`tls { issuer acme { ... } key_type rsa2048 }`) so CF→origin can be HTTPS again.

### 11.8 — V0 Decommission (COMPLETE 2026-04-25)

| Step | Resource | Status |
|------|----------|--------|
| 1 | ECS services scaled to 0, drained | ✓ |
| 2 | ECS services + cluster `jeromelu` deleted | ✓ INACTIVE |
| 3 | ALB `jeromelu-alb` + target groups `jeromelu-web-tg`, `jeromelu-api-tg` deleted | ✓ |
| 4 | NAT Gateway `nat-0ebe6638ebe58e8ce` deleted (EIP auto-released) | ✓ deleted |
| 5 | Routes `0.0.0.0/0 → NAT` removed from `rtb-0e130eca0b7c31bcb`, `rtb-084df4eb73b7c6c30` | ✓ |
| 6 | RDS `jeromelu-db` deletion initiated (deletion protection disabled, automated backups skipped) | deleting; final-snapshot retained as `jeromelu-db-pre-lightsail-2026-04-25` |
| 7 | 3 Secrets Manager secrets scheduled for deletion (7-day recovery window): `jeromelu/db-credentials`, `jeromelu/openai-api-key`, `jeromelu/app-secrets` | ✓ pending-delete 2026-05-02 |
| 8 | KMS CMK `jeromelu-master-key` (`23a1e42f-ac32-4e3b-bd11-3f8e5c0335cc`) scheduled for deletion (7-day window) | ✓ PendingDeletion 2026-05-02 |
| 9 | ECR repo `jeromelu/worker-orchestrator` deleted | ✓ |

ECR repos kept: `jeromelu/web`, `jeromelu/api` (active), and the 4 worker repos (small storage, retained for future use).

### 11.7.1 — Database Migrations Brought Forward (COMPLETE 2026-04-25)

The dump from RDS was schema-frozen at migration 009. Migrations 010–016 had never been applied to RDS (the running ECS api was likely returning 500s on `/api/feed` for the same reason — pre-existing bug). Applied on Lightsail:

- `010_event_feed_rework.sql`
- `011_knowledge_base.sql`
- `012_qa_event_types.sql`
- `013_crew_activity.sql`
- `014_squad.sql`
- `015_wiki.sql`
- `016_insights_kb_types.sql`

`schema_migrations` table populated with all 16 versions.

### 11.7 — App Stack on Lightsail (COMPLETE 2026-04-25)

| Container | Image | Status |
|-----------|-------|--------|
| `jeromelu-postgres` | `pgvector/pgvector:pg16` | healthy, attached to `jeromelu_postgres_data` |
| `jeromelu-api` | `111424988703.dkr.ecr.ap-southeast-2.amazonaws.com/jeromelu/api:latest` | running (uvicorn :8000, `/docs` → 200) |
| `jeromelu-web` | `111424988703.dkr.ecr.ap-southeast-2.amazonaws.com/jeromelu/web:latest` | running (Next.js 16.1.6 :3000, `/` → 200) |
| `jeromelu-caddy` | `caddy:2-alpine` | running (:80, :443) |

Caddy is in ACME retry loop until DNS cuts over (Phase 5) — `jeromelu.ai` and `api.jeromelu.ai` still resolve to CloudFront/ALB. No traffic impact yet; the existing ECS stack still serves users.

Volumes pinned: `jeromelu_postgres_data`, `jeromelu_caddy_data`, `jeromelu_caddy_config`.
