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
    "jeromelu/video-worker",
  ])

  # Subset of ecr_repos that already have a lifecycle policy in AWS — used
  # by imports.tf. video-worker is excluded because it was never given one
  # via click-ops; TF creates it on first apply.
  ecr_repos_with_existing_lifecycle_policy = toset([
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
        description  = "Keep only the last 10 tagged images"
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

  # Live state is MUTABLE (despite the inventory saying tag immutability is
  # enabled). Switching to IMMUTABLE would break `docker push :latest` from
  # the deploy workflow. If we ever want immutable tags, the deploy workflow
  # must drop the `latest` push first.
  name                 = each.key
  image_tag_mutability = "MUTABLE"

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
