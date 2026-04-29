terraform {
  backend "s3" {
    bucket       = "jeromelu-tfstate"
    key          = "prod/terraform.tfstate"
    region       = "ap-southeast-2"
    encrypt      = true
    use_lockfile = true # native S3 lockfile (Terraform 1.10+); replaces dynamodb_table
  }
}
