---
tags: [area/operations]
---

# Infrastructure as Code Overview

Adopted 2026-04-29. This document captures the *why* behind the IaC choices.
Companion documents:

- [`iac-migration-plan.md`](iac-migration-plan.md) — the project plan for
  shifting from click-ops to Terraform: baseline, target, phases, risks,
  rollback.
- [`iac-runbook.md`](iac-runbook.md) — operational runbook for executing
  the migration and day-2 maintenance.
- [`infra/terraform/README.md`](../../infra/terraform/README.md) — file
  layout, commands, status table.

## Decision: Terraform

Considered: Terraform, AWS CDK, CloudFormation/SAM, Pulumi.

Picked Terraform because:

- The Lightsail-centric topology has good provider support in the AWS Terraform
  provider (instance, static IP, keypair, firewall). CloudFormation Lightsail
  coverage is partial; CDK has no L2 Lightsail constructs.
- Solo-operator setup. Flat HCL is easier to scan and review than a typed CDK
  tree.
- Terraform 1.7+ `import` blocks let us adopt the existing manually-created
  AWS estate without recreating anything. Each `import` is idempotent and lives
  in the repo as a permanent record of provenance.

The main tradeoff: Terraform does not manage things that already ran on the
Lightsail box (cloud-init, Docker volumes, Caddy ACME, container images). Those
remain the responsibility of `docker-compose.prod.yml` and the deploy script.
"Rebuild from IaC" is therefore a two-step recipe (`terraform apply`, then SSH
in and run compose), not a one-button operation. We accept this in exchange for
the cost and simplicity wins of Lightsail.

## State backend

- **Bucket:** `jeromelu-tfstate` (ap-southeast-2, versioned, SSE-S3, public
  access blocked). Created out-of-band by `infra/terraform/bootstrap/bootstrap.sh`.
- **Locking:** S3-native lockfile (`use_lockfile = true` in `backend.tf`) —
  Terraform 1.10+ feature. No DynamoDB table required.
- **State key:** `prod/terraform.tfstate`.

The bootstrap bucket cannot live in the same Terraform root it backs, so it
is created by the bootstrap script and tagged `ManagedBy=bootstrap-script` to
make this lineage visible.

## What Terraform does **not** manage

| Asset | Owned by | Why not Terraform |
|---|---|---|
| IAM access keys | manual rotation | secrets must never enter state |
| Parameter Store SecureString *values* | console / aws CLI | rotated independently of infra changes; HCL has `ignore_changes = [value]` |
| Lightsail snapshots | console / cron | backup policy, not infra |
| Postgres data volume | Docker volume on the instance | runtime data |
| Container images | GitHub Actions → ECR push | application artefacts |
| Caddy ACME certificates | Caddy on the instance | runtime |
| GitHub Actions secrets | GitHub UI | platform-specific |

If one of these changes and `terraform plan` still shows clean, that is correct.

## Drift policy

1. `terraform plan` runs on every PR (when CI is wired in PR4).
2. A weekly scheduled `terraform plan` will alert on drift caused by
   out-of-band changes — to be added when there is real ops volume.
3. Drift detected: prefer updating the HCL to match live state. Only update
   the live resource if the HCL already represents the intent and the live
   state is wrong.

## Migration roadmap

Tracked as four PRs, sequenced from low to high blast radius:

1. **PR1** — scaffold, state backend, S3, ECR, SSM Parameter Store.
2. **PR2** — IAM users (`jeromelu-cicd`, `jeromelu-instance`), Route 53 zone +
   records, ACM (data source), CloudFront, Lightsail (instance, static IP,
   firewall).
3. **PR3** — V0 orphan cleanup via `infra/terraform/cleanup-v0.sh` (out-of-band
   script with dry-run + per-step confirmation). Deletes the V0 VPC and its
   children, the 4 unused worker ECR repos, and the unused `ap-southeast-2`
   ACM cert.
4. **PR4** — `.github/workflows/terraform.yml`: `fmt` + `validate` + `plan` +
   PR comment on every PR. Auth via a dedicated `jeromelu-terraform-plan` IAM
   user with `ReadOnlyAccess`. Apply remains manual until the operator
   headcount justifies setting up apply automation.

After PR4 lands, the project rule is: any new AWS resource is added in
`infra/terraform/` and applied via PR. No more click-ops.

## Why apply is not automated yet

`terraform apply` for the full Jeromelu account needs near-admin permissions
(IAM user creation, CloudFront updates, Lightsail mutation, etc.). With one
operator, having a long-lived admin access key sit in GitHub Actions secrets
is more risk than running `terraform apply` from the workstation when needed.

When the team grows or apply frequency picks up, the upgrade path is GitHub
OIDC + a `jeromelu-terraform-apply` IAM role. Manual approval gating via a
`production` Actions environment is the natural place to add it.

## Future scale path

If Jeromelu outgrows Lightsail (see
[`docs/architecture/12-aws-architecture.md`](../architecture/12-aws-architecture.md)
"Future scale path"), the migration target is ECS Fargate behind an ALB. The
existing Terraform layout absorbs that cleanly — add `vpc.tf`, `alb.tf`,
`ecs.tf`, `rds.tf`; remove `lightsail.tf`. CloudFront, Route 53, ECR, S3, IAM,
SSM all carry over unchanged.
