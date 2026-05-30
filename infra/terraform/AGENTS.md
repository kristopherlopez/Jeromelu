# Terraform Instructions

Read this before editing `infra/terraform/**`.

## Scope

Terraform owns AWS resource definitions and imports. Apply remains an operator action.

## Required Context

- Terraform README: `infra/terraform/README.md`
- IaC docs: `docs/operations/iac-overview.md`, `docs/operations/iac-runbook.md`
- AWS inventory: `docs/operations/aws-resource-inventory.md`
- CI workflow: `.github/workflows/terraform.yml`

## Rules

- New AWS resources go through Terraform. Do not use AWS CLI provisioning as a shortcut.
- Run or document `terraform fmt`, `terraform validate`, and `terraform plan` for infra changes.
- If adopting live resources, use import blocks and reconcile HCL until plan avoids replacement.
- Never commit secret values. SecureString values are ignored by Terraform and rotated out of band.
- If a resource is deliberately unmanaged, document that boundary in the README or runbook.
- Apply is manual from an operator workstation unless the project explicitly changes that policy.
