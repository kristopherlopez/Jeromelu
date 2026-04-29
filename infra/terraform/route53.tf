################################################################################
# Route 53 — hosted zone + 4 records
#
# Records (matching docs/operations/aws-resource-inventory.md Phase 11.5):
#   jeromelu.ai          → CloudFront alias        (CDN-fronted apex)
#   www.jeromelu.ai      → CloudFront alias        (returns CF error today —
#                                                   pre-existing fix; still
#                                                   pointed at CF)
#   api.jeromelu.ai      → A → Lightsail static IP (TTL 60, direct, no CF)
#   origin.jeromelu.ai   → A → Lightsail static IP (TTL 60, used by CF origin)
#
# NS and SOA records auto-exist with the zone and are not managed here.
################################################################################

resource "aws_route53_zone" "primary" {
  name    = var.domain
  comment = "Jaromelu primary public zone"
}

resource "aws_route53_record" "apex" {
  zone_id = aws_route53_zone.primary.zone_id
  name    = var.domain
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "www" {
  zone_id = aws_route53_zone.primary.zone_id
  name    = "www.${var.domain}"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "api" {
  zone_id = aws_route53_zone.primary.zone_id
  name    = "api.${var.domain}"
  type    = "A"
  ttl     = 60
  records = [aws_lightsail_static_ip.jeromelu.ip_address]
}

resource "aws_route53_record" "origin" {
  zone_id = aws_route53_zone.primary.zone_id
  name    = "origin.${var.domain}"
  type    = "A"
  ttl     = 60
  records = [aws_lightsail_static_ip.jeromelu.ip_address]
}
