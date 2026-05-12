################################################################################
# SES — daily cost report email
#
# Carries the once-a-day spend + resource inventory email from
# reports@jeromelu.ai to kristopher.lopez@gmail.com. Composed by
# scripts/cost_report.py, dispatched by .github/workflows/cost-report.yml.
#
# SES sandbox mode is sufficient: one email/day to one verified recipient
# is comfortably inside the 200 msg/day sandbox cap. Leaving sandbox would
# require an AWS support ticket — not needed at this volume.
#
# Verification:
#   - Domain identity (jeromelu.ai) — DKIM via three Route53 CNAMEs. Auto-
#     verifies once DNS propagates (~5-15 min after apply). Terraform's
#     `aws_ses_domain_identity_verification` blocks apply until SES
#     confirms verification.
#   - Recipient (kristopher.lopez@gmail.com) — `aws_ses_email_identity`
#     triggers AWS to send a verification link to that inbox. Click the
#     link once; identity stays verified forever. Until clicked, SendEmail
#     fails with "Email address is not verified".
################################################################################

# ---- Sender: verified domain identity --------------------------------------

resource "aws_ses_domain_identity" "jeromelu" {
  domain = var.domain
}

resource "aws_ses_domain_dkim" "jeromelu" {
  domain = aws_ses_domain_identity.jeromelu.domain
}

resource "aws_route53_record" "ses_dkim" {
  count = 3

  zone_id = aws_route53_zone.primary.zone_id
  name    = "${aws_ses_domain_dkim.jeromelu.dkim_tokens[count.index]}._domainkey.${var.domain}"
  type    = "CNAME"
  ttl     = 600
  records = ["${aws_ses_domain_dkim.jeromelu.dkim_tokens[count.index]}.dkim.amazonses.com"]
}

resource "aws_ses_domain_identity_verification" "jeromelu" {
  domain     = aws_ses_domain_identity.jeromelu.domain
  depends_on = [aws_route53_record.ses_dkim]
}

# ---- Recipient: verified email identity (sandbox mode requirement) ---------

resource "aws_ses_email_identity" "kris" {
  email = "kristopher.lopez@gmail.com"
}
