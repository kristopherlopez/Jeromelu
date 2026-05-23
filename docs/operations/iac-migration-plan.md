---
tags: [area/operations]
---

# IaC Migration Plan

The project plan for shifting Jeromelu's AWS infrastructure from click-ops to
Terraform. Companion docs:

- [`iac-overview.md`](iac-overview.md) — current state, what's managed,
  drift policy.
- [`iac-runbook.md`](iac-runbook.md) — the operational checklist for
  executing this plan.

## Context

The Jeromelu AWS account (`111424988703`, primary region `ap-southeast-2`)
has been provisioned manually since project inception. The original V0
ECS/Fargate build (Phases 1–10 of
[`aws-resource-inventory.md`](aws-resource-inventory.md)) was created via
the AWS console following the runbook in
[`aws-setup-guide.md`](aws-setup-guide.md). On 2026-04-25 the architecture
was simplified to a single Lightsail VM (Phase 11) — also done by hand.

Click-ops worked for a one-person team building a V1, but it has costs that
compound with time:

- **No source of truth.** The inventory doc is a best-effort transcript of
  console state; it can drift silently.
- **No diff-able history.** Resource changes leave no commit log.
- **No reproducibility.** Spinning the account back up after a catastrophic
  loss would be a multi-hour console crawl through a stale runbook.
- **No safety net.** A wrong click in the console is immediate and
  unreviewed.

Adopting IaC fixes all four. The cost is a one-off migration plus a small
ongoing tax (`terraform apply` instead of clicks for new resources).

## Baseline (before the shift)

The full inventory lives in
[`aws-resource-inventory.md`](aws-resource-inventory.md). Summarised:

| Layer | Live resources | Provisioned via |
|---|---|---|
| Compute | Lightsail `jeromelu` (`small_3_2`) + static IP + keypair + firewall | Console (Phase 11.1) |
| Edge | CloudFront `E2G6FL11A3JP8F` (HTTP-only origin) | Console (Phase 8) |
| TLS | ACM cert in `us-east-1` | Console (Phase 2.3) |
| DNS | Route 53 zone `Z0304833VPJJKDFO86WO` + 4 records | Console (Phases 2.1, 10, 11.5) |
| Storage | 3 S3 buckets + 1 lifecycle rule | Console (Phase 3.2) |
| Registry | 6 ECR repos (2 active, 4 unused) | Console (Phase 5) |
| IAM | 2 users + inline policies | Console (Phase 11.2) |
| Config | 9 String + 6 SecureString SSM parameters | Console (Phases 4.2, 11.3) |
| V0 orphans | VPC, 4 V0 SGs, IGW, S3 gateway endpoint, ap-southeast-2 ACM cert | Decommissioned 2026-04-25, never deleted |

## Target state

After this migration:

- Every resource above (except the V0 orphans, which will be deleted) is
  defined in `infra/terraform/`.
- A single `terraform plan` reports drift, if any, between code and live
  state.
- Every PR touching `infra/terraform/**` runs plan-on-PR via GitHub Actions.
- New resources are added by editing HCL, not clicking. The same applies to
  changes (firewall rules, lifecycle policies, parameter additions, etc.).
- `terraform.tfstate` is the recovery artifact: lose the account, restore
  from S3 versioned state + a fresh `terraform apply`.

What deliberately stays manual is documented in
[`iac-overview.md`](iac-overview.md#what-terraform-does-not-manage). The
short version: secrets values, Lightsail SSH keypair, runtime artefacts.

## Approach: import, don't recreate

Two strategies were considered:

| Strategy | Pros | Cons |
|---|---|---|
| **Import live resources** (chosen) | No downtime; preserves CloudFront distro, certs, S3 history; keeps the static IP and DNS stable | Initial HCL must mirror live state; CloudFront diffs are slow to validate |
| Recreate from scratch | Cleaner HCL with no quirks (e.g. HTTP-only origin); known-good starting point | Downtime during DNS cutover; lose CloudFront distribution ID; new ACM cert validation |

We chose import. The Jeromelu site is live (CloudFront fronting `jeromelu.ai`)
and the cost of recreation outweighs the cost of carrying small live-state
quirks in HCL.

Import is enabled by Terraform 1.7+ `import` blocks (declarative, idempotent,
checked in to `imports.tf`).

## Sequencing — four PRs

Sequenced from low to high blast radius. Each PR is independently
mergeable; nothing in PR(N+1) depends on PR(N) being applied, only on its
HCL existing in the repo.

### PR1 — Scaffold + low-risk imports

- Repo layout, providers (`ap-southeast-2` + `us-east-1` alias), default
  tags, S3 backend.
- `bootstrap/bootstrap.sh` creates the `jeromelu-tfstate` bucket out-of-band.
  State locking is via S3-native lockfile (`use_lockfile = true`); no
  DynamoDB table needed.
- HCL + import blocks for: 3 S3 buckets, 2 ECR repos, 15 SSM parameters.

These are the safest resources to adopt: no inter-resource references,
clear lifecycle, low-stakes if a plan is misread.

### PR2 — Higher-coupling imports

- IAM users + inline policies (`jeromelu-cicd`, `jeromelu-instance`).
- Route 53 zone + 4 records (apex, www, api, origin).
- ACM certificate as a `data` source in `us-east-1`.
- CloudFront distribution `E2G6FL11A3JP8F`.
- Lightsail instance + static IP + attachment + firewall ports.

Higher risk because:
- IAM policy JSON is reconstructed from documentation; live state may
  differ.
- CloudFront takes 10–15 minutes per change to deploy.
- Lightsail keypair import is unreliable, so it is intentionally excluded.

### PR3 — V0 orphan teardown

`infra/terraform/cleanup-v0.sh`: idempotent bash, dry-run by default,
confirms each destruction. Targets:

- VPC `vpc-0dfbe4160b1d408ef` and all its children (endpoints, SGs,
  subnets, route tables, IGW).
- 4 unused worker ECR repositories.
- ap-southeast-2 ACM certificate.

Out-of-band (not Terraform) because the resources never enter our managed
state — there is no value in importing them just to destroy them.

### PR4 — CI workflow

- `.github/workflows/terraform.yml`: `fmt -check`, `init`, `validate`,
  `plan` on every PR. Posts plan output as a PR comment.
- New IAM user `jeromelu-terraform-plan` (created by Terraform, **not**
  imported) with the AWS-managed `ReadOnlyAccess` policy.
- Apply remains manual from operator workstation.

Apply automation is deferred — see
[`iac-overview.md`](iac-overview.md#why-apply-is-not-automated-yet).

## Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `terraform apply` narrows a live IAM policy and breaks consumers | Medium | Auth failures in CI / Lightsail | Pre-flight diff via `aws iam get-user-policy` before first plan; reconcile HCL first |
| CloudFront distribution wants replacement | Low | ~30min downtime + new ACM validation | Inspect `terraform plan` carefully; never apply a CF replacement; reconcile via HCL or `aws cloudfront get-distribution-config` |
| Lightsail import quirks (keypair, static IP attachment) | Medium | Plan errors | Keypair is intentionally excluded; static IP attachment has a documented fallback (`terraform import` CLI) |
| SSM SecureString values land in state | High by design | State contains secrets | State backend is encrypted (SSE-S3) and access-controlled; same risk model as Secrets Manager + Terraform |
| Operator's IP changes; SSH stops working | Low | Lock-out from Lightsail | `operator_ssh_cidr` is a variable; one-line change + apply restores access |
| V0 cleanup deletes a still-used resource | Low | Hard outage | Cleanup script confirms each step; dry-run is the default; production traffic was migrated 2026-04-25 |
| CloudFront WAF Web ACL detached on apply | Low | Loss of free-plan WAF | `web_acl_id` is in `ignore_changes`; live value preserved on import |

## Success criteria

The migration is done when **all** of the following hold:

1. `terraform plan` from a clean working tree shows **zero pending changes**
   for all imported resources (tag additions accepted, anything else
   investigated).
2. `cleanup-v0.sh` reports nothing left to delete.
3. `.github/workflows/terraform.yml` posts a plan comment on a no-op test
   PR within ~3 minutes.
4. [`aws-resource-inventory.md`](aws-resource-inventory.md) header reflects
   that the source of truth is `infra/terraform/`.
5. `make deploy-prod` (the Compose stack) still works end-to-end. IaC must
   not break the application's deploy pipeline.

## Rollback

By design, the migration is largely non-destructive:

- **PR1, PR2, PR4** only *adopt* resources into Terraform state. The live
  resources are unchanged. Rolling back means deleting the state file and
  removing the HCL — the AWS resources keep running.
- **PR3** is destructive and the destruction is intentional. The deleted
  resources have been unused since 2026-04-25; recreating them is a
  multi-hour console job following the V0 setup guide. We accept this.

State recovery: the `jeromelu-tfstate` bucket has versioning enabled. A
corrupted `terraform.tfstate` can be rolled back to a prior version via the
S3 console.

## Post-migration project rule

After PR4 lands, **all new AWS resources must be added in `infra/terraform/`
and applied via PR**. The console is read-only for AWS — exceptions are
limited to:

- Rotating SecureString values and IAM access keys.
- Taking Lightsail snapshots.
- One-off investigation queries (read).

If you find yourself creating something via the console "just for now",
stop and add it to Terraform first. The whole point is to prevent the
state we just spent four PRs unwinding.

## What this migration does NOT do

Out of scope:

- Replacing the Compose-on-Lightsail deploy with Terraform-managed compute.
  The application stack is Compose's responsibility; Terraform manages the
  Lightsail box's existence and its perimeter, not its contents.
- Setting up auto-apply on `master`. Deferred until the team grows.
- Migrating to ECS Fargate. The future scale path
  ([`09-aws-architecture.md`](../architecture/09-aws-architecture.md#future-scale-path))
  is independent of the IaC migration; doing both at once would be reckless.
- Multi-environment (`dev`/`stg`/`prod`). One environment, one state file.
  The layout splits cleanly into `envs/<env>/` if a second environment is
  ever needed.
