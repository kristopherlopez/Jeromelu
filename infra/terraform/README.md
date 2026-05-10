# Jeromelu Terraform

Infrastructure as Code for the AWS resources backing Jeromelu. Adoption of
manually-created resources is in progress — see *Status* below for current
coverage.

## Status

| Layer | In Terraform | Notes |
|---|---|---|
| S3 buckets (3) | yes (PR1) | `raw-transcripts`, `clean-documents`, `public-assets` + lifecycle rule on `backups/postgres/` |
| ECR repos (2) | yes (PR1) | `jeromelu/web`, `jeromelu/api` |
| SSM Parameter Store | yes (PR1) | Strings hold real values; SecureStrings ignore `value` drift |
| IAM users + policies | yes (PR2 + PR4) | `jeromelu-cicd`, `jeromelu-instance` (imported); `jeromelu-terraform-plan` (created). Access keys stay manual. |
| Route 53 zone + records | yes (PR2) | Zone `Z0304833VPJJKDFO86WO`; 4 records (apex, www, api, origin) |
| ACM certificate (CloudFront viewer) | yes (PR2) | `us-east-1`, **data source only** |
| CloudFront distribution | yes (PR2) | `E2G6FL11A3JP8F` — HTTP-only origin override preserved; `web_acl_id` ignored |
| Lightsail instance + static IP + firewall | yes (PR2) | `jeromelu` instance + `jeromelu-ip`. SSH key pair stays manual. |
| V0 orphan teardown | yes (PR3) | Out-of-band script — see [`cleanup-v0.sh`](cleanup-v0.sh) |
| CI workflow (`.github/workflows/terraform.yml`) | yes (PR4) — live 2026-04-30 | Plan-on-PR, comment plan; apply stays manual until apply IAM is sorted |
| Lineup GPU (Phase 5.5) | yes — `lineup.tf` | ECR `jeromelu/lineup-gpu` + S3 `jeromelu-sagemaker-async` (both `us-east-1`) + IAM role `JeromeluSagemakerLineup`. SageMaker model/config/endpoint stay imperative — see [`services/gpu/deploy.py`](../../services/gpu/deploy.py). |

## What is **not** managed by Terraform

Deliberately out of scope, by design:

- IAM access keys for `jeromelu-cicd` and `jeromelu-instance` — rotate manually.
- SecureString **values** in Parameter Store — `lifecycle.ignore_changes = [value]`.
- Lightsail SSH key pair `jeromelu-prod` — keypairs do not round-trip cleanly through `terraform import` (the `public_key` attribute is write-only). Created via console; private half on operator workstation.
- Lightsail snapshots — taken via console / cron.
- Lightsail `user_data` — cloud-init already ran; subsequent edits would either no-op or reprovision the host.
- CloudFront free-plan WAF Web ACL (`web_acl_id`) — auto-created by the free plan; preserved on import via `ignore_changes`.
- Postgres data volume, container images, Caddy ACME certificates — runtime artefacts of the Compose stack.
- GitHub Actions secrets — set in the repo settings UI.

If you change one of these out-of-band and Terraform plan still shows clean,
that is the intended behaviour.

## Layout

```
infra/terraform/
  versions.tf                 Terraform + provider version constraints
  providers.tf                ap-southeast-2 default + us_east_1 alias for CloudFront
  backend.tf                  S3 + DynamoDB state backend
  variables.tf                Inputs
  prod.auto.tfvars            Values for the single (prod) environment
  locals.tf                   Common tags

  s3.tf                       3 buckets, encryption, lifecycle
  ecr.tf                      2 repositories + lifecycle
  ssm.tf                      Parameter Store (String + SecureString)
  iam.tf                      jeromelu-cicd + jeromelu-instance users
  acm.tf                      CloudFront viewer cert (data source, us-east-1)
  cloudfront.tf               Distribution E2G6FL11A3JP8F
  route53.tf                  Hosted zone + 4 records
  lightsail.tf                Instance, static IP, firewall ports

  imports.tf                  `import` blocks adopting live resources
  bootstrap/
    bootstrap.sh              Creates the state bucket + lock table (run once)
```

There is one environment (`prod`). If a second is ever needed, this structure
splits cleanly into `envs/<env>/` with shared modules.

## First-time setup

You need:

- AWS CLI v2 logged in to account `111424988703` with admin or equivalent.
- Terraform `>= 1.7.0` (for `for_each` in `import` blocks).

### Pre-flight: verify policies and parameters match HCL

The IAM policy documents in `iam.tf` are reconstructed from documentation and
may not match live state byte-for-byte. Verify before plan:

```bash
# Diff what's in iam.tf against live.
aws iam get-user-policy --user-name jeromelu-cicd \
  --policy-name jeromelu-cicd-permissions --query PolicyDocument
aws iam get-user-policy --user-name jeromelu-instance \
  --policy-name jeromelu-instance-permissions --query PolicyDocument

# Sanity check on SSM — list of /jeromelu/* params should match `ssm.tf`.
aws ssm describe-parameters \
  --query 'Parameters[?starts_with(Name, `/jeromelu/`)].Name' \
  --output text
```

If anything differs, edit the HCL **before** the first plan so apply does
not narrow live permissions or remove a live parameter.

### Run

```bash
# 1. Create the state backend (one-off, idempotent)
bash infra/terraform/bootstrap/bootstrap.sh

# 2. Initialise Terraform against the new backend
cd infra/terraform
terraform init

# 3. Verify the import blocks land cleanly
terraform plan
#    Expected: imports run and the diff is small
#    (mostly tag additions from default_tags). No replacements.

# 4. Apply
terraform apply
```

If the plan tries to **replace** anything, stop and investigate — do not apply.
The `import` blocks should adopt the live resource; replacements mean the HCL
does not match live state. CloudFront in particular: replacement = ~30 minutes
of downtime + DNS cutover. Reconcile via HCL edits first.

## Adding a new AWS resource

1. Add the resource definition to the relevant `*.tf` file.
2. `terraform plan` from a feature branch.
3. Open a PR. CI runs `fmt`, `validate`, and `plan` (PR4, not yet wired).
4. After review, merge — CI applies on `master`.

## Adopting an existing manually-created resource

1. Write the matching resource block in HCL, mirroring live config as best you can.
2. Add an `import { to = ... id = ... }` block in `imports.tf`.
3. Optional: `terraform plan -generate-config-out=generated.tf` to scaffold the
   resource block from live state. Diff `generated.tf` against your hand-written
   version, take the parts you missed, then delete `generated.tf` (it is in
   `.gitignore`).
4. `terraform plan` until the diff is zero or only acceptable changes (e.g. tag
   additions).
5. `terraform apply`.

## Rotating a secret

The Parameter Store SecureStrings ignore drift on `value`, so you rotate via
console or aws CLI:

```bash
aws ssm put-parameter \
  --name /jeromelu/openai-api-key \
  --type SecureString \
  --value "sk-..." \
  --overwrite
```

Terraform plan will not show this change. Update wherever the secret is
consumed (the `.env` file on the Lightsail box, GitHub Actions secrets, etc.)
separately.

## Cleanup tasks (out-of-band, not in Terraform)

V0 orphans (VPC, V0 security groups, `ap-southeast-2` ACM cert, the 4 unused
worker ECR repos) are handled by [`cleanup-v0.sh`](cleanup-v0.sh).

```bash
# Dry-run first — lists what would be deleted, makes no changes.
bash infra/terraform/cleanup-v0.sh

# When you're satisfied:
bash infra/terraform/cleanup-v0.sh --apply
```

The script is idempotent (skips already-deleted resources) and confirms
before each destructive action. After running, update
[`docs/operations/aws-resource-inventory.md`](../../docs/operations/aws-resource-inventory.md)
to mark the deleted resources as gone.

Not in scope for this script:

- RDS final snapshot `jeromelu-db-pre-lightsail-2026-04-25` — retain until
  2026-05-25, then delete via `aws rds delete-db-snapshot`.
- KMS CMK and Secrets Manager secrets — already in the AWS pending-deletion
  state; will auto-delete on schedule.

## CI workflow

`.github/workflows/terraform.yml` runs on every PR that touches
`infra/terraform/**`. It does:

- `terraform fmt -check -recursive`
- `terraform init`
- `terraform validate`
- `terraform plan`
- Posts plan output as a PR comment

Apply remains manual — run `terraform apply` from your workstation with admin
credentials. Auto-apply on `master` is intentionally not wired up; revisit
once there are multiple operators.

### Setup (one-off after first `terraform apply`)

The `jeromelu-terraform-plan` IAM user is created by Terraform itself. Once
the first apply has created the user:

1. **Create access keys** (console → IAM → Users → `jeromelu-terraform-plan` → Security credentials → Create access key).
2. **Add to GitHub repo secrets** (Settings → Secrets and variables → Actions):
   - `TF_AWS_ACCESS_KEY_ID`
   - `TF_AWS_SECRET_ACCESS_KEY`
3. **Open a no-op PR touching `infra/terraform/`** to confirm the workflow runs and posts a plan comment.
