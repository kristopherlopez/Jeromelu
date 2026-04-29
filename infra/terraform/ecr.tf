################################################################################
# ECR repositories
#
# Active repos: jeromelu/web, jeromelu/api.
# Worker repos (jeromelu/worker-*) are slated for deletion — handled out-of-band
# via aws CLI (see infra/terraform/README.md), not imported into Terraform.
#
# All repos: AES256 encryption, immutable tags, scan-on-push, lifecycle rules
# matching the V0 setup (untagged > 14d expire, keep last 10 tagged).
################################################################################

locals {
  ecr_repos = toset([
    "jeromelu/web",
    "jeromelu/api",
  ])

  ecr_lifecycle_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images older than 14 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 14
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep the last 10 tagged images"
        selection = {
          tagStatus      = "tagged"
          tagPatternList = ["*"]
          countType      = "imageCountMoreThan"
          countNumber    = 10
        }
        action = { type = "expire" }
      },
    ]
  })
}

resource "aws_ecr_repository" "this" {
  for_each = local.ecr_repos

  name                 = each.key
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each = aws_ecr_repository.this

  repository = each.value.name
  policy     = local.ecr_lifecycle_policy
}
