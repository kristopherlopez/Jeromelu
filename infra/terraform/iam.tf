################################################################################
# IAM users and inline policies
#
# Two IAM users, both used non-interactively via long-lived access keys:
#
#   jeromelu-cicd      — GitHub Actions (build + push to ECR, invalidate CF)
#   jeromelu-instance  — Lightsail box (pull from ECR, read/write S3, read SSM)
#
# Access keys are NOT managed by Terraform. Rotate them via console / aws CLI
# and update the consuming systems (GitHub Actions secrets, /opt/jeromelu/.env)
# manually.
#
# The policy documents below are reconstructed from the descriptions in
# docs/operations/aws-resource-inventory.md (Phase 11.2). Before applying,
# verify they match live state:
#
#   aws iam get-user-policy --user-name jeromelu-cicd \
#     --policy-name jeromelu-cicd-permissions --query PolicyDocument
#   aws iam get-user-policy --user-name jeromelu-instance \
#     --policy-name jeromelu-instance-permissions --query PolicyDocument
#
# If the live policy is broader than what is here, *do not apply* — paste the
# live JSON in first, then plan again. Narrowing a live policy via apply will
# break whatever consumes it.
################################################################################

# ---- jeromelu-cicd -----------------------------------------------------------

resource "aws_iam_user" "cicd" {
  name = "jeromelu-cicd"
  path = "/"
}

data "aws_iam_policy_document" "cicd" {
  statement {
    sid       = "ECRAuth"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "ECRPushPull"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:ListImages",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = [
      "arn:aws:ecr:${var.aws_region}:${var.aws_account_id}:repository/jeromelu/web",
      "arn:aws:ecr:${var.aws_region}:${var.aws_account_id}:repository/jeromelu/api",
      "arn:aws:ecr:${var.aws_region}:${var.aws_account_id}:repository/jeromelu/video-worker",
    ]
  }

  statement {
    sid    = "CloudFrontInvalidate"
    effect = "Allow"
    actions = [
      "cloudfront:CreateInvalidation",
      "cloudfront:GetInvalidation",
    ]
    resources = [
      "arn:aws:cloudfront::${var.aws_account_id}:distribution/${var.cloudfront_distribution_id}",
    ]
  }
}

resource "aws_iam_user_policy" "cicd" {
  name   = "jeromelu-cicd-permissions"
  user   = aws_iam_user.cicd.name
  policy = data.aws_iam_policy_document.cicd.json
}

# ---- jeromelu-instance -------------------------------------------------------

resource "aws_iam_user" "instance" {
  name = "jeromelu-instance"
  path = "/"
}

data "aws_iam_policy_document" "instance" {
  statement {
    sid       = "ECRPullOnly"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "ECRPullImages"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [
      "arn:aws:ecr:${var.aws_region}:${var.aws_account_id}:repository/jeromelu/web",
      "arn:aws:ecr:${var.aws_region}:${var.aws_account_id}:repository/jeromelu/api",
      "arn:aws:ecr:${var.aws_region}:${var.aws_account_id}:repository/jeromelu/video-worker",
    ]
  }

  statement {
    sid    = "S3App"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      "arn:aws:s3:::jeromelu-raw-transcripts",
      "arn:aws:s3:::jeromelu-raw-transcripts/*",
      "arn:aws:s3:::jeromelu-raw-audio",
      "arn:aws:s3:::jeromelu-raw-audio/*",
      "arn:aws:s3:::jeromelu-clean-documents",
      "arn:aws:s3:::jeromelu-clean-documents/*",
      "arn:aws:s3:::jeromelu-public-assets",
      "arn:aws:s3:::jeromelu-public-assets/*",
    ]
  }

  statement {
    sid    = "SSMReadParams"
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = [
      "arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:parameter/jeromelu/*",
    ]
  }
}

resource "aws_iam_user_policy" "instance" {
  name   = "jeromelu-instance-permissions"
  user   = aws_iam_user.instance.name
  policy = data.aws_iam_policy_document.instance.json
}

# ---- jeromelu-terraform-plan -------------------------------------------------
#
# Used by .github/workflows/terraform.yml to run `terraform plan` on PRs.
# Has the AWS-managed `ReadOnlyAccess` policy attached — broad read across all
# services, no write. This is the ONLY IAM user in this file that Terraform
# creates rather than imports: the user does not exist yet in AWS.
#
# Bootstrapping order:
#   1. `terraform apply` (with admin creds) creates this user.
#   2. Manually create an access key pair for the user via console / aws CLI.
#   3. Store as TF_AWS_ACCESS_KEY_ID + TF_AWS_SECRET_ACCESS_KEY in
#      GitHub repo secrets.
#   4. The workflow at .github/workflows/terraform.yml uses those secrets.
#
# The access key itself is not managed by Terraform (same rule as the other
# users — secrets do not enter state).

resource "aws_iam_user" "terraform_plan" {
  name = "jeromelu-terraform-plan"
  path = "/"
}

resource "aws_iam_user_policy_attachment" "terraform_plan_readonly" {
  user       = aws_iam_user.terraform_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}
