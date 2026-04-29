#!/usr/bin/env bash
# Creates the Terraform state backend resources:
#   - S3 bucket  jeromelu-tfstate     (versioned, SSE-S3, public access blocked)
#   - DynamoDB   jeromelu-tf-locks    (LockID hash key, PAY_PER_REQUEST)
#
# Run this once, before the first `terraform init` in infra/terraform/.
# Idempotent: skips creation if either resource already exists.
#
# Requires AWS credentials with permissions to create S3 buckets and DynamoDB
# tables in account 111424988703.

set -euo pipefail

REGION="ap-southeast-2"
ACCOUNT_ID="111424988703"
BUCKET="jeromelu-tfstate"
TABLE="jeromelu-tf-locks"

CALLER_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
if [ "$CALLER_ACCOUNT" != "$ACCOUNT_ID" ]; then
  echo "ERROR: AWS credentials are for account $CALLER_ACCOUNT, expected $ACCOUNT_ID." >&2
  exit 1
fi

if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "[skip] S3 bucket $BUCKET already exists."
else
  echo "[create] S3 bucket $BUCKET in $REGION..."
  aws s3api create-bucket \
    --bucket "$BUCKET" \
    --region "$REGION" \
    --create-bucket-configuration "LocationConstraint=$REGION"

  aws s3api put-bucket-versioning \
    --bucket "$BUCKET" \
    --versioning-configuration Status=Enabled

  aws s3api put-bucket-encryption \
    --bucket "$BUCKET" \
    --server-side-encryption-configuration \
      '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

  aws s3api put-public-access-block \
    --bucket "$BUCKET" \
    --public-access-block-configuration \
      "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

  aws s3api put-bucket-tagging \
    --bucket "$BUCKET" \
    --tagging 'TagSet=[{Key=Project,Value=jeromelu},{Key=ManagedBy,Value=bootstrap-script},{Key=Purpose,Value=terraform-state}]'
fi

if aws dynamodb describe-table --table-name "$TABLE" --region "$REGION" >/dev/null 2>&1; then
  echo "[skip] DynamoDB table $TABLE already exists."
else
  echo "[create] DynamoDB lock table $TABLE in $REGION..."
  aws dynamodb create-table \
    --table-name "$TABLE" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "$REGION" \
    --tags Key=Project,Value=jeromelu Key=ManagedBy,Value=bootstrap-script Key=Purpose,Value=terraform-locks

  aws dynamodb wait table-exists --table-name "$TABLE" --region "$REGION"
fi

echo
echo "Backend ready. Next:"
echo "  cd infra/terraform"
echo "  terraform init"
echo "  terraform plan"
