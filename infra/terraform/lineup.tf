################################################################################
# Lineup — Phase 5.5 GPU inference (SageMaker Async).
#
# Static infrastructure for the Lineup speaker-identification GPU pipeline:
#
#   - ECR repository for the GPU container image (us-east-1)
#   - S3 staging bucket for SageMaker's internal async invoke I/O (us-east-1)
#   - IAM role the SageMaker endpoint assumes at runtime (global)
#
# Dynamic infrastructure (the SageMaker model, endpoint config, and endpoint
# itself) is managed imperatively by `services/gpu/deploy.py`. Terraform's
# SageMaker resources require destroy+recreate on image-tag rolls, which the
# rolling-update semantics of `update_endpoint` sidestep cleanly.
#
# Region split:
#   - The endpoint runs in us-east-1 (Sydney g4dn / g5 capacity is tight,
#     and us-east-1 has effectively unlimited GPU availability).
#   - The artefact buckets (raw-audio, raw-transcripts) stay in
#     ap-southeast-2 — the cross-region transfer is ~$0.001/source.
#   - This staging bucket is in us-east-1 because SageMaker Async requires
#     its async I/O paths to be in the endpoint's own region.
#
# See services/gpu/SETUP.md for the runbook these resources implement.
################################################################################

# ---- ECR repo (us-east-1) ---------------------------------------------------

resource "aws_ecr_repository" "lineup_gpu" {
  provider = aws.us_east_1

  # MUTABLE because the deploy workflow pushes `:latest`. If we ever switch
  # to immutable-only tags, drop the `:latest` push from build_and_push.sh
  # first.
  name                 = "jeromelu/lineup-gpu"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "lineup_gpu" {
  provider = aws.us_east_1

  repository = aws_ecr_repository.lineup_gpu.name
  policy     = local.ecr_lifecycle_policy
}

# ---- Staging bucket (us-east-1) ---------------------------------------------

resource "aws_s3_bucket" "sagemaker_async" {
  provider = aws.us_east_1

  bucket = "jeromelu-sagemaker-async"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "sagemaker_async" {
  provider = aws.us_east_1

  bucket = aws_s3_bucket.sagemaker_async.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "sagemaker_async" {
  provider = aws.us_east_1

  bucket                  = aws_s3_bucket.sagemaker_async.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Async invoke artefacts are ephemeral — request/response JSONs that mean
# nothing once the consuming run has finished. 7-day expiry keeps the
# bucket from accumulating dust.
resource "aws_s3_bucket_lifecycle_configuration" "sagemaker_async" {
  provider = aws.us_east_1

  bucket = aws_s3_bucket.sagemaker_async.id

  rule {
    id     = "expire-async-io-after-7d"
    status = "Enabled"

    filter {}

    expiration {
      days = 7
    }
  }
}

# ---- IAM role (global; assumed by the SageMaker endpoint) -------------------

data "aws_iam_policy_document" "sagemaker_lineup_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "sagemaker_lineup_inline" {
  statement {
    sid       = "ReadAudio"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.raw_audio.arn}/*"]
  }

  statement {
    sid     = "ReadWriteRawTranscripts"
    effect  = "Allow"
    actions = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = [
      "${aws_s3_bucket.raw_transcripts.arn}/*",
    ]
  }

  statement {
    sid     = "ReadWriteSagemakerStaging"
    effect  = "Allow"
    actions = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = [
      "${aws_s3_bucket.sagemaker_async.arn}/*",
    ]
  }

  statement {
    sid     = "ListBuckets"
    effect  = "Allow"
    actions = ["s3:ListBucket"]
    resources = [
      aws_s3_bucket.raw_audio.arn,
      aws_s3_bucket.raw_transcripts.arn,
      aws_s3_bucket.sagemaker_async.arn,
    ]
  }

  statement {
    sid    = "PullContainerImage"
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "Logs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:CreateLogGroup",
      "logs:DescribeLogStreams",
    ]
    resources = ["arn:aws:logs:*:*:log-group:/aws/sagemaker/*"]
  }
}

resource "aws_iam_role" "sagemaker_lineup" {
  name               = "JeromeluSagemakerLineup"
  assume_role_policy = data.aws_iam_policy_document.sagemaker_lineup_trust.json
  description        = "Run-time role for the Lineup SageMaker Async endpoint (Phase 5.5)."
}

resource "aws_iam_role_policy" "sagemaker_lineup" {
  name   = "JeromeluSagemakerLineupInline"
  role   = aws_iam_role.sagemaker_lineup.id
  policy = data.aws_iam_policy_document.sagemaker_lineup_inline.json
}

# ---- Application Auto Scaling — scale variant to zero ----------------------
#
# The async endpoint (`jeromelu-lineup-async`, managed imperatively by
# `services/gpu/deploy.py`) starts at InitialInstanceCount=1 and stays at 1
# forever unless a scalable target with MinCapacity=0 is attached.
# ml.g5.xlarge in us-east-1 is $1.408/hr — ~$1,014/mo running 24/7 for an
# endpoint invoked 1-2 hrs/day. (Confirmed: May 2026 MTD spend was $218 in
# 7 days against zero registered scalable targets.)
#
# AWS-recommended dual-policy pattern for async + scale-to-zero:
#   - Target-tracking on `ApproximateBacklogSizePerInstance` drives steady-
#     state count while instances >= 1.
#   - Step-scaling triggered by `HasBacklogWithoutCapacity` CloudWatch alarm
#     handles the 0 -> 1 cold start (target-tracking can't, because the
#     backlog-per-instance metric divides by zero when no instance exists).
#
# Cold-start tradeoff: first request after idle takes 1-3 min to fetch the
# image and load the model. ScaleInCooldown=600s keeps the variant warm for
# 10 min after the queue drains so brief gaps within a session don't trigger
# a recycle.

resource "aws_appautoscaling_target" "lineup_async" {
  provider = aws.us_east_1

  service_namespace  = "sagemaker"
  resource_id        = "endpoint/jeromelu-lineup-async/variant/AllTraffic"
  scalable_dimension = "sagemaker:variant:DesiredInstanceCount"

  min_capacity = 0
  max_capacity = 2
}

resource "aws_appautoscaling_policy" "lineup_async_backlog" {
  provider = aws.us_east_1

  name               = "jeromelu-lineup-async-backlog"
  service_namespace  = aws_appautoscaling_target.lineup_async.service_namespace
  resource_id        = aws_appautoscaling_target.lineup_async.resource_id
  scalable_dimension = aws_appautoscaling_target.lineup_async.scalable_dimension
  policy_type        = "TargetTrackingScaling"

  target_tracking_scaling_policy_configuration {
    target_value       = 5.0
    scale_in_cooldown  = 600
    scale_out_cooldown = 60

    customized_metric_specification {
      metric_name = "ApproximateBacklogSizePerInstance"
      namespace   = "AWS/SageMaker"
      statistic   = "Average"

      dimensions {
        name  = "EndpointName"
        value = "jeromelu-lineup-async"
      }
    }
  }
}

resource "aws_appautoscaling_policy" "lineup_async_cold_start" {
  provider = aws.us_east_1

  name               = "jeromelu-lineup-async-cold-start"
  service_namespace  = aws_appautoscaling_target.lineup_async.service_namespace
  resource_id        = aws_appautoscaling_target.lineup_async.resource_id
  scalable_dimension = aws_appautoscaling_target.lineup_async.scalable_dimension
  policy_type        = "StepScaling"

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 300
    metric_aggregation_type = "Maximum"

    step_adjustment {
      metric_interval_lower_bound = 0
      scaling_adjustment          = 1
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "lineup_async_backlog_no_capacity" {
  provider = aws.us_east_1

  alarm_name          = "jeromelu-lineup-async-has-backlog-without-capacity"
  alarm_description   = "Scale lineup-async from 0 to 1 when an invoke arrives at an idle endpoint."
  metric_name         = "HasBacklogWithoutCapacity"
  namespace           = "AWS/SageMaker"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    EndpointName = "jeromelu-lineup-async"
  }

  alarm_actions = [aws_appautoscaling_policy.lineup_async_cold_start.arn]
}
