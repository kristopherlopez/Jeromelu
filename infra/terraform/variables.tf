variable "aws_account_id" {
  description = "AWS account ID. Provider will refuse to operate on any other account."
  type        = string
}

variable "aws_region" {
  description = "Primary AWS region for almost all resources."
  type        = string
  default     = "ap-southeast-2"
}

variable "project" {
  description = "Short project identifier; used as a name prefix and tag value."
  type        = string
  default     = "jeromelu"
}

variable "domain" {
  description = "Primary domain managed by Route 53."
  type        = string
  default     = "jeromelu.ai"
}

variable "cloudfront_distribution_id" {
  description = "ID of the existing CloudFront distribution adopted by Terraform. Used in IAM policy resource ARNs (the distribution itself is referenced by resource attribute)."
  type        = string
  default     = "E2G6FL11A3JP8F"
}

variable "operator_ssh_cidr" {
  description = "Operator's public CIDR allowed to SSH to the Lightsail instance. Update when operator IP changes."
  type        = string
  default     = "112.213.139.221/32"
}

variable "lightsail_static_ip" {
  description = "Public IP attached to the Lightsail instance. The static IP itself isn't TF-managed (no provider import support); this variable lets DNS records reference it."
  type        = string
  default     = "52.65.91.199"
}
