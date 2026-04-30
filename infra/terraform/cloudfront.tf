################################################################################
# CloudFront distribution
#
# Distribution E2G6FL11A3JP8F sits in front of the apex domain. The origin is
# `origin.jeromelu.ai` (HTTP-only — see "Note on HTTP-only origin protocol" in
# docs/operations/aws-resource-inventory.md Phase 11.6). HTTPS to the user is
# unchanged; only the CloudFront edge → Lightsail hop is plaintext.
#
# Aliases: `jeromelu.ai` only. `www.jeromelu.ai` is missing from aliases by
# design (pre-existing fix item — see inventory Phase 11.5).
#
# Cache + origin request policies are AWS-managed:
#   - CachingDisabled: 4135ea2d-6df8-44a3-9df3-4b5a84be39ad
#   - AllViewer:       216adef6-5c7f-47e4-b989-5492eafa07d3
#
# WAF: enabled via the CloudFront free plan, which auto-creates a Web ACL.
# `web_acl_id` is left out of HCL so that whatever the live distribution has
# attached is preserved on import. If you want to manage it deliberately, set
# the variable `cloudfront_web_acl_id` after the first plan reveals the value.
#
# Best-effort: this block is reconstructed from the inventory + setup guide.
# Run `terraform plan -generate-config-out=cloudfront-generated.tf` if you
# want a from-live-state version to compare against. Reconcile any drift
# *before* applying — CloudFront takes ~10–15 minutes per change to deploy.
################################################################################

locals {
  cf_origin_id = "origin-jeromelu-ai"
}

resource "aws_cloudfront_distribution" "main" {
  enabled         = true
  is_ipv6_enabled = true
  # Note: spelled "Jeromelu" (with E) to match live CloudFront comment.
  # The agent name is "Jaromelu" but the repo and infra use "Jeromelu";
  # changing this triggers a slow distribution-wide deploy for no gain.
  comment             = "Jeromelu public experience"
  default_root_object = ""
  http_version        = "http2"
  price_class         = "PriceClass_All"

  aliases = ["jeromelu.ai"]

  origin {
    origin_id   = local.cf_origin_id
    domain_name = "origin.${var.domain}"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = local.cf_origin_id
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" # CachingDisabled
    origin_request_policy_id = "216adef6-5c7f-47e4-b989-5492eafa07d3" # AllViewer
  }

  viewer_certificate {
    acm_certificate_arn      = data.aws_acm_certificate.cloudfront.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # Free-plan WAF Web ACL is managed out-of-band. Whatever is live on the
  # distribution at import time stays attached.
  lifecycle {
    ignore_changes = [
      web_acl_id,
    ]
  }
}
