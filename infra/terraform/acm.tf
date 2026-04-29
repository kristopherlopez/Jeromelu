################################################################################
# ACM certificate (CloudFront viewer)
#
# CloudFront viewer certificates must live in us-east-1, so this is referenced
# via the aliased provider. The cert was created and DNS-validated manually
# during V0 setup — we keep it as a data source rather than a resource because:
#
#  - It is shared with the Route 53 zone for validation (no recreation cost).
#  - Terraform managing certificate validation records is fiddly when the cert
#    already exists and is already issued.
#
# If we ever need to manage the cert lifecycle (e.g. add a new SAN), promote
# this from a data source to an `aws_acm_certificate` resource + import block.
#
# The unused ap-southeast-2 cert (originally for the V0 ALB) is handled in
# PR3 (V0 orphan cleanup) — import then destroy.
################################################################################

data "aws_acm_certificate" "cloudfront" {
  provider    = aws.us_east_1
  domain      = var.domain
  statuses    = ["ISSUED"]
  most_recent = true
}
