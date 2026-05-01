---
tags: [area/operations]
---

# IaC Runbook

Operational checklist for executing the IaC migration and for day-2
maintenance afterwards. The narrative behind these steps lives in
[`iac-migration-plan.md`](iac-migration-plan.md); the architectural
decisions in [`iac-overview.md`](iac-overview.md).

If you only read one section, read [Pre-flight](#pre-flight) — most
migration mistakes are caught there.

## Prerequisites

- AWS CLI v2, logged in to account `111424988703` with admin or equivalent
  permissions for the migration itself. Run `aws sts get-caller-identity`
  to confirm.
- Terraform `>= 1.7.0` (for `for_each` in `import` blocks).
  Check with `terraform version`.
- Repo cloned at a clean working tree on `master`.
- `bash` (Git Bash on Windows is fine).

## Pre-flight

Two HCL blocks are reconstructed from documentation and may not match live
state byte-for-byte. Verify before *any* plan, including the very first
one.

### 1. SSM parameter list

Confirm the live param list matches `infra/terraform/ssm.tf`:

```bash
aws ssm describe-parameters \
  --query 'Parameters[?starts_with(Name, `/jeromelu/`)].Name' \
  --output text
```

If the live list contains parameters that aren't in `ssm.tf`, add them
before the first plan. Notably, `/jeromelu/anthropic-api-key` may exist
(per recent commits) without being in the inventory doc.

If `ssm.tf` lists parameters that aren't live, remove them — Terraform
would otherwise create empty placeholders.

### 2. IAM policy documents

Compare live policies against the HCL:

```bash
aws iam get-user-policy \
  --user-name jeromelu-cicd \
  --policy-name jeromelu-cicd-permissions \
  --query PolicyDocument

aws iam get-user-policy \
  --user-name jeromelu-instance \
  --policy-name jeromelu-instance-permissions \
  --query PolicyDocument
```

If the live policy is **broader** than what `iam.tf` reconstructs, paste
the live JSON into the matching `data "aws_iam_policy_document"` block
before applying. **Narrowing a live policy via `terraform apply` is the
single most likely way to break Jeromelu mid-migration.**

### 3. CloudFront live config (optional but recommended)

```bash
aws cloudfront get-distribution-config --id E2G6FL11A3JP8F \
  > /tmp/cf-live.json
```

Skim for: aliases, origins, cache behaviors, viewer cert ARN, web ACL ID.
Compare against `cloudfront.tf`. The `web_acl_id` is in `ignore_changes`
deliberately — record the value but don't add it to HCL unless you intend
to manage it.

## Execution

### Phase 1 — Bootstrap state backend (one-off)

Idempotent. Re-running is safe.

```bash
bash infra/terraform/bootstrap/bootstrap.sh
```

Verifies the AWS account, then creates the `jeromelu-tfstate` S3 bucket
(versioned, SSE-S3, public access blocked). Locking uses the S3-native
lockfile feature (`use_lockfile = true` in `backend.tf`); no DynamoDB
table is needed.

### Phase 2 — First Terraform run

```bash
cd infra/terraform
terraform init
terraform plan
```

**Expected plan output:**

- Many `import { ... }` blocks resolve to "imported" lines.
- Tag additions (`Project`, `ManagedBy`, `Repo`) on every resource — those
  come from `default_tags`.
- One `+ resource "aws_iam_user" "terraform_plan"` (this user is created,
  not imported).
- One `+ resource "aws_iam_user_policy_attachment" "terraform_plan_readonly"`.

**Stop and investigate if:**

- Anything is marked `~/+` (replacement).
- An IAM policy diff shows actions removed.
- CloudFront wants to recreate.
- A CloudFront alias, origin, or viewer cert is changing.

If you see a replacement you don't intend, edit HCL to match live state
before proceeding. Use
`terraform plan -generate-config-out=generated.tf` if you want Terraform's
own view of the live resource as a starting point.

### Phase 3 — Apply

When plan is clean:

```bash
terraform apply
```

Terraform will:

1. Import each resource into state.
2. Create `jeromelu-terraform-plan` user + policy attachment.
3. Add tags where they were missing.

This first apply touches CloudFront only if there's a tag diff there. Even
that is fast (tags don't trigger a full distribution deployment).

### Phase 4 — Wire up CI

After Phase 3 succeeds, `jeromelu-terraform-plan` exists. Now create its
access key and plug into GitHub:

1. **Console:** IAM → Users → `jeromelu-terraform-plan` → Security
   credentials → Create access key. Choose "Other" as the use case.
2. **GitHub:** repo Settings → Secrets and variables → Actions → New
   repository secret. Add both:
   - `TF_AWS_ACCESS_KEY_ID`
   - `TF_AWS_SECRET_ACCESS_KEY`
3. **Verify:** open a no-op PR touching any file in `infra/terraform/`
   (e.g. add a comment to `README.md`). The Terraform workflow should run
   and post a plan comment within ~3 minutes.

### Phase 5 — V0 cleanup

Independent of Phases 1–4. Run any time after the V1 architecture has been
soaking (which it has, since 2026-04-25):

```bash
# Dry-run first — lists what would be deleted, no changes made
bash infra/terraform/cleanup-v0.sh

# When you're satisfied:
bash infra/terraform/cleanup-v0.sh --apply
```

The script confirms before each destructive action. After it completes,
update [`aws-resource-inventory.md`](aws-resource-inventory.md) to mark
the deleted resources as gone.

Out of scope for the script (handle separately when due):

- RDS final snapshot `jeromelu-db-pre-lightsail-2026-04-25` — retain until
  2026-05-25, then `aws rds delete-db-snapshot`.

## Troubleshooting

### "Plan wants to replace the CloudFront distribution"

**Do not apply.** A CloudFront replacement is ~30 minutes of downtime plus
a new distribution ID, breaking the Route 53 alias and possibly forcing
ACM cert revalidation.

Diagnose with:

```bash
aws cloudfront get-distribution-config --id E2G6FL11A3JP8F > /tmp/cf-live.json
```

Compare each top-level field with `cloudfront.tf`. The most common
culprits are:

- `origin.custom_origin_config.origin_protocol_policy` differs (live is
  `http-only`, HCL drifted).
- `aliases` differs (e.g. `www.jeromelu.ai` was added live but not in HCL).
- `viewer_certificate.acm_certificate_arn` mismatch.

Edit HCL to match live, re-plan.

### "Plan shows a narrowed IAM policy"

Same root cause: HCL doesn't match live. Run the pre-flight commands
again, paste the live JSON into the relevant `aws_iam_policy_document`
block.

If the broader live policy is genuinely wrong (over-privileged), do the
narrowing as a deliberate, separate PR — not as part of the migration.

### "Lightsail static IP attachment fails to import"

Some provider versions are picky. Try a manual import as a one-off:

```bash
cd infra/terraform
terraform import aws_lightsail_static_ip_attachment.jeromelu jeromelu-ip
```

If that also fails, check the provider version in `versions.tf` and
upgrade to the latest `5.x`.

### "Error: Error locking state" / S3 lockfile

The backend uses S3-native locking (`use_lockfile = true`). The lock is a
single object at `prod/terraform.tfstate.tflock` in `jeromelu-tfstate`. If a
previous run crashed and left it behind:

```bash
aws s3 ls s3://jeromelu-tfstate/prod/terraform.tfstate.tflock
aws s3 cp s3://jeromelu-tfstate/prod/terraform.tfstate.tflock - | head
# If you're certain no one else is running terraform:
aws s3 rm s3://jeromelu-tfstate/prod/terraform.tfstate.tflock
```

Or use `terraform force-unlock <LOCK_ID>` (the LOCK_ID is in the error
message). Only force-unlock when you are certain no concurrent run exists.

### "Plan output too large for PR comment"

The CI workflow truncates output longer than 60k characters and shows the
last chunk. The full plan is in the workflow logs (Actions tab → workflow
run → `terraform plan` step).

If plan output is regularly hitting this limit, the change set is probably
too big — split the PR.

### "I broke something live; how do I roll back state?"

The state bucket has versioning enabled.

1. List versions: `aws s3api list-object-versions --bucket jeromelu-tfstate --prefix prod/terraform.tfstate`
2. Pick a known-good `VersionId`.
3. Copy that version back over the current key:
   ```bash
   aws s3api copy-object \
     --bucket jeromelu-tfstate \
     --copy-source 'jeromelu-tfstate/prod/terraform.tfstate?versionId=<VERSION_ID>' \
     --key prod/terraform.tfstate
   ```
4. `terraform refresh` to align with whatever live state currently is.

State rollback **does not roll back live AWS resources**. If apply did
something destructive, rolling back state just changes Terraform's view —
you still need to manually fix AWS.

## Day-2 maintenance

### Adding a new AWS resource

1. Add the HCL to the appropriate `*.tf` file (or create a new one for
   a new service).
2. Open a feature branch.
3. `terraform plan` locally to confirm intent.
4. Open a PR. CI runs plan and posts the comment.
5. Merge.
6. From your workstation, on `master`: `terraform apply`.
7. Update [`aws-resource-inventory.md`](aws-resource-inventory.md) if the
   resource warrants an entry.

### Adopting a manually-created resource

If you (or someone) created a resource via the console and want to bring
it into Terraform:

1. Write the HCL block, mirroring live config as best you can. For a
   first-pass, run:
   ```bash
   terraform plan -generate-config-out=generated.tf
   ```
   after adding an `import` block — this scaffolds the resource from live
   state. Diff `generated.tf` against your hand-written version, take the
   parts you missed, then delete `generated.tf` (it's in `.gitignore`).
2. Add the `import { to = ..., id = ... }` block to `imports.tf`.
3. `terraform plan` until the diff is zero or only acceptable changes.
4. `terraform apply`.

### Rotating a secret

SecureString values are managed out-of-band:

```bash
aws ssm put-parameter \
  --name /jeromelu/openai-api-key \
  --type SecureString \
  --value "sk-..." \
  --overwrite
```

`terraform plan` will not flag this. After rotation, update wherever the
secret is consumed:

- Lightsail box: `/opt/jeromelu/.env` (then restart the affected container).
- GitHub Actions secrets: Settings → Secrets → update the value.

### Rotating an IAM access key

Access keys are also out-of-band. Standard rotation:

1. Console → IAM → Users → `<user>` → Security credentials → Create access key.
2. Update consumer (`/opt/jeromelu/.env` for `jeromelu-instance`; GitHub
   secrets for `jeromelu-cicd` or `jeromelu-terraform-plan`).
3. Test the consumer.
4. Deactivate the old key. Wait 24h.
5. Delete the old key.

`terraform plan` is not involved.

### Operator IP changed

Edit `prod.auto.tfvars` (or `variables.tf` default) to set
`operator_ssh_cidr = "x.x.x.x/32"`. Apply.

```bash
cd infra/terraform
terraform apply
```

This updates the Lightsail firewall in seconds.

### "What's actually in IaC?"

Status table is in
[`infra/terraform/README.md`](../../infra/terraform/README.md#status).
For an authoritative answer, `terraform state list` in `infra/terraform/`.

### Periodic drift check

When the project starts having multiple operators, schedule a weekly
`terraform plan` to detect out-of-band changes. Today, with one operator
and infrequent infra changes, manual `terraform plan` before any apply is
sufficient. Track this as a future item, not a present need.
