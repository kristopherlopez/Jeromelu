################################################################################
# SSM Parameter Store
#
# Plain String params hold non-secret config (env, region, bucket names, feature
# flags). Their values live in HCL and are reproducible from this file.
#
# SecureString params hold secrets (DB password, API keys, instance access
# keys). Their values are managed out-of-band; Terraform creates the parameter
# resource with a placeholder value and ignores future drift on `value` so
# rotations done via Console / aws CLI are not reverted by `terraform apply`.
#
# Cross-check before importing:
#   aws ssm describe-parameters --query 'Parameters[?starts_with(Name, `/jeromelu/`)].Name'
# If the live list differs from the locals below, edit before running plan.
################################################################################

locals {
  ssm_string_params = {
    "/jeromelu/env"                       = "production"
    "/jeromelu/region"                    = "ap-southeast-2"
    "/jeromelu/db-name"                   = "jeromelu"
    "/jeromelu/s3-raw-bucket"             = "jeromelu-raw-transcripts"
    "/jeromelu/s3-clean-bucket"           = "jeromelu-clean-documents"
    "/jeromelu/s3-assets-bucket"          = "jeromelu-public-assets"
    "/jeromelu/feature/chat-enabled"      = "true"
    "/jeromelu/feature/contrarian-mode"   = "true"
    "/jeromelu/feature/publishing-paused" = "false"
  }

  ssm_secure_params = toset([
    "/jeromelu/postgres-password",
    "/jeromelu/openai-api-key",
    "/jeromelu/admin-key",
    "/jeromelu/session-secret",
    "/jeromelu/instance-aws-access-key-id",
    "/jeromelu/instance-aws-secret-access-key",
  ])
}

resource "aws_ssm_parameter" "string" {
  for_each = local.ssm_string_params

  name  = each.key
  type  = "String"
  value = each.value
}

resource "aws_ssm_parameter" "secure" {
  for_each = local.ssm_secure_params

  name  = each.key
  type  = "SecureString"
  value = "managed-out-of-band"

  lifecycle {
    ignore_changes = [value]
  }
}
