################################################################################
# Import blocks (Terraform 1.7+ for_each support).
#
# These adopt manually-created AWS resources into Terraform state without
# recreating them. Each block is idempotent — once the resource is in state
# the block is a no-op, so we keep them here as a permanent record of which
# resources started life as click-ops.
#
# Run order:
#   1. terraform init
#   2. terraform plan -generate-config-out=generated.tf  (optional, to compare)
#   3. terraform plan                                    (target: zero diff)
#   4. terraform apply                                   (only after plan is clean)
#
# If plan shows drift, prefer fixing the HCL to match live state over modifying
# the live resource. If the drift is acceptable (e.g. tags being added), apply
# it deliberately.
################################################################################

# ---- S3 ----------------------------------------------------------------------

import {
  to = aws_s3_bucket.raw_transcripts
  id = "jeromelu-raw-transcripts"
}

import {
  to = aws_s3_bucket_versioning.raw_transcripts
  id = "jeromelu-raw-transcripts"
}

import {
  to = aws_s3_bucket_server_side_encryption_configuration.raw_transcripts
  id = "jeromelu-raw-transcripts"
}

import {
  to = aws_s3_bucket_public_access_block.raw_transcripts
  id = "jeromelu-raw-transcripts"
}

import {
  to = aws_s3_bucket.clean_documents
  id = "jeromelu-clean-documents"
}

import {
  to = aws_s3_bucket_server_side_encryption_configuration.clean_documents
  id = "jeromelu-clean-documents"
}

import {
  to = aws_s3_bucket_public_access_block.clean_documents
  id = "jeromelu-clean-documents"
}

import {
  to = aws_s3_bucket.public_assets
  id = "jeromelu-public-assets"
}

import {
  to = aws_s3_bucket_server_side_encryption_configuration.public_assets
  id = "jeromelu-public-assets"
}

import {
  to = aws_s3_bucket_public_access_block.public_assets
  id = "jeromelu-public-assets"
}

# Note: aws_s3_bucket_lifecycle_configuration.public_assets is intentionally
# NOT imported — the lifecycle rule documented in the inventory was never
# actually configured on the live bucket. On first apply, Terraform creates
# the rule from HCL, finally bringing the bucket in line with the documented
# 30-day expiry on `backups/postgres/`.

# ---- ECR ---------------------------------------------------------------------

import {
  for_each = local.ecr_repos
  to       = aws_ecr_repository.this[each.key]
  id       = each.key
}

import {
  for_each = local.ecr_repos
  to       = aws_ecr_lifecycle_policy.this[each.key]
  id       = each.key
}

# ---- SSM ---------------------------------------------------------------------

import {
  for_each = local.ssm_string_params
  to       = aws_ssm_parameter.string[each.key]
  id       = each.key
}

import {
  for_each = local.ssm_secure_params
  to       = aws_ssm_parameter.secure[each.key]
  id       = each.key
}

# ---- IAM ---------------------------------------------------------------------
#
# `jeromelu-cicd` and `jeromelu-instance` are imported (created via console).
# `jeromelu-terraform-plan` is NOT imported — it is created by Terraform on
# the first apply.

import {
  to = aws_iam_user.cicd
  id = "jeromelu-cicd"
}

import {
  to = aws_iam_user_policy.cicd
  id = "jeromelu-cicd:jeromelu-cicd-permissions"
}

import {
  to = aws_iam_user.instance
  id = "jeromelu-instance"
}

import {
  to = aws_iam_user_policy.instance
  id = "jeromelu-instance:jeromelu-instance-permissions"
}

# ---- Route 53 ----------------------------------------------------------------

import {
  to = aws_route53_zone.primary
  id = "Z0304833VPJJKDFO86WO"
}

import {
  to = aws_route53_record.apex
  id = "Z0304833VPJJKDFO86WO_jeromelu.ai_A"
}

import {
  to = aws_route53_record.www
  id = "Z0304833VPJJKDFO86WO_www.jeromelu.ai_A"
}

import {
  to = aws_route53_record.api
  id = "Z0304833VPJJKDFO86WO_api.jeromelu.ai_A"
}

import {
  to = aws_route53_record.origin
  id = "Z0304833VPJJKDFO86WO_origin.jeromelu.ai_A"
}

# ---- CloudFront --------------------------------------------------------------

import {
  to = aws_cloudfront_distribution.main
  id = "E2G6FL11A3JP8F"
}

# ---- Lightsail ---------------------------------------------------------------
#
# Only the instance is imported. The static IP, its attachment, and the
# public-ports resource cannot be imported in AWS provider 5.x; see
# lightsail.tf for how each is handled.

import {
  to = aws_lightsail_instance.jeromelu
  id = "jeromelu"
}
