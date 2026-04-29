terraform {
  backend "s3" {
    bucket         = "jeromelu-tfstate"
    key            = "prod/terraform.tfstate"
    region         = "ap-southeast-2"
    dynamodb_table = "jeromelu-tf-locks"
    encrypt        = true
  }
}
