#!/usr/bin/env bash
# V0 orphan teardown.
#
# Deletes resources from the original ECS/Fargate architecture that were
# decommissioned in spirit on 2026-04-25 (see
# docs/operations/aws-resource-inventory.md Phase 11.8) but never actually
# removed from the account. Doing this now reduces console noise and
# eliminates "what is this for?" questions from future operators.
#
# Targets (all in ap-southeast-2 unless noted):
#
#   1. ECR worker repositories (4): jeromelu/worker-{ingestion,extraction,decision,publishing}
#   2. VPC vpc-0dfbe4160b1d408ef + all its children:
#        - VPC endpoints (S3 gateway endpoint vpce-0cf3ea6da9fdf4300)
#        - 4 V0 security groups (jeromelu-{alb,app,worker,db}-sg)
#        - subnets (4)
#        - non-default route tables
#        - internet gateway igw-0927b99dac1731a77
#   3. ACM certificate arn:aws:acm:ap-southeast-2:111424988703:certificate/f270cfe9-d799-4d99-b9c1-1bb93b79fa11
#
# NOT targeted (handled separately):
#   - RDS final snapshot jeromelu-db-pre-lightsail-2026-04-25 (retain until 2026-05-25)
#   - KMS CMK and Secrets Manager secrets (already in pending-deletion state, will auto-delete)
#
# Usage:
#   ./cleanup-v0.sh           # dry-run, prints what would be deleted
#   ./cleanup-v0.sh --apply   # actually delete, with per-step confirmation
#
# This is idempotent — re-running after partial success skips already-deleted
# resources cleanly.

set -euo pipefail

REGION="ap-southeast-2"
ACCOUNT_ID="111424988703"
VPC_ID="vpc-0dfbe4160b1d408ef"
ACM_CERT_ARN="arn:aws:acm:ap-southeast-2:111424988703:certificate/f270cfe9-d799-4d99-b9c1-1bb93b79fa11"
ECR_WORKER_REPOS=(
  "jeromelu/worker-ingestion"
  "jeromelu/worker-extraction"
  "jeromelu/worker-decision"
  "jeromelu/worker-publishing"
)

DRY_RUN=true
if [ "${1:-}" = "--apply" ]; then
  DRY_RUN=false
fi

CALLER_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
if [ "$CALLER_ACCOUNT" != "$ACCOUNT_ID" ]; then
  echo "ERROR: AWS credentials are for account $CALLER_ACCOUNT, expected $ACCOUNT_ID." >&2
  exit 1
fi

confirm() {
  if $DRY_RUN; then
    echo "  [dry-run] would: $1"
    return 1
  fi
  read -r -p "  $1 [y/N] " yn
  case "$yn" in
    [Yy]*) return 0 ;;
    *) echo "  -> skipped"; return 1 ;;
  esac
}

heading() {
  echo
  echo "=== $1 ==="
}

# ---- 1. ECR worker repositories ----------------------------------------------

heading "ECR worker repositories"

for repo in "${ECR_WORKER_REPOS[@]}"; do
  if aws ecr describe-repositories \
       --repository-names "$repo" \
       --region "$REGION" >/dev/null 2>&1; then
    if confirm "delete ECR repo $repo (force, includes all images)?"; then
      aws ecr delete-repository \
        --repository-name "$repo" \
        --force \
        --region "$REGION"
      echo "  -> deleted"
    fi
  else
    echo "  [skip] $repo already gone"
  fi
done

# ---- 2. VPC and its children -------------------------------------------------

heading "VPC $VPC_ID and dependencies"

if aws ec2 describe-vpcs --vpc-ids "$VPC_ID" --region "$REGION" >/dev/null 2>&1; then

  # 2a. VPC endpoints
  echo "-- VPC endpoints"
  ENDPOINT_IDS=$(aws ec2 describe-vpc-endpoints \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --region "$REGION" \
    --query 'VpcEndpoints[].VpcEndpointId' \
    --output text)
  if [ -n "$ENDPOINT_IDS" ]; then
    if confirm "delete VPC endpoints: $ENDPOINT_IDS?"; then
      # delete-vpc-endpoints accepts a space-separated list
      aws ec2 delete-vpc-endpoints \
        --vpc-endpoint-ids $ENDPOINT_IDS \
        --region "$REGION" >/dev/null
      echo "  -> deleted"
    fi
  else
    echo "  [skip] no VPC endpoints"
  fi

  # 2b. Security groups (non-default).
  # Two passes: revoke ingress first (cross-SG references make deletion fail
  # otherwise), then delete.
  echo "-- Security groups (non-default)"
  SG_IDS=$(aws ec2 describe-security-groups \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --region "$REGION" \
    --query 'SecurityGroups[?GroupName!=`default`].GroupId' \
    --output text)
  if [ -n "$SG_IDS" ]; then
    if confirm "revoke all ingress rules on SGs: $SG_IDS?"; then
      for sg in $SG_IDS; do
        RULES=$(aws ec2 describe-security-group-rules \
          --filters "Name=group-id,Values=$sg" \
          --region "$REGION" \
          --query 'SecurityGroupRules[?!IsEgress].SecurityGroupRuleId' \
          --output text)
        if [ -n "$RULES" ]; then
          aws ec2 revoke-security-group-ingress \
            --group-id "$sg" \
            --security-group-rule-ids $RULES \
            --region "$REGION" >/dev/null || true
        fi
      done
      echo "  -> revoked"
    fi

    for sg in $SG_IDS; do
      if confirm "delete SG $sg?"; then
        aws ec2 delete-security-group --group-id "$sg" --region "$REGION"
        echo "  -> deleted $sg"
      fi
    done
  else
    echo "  [skip] only default SG remains"
  fi

  # 2c. Subnets
  echo "-- Subnets"
  SUBNET_IDS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --region "$REGION" \
    --query 'Subnets[].SubnetId' \
    --output text)
  if [ -n "$SUBNET_IDS" ]; then
    for subnet in $SUBNET_IDS; do
      if confirm "delete subnet $subnet?"; then
        aws ec2 delete-subnet --subnet-id "$subnet" --region "$REGION"
        echo "  -> deleted"
      fi
    done
  else
    echo "  [skip] no subnets"
  fi

  # 2d. Non-default (non-main) route tables
  echo "-- Route tables (non-main)"
  RT_IDS=$(aws ec2 describe-route-tables \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --region "$REGION" \
    --query 'RouteTables[?!(Associations[?Main==`true`])].RouteTableId' \
    --output text)
  if [ -n "$RT_IDS" ]; then
    for rt in $RT_IDS; do
      if confirm "delete route table $rt?"; then
        aws ec2 delete-route-table --route-table-id "$rt" --region "$REGION"
        echo "  -> deleted"
      fi
    done
  else
    echo "  [skip] only main route table remains"
  fi

  # 2e. Internet gateway
  echo "-- Internet gateway"
  IGW_IDS=$(aws ec2 describe-internet-gateways \
    --filters "Name=attachment.vpc-id,Values=$VPC_ID" \
    --region "$REGION" \
    --query 'InternetGateways[].InternetGatewayId' \
    --output text)
  if [ -n "$IGW_IDS" ]; then
    for igw in $IGW_IDS; do
      if confirm "detach + delete IGW $igw?"; then
        aws ec2 detach-internet-gateway \
          --internet-gateway-id "$igw" \
          --vpc-id "$VPC_ID" \
          --region "$REGION"
        aws ec2 delete-internet-gateway \
          --internet-gateway-id "$igw" \
          --region "$REGION"
        echo "  -> deleted"
      fi
    done
  else
    echo "  [skip] no IGW attached"
  fi

  # 2f. The VPC itself
  echo "-- VPC"
  if confirm "delete VPC $VPC_ID?"; then
    aws ec2 delete-vpc --vpc-id "$VPC_ID" --region "$REGION"
    echo "  -> deleted"
  fi
else
  echo "  [skip] VPC $VPC_ID already gone"
fi

# ---- 3. ACM certificate (V0 ALB) --------------------------------------------

heading "ACM certificate (ap-southeast-2)"

if aws acm describe-certificate \
     --certificate-arn "$ACM_CERT_ARN" \
     --region "$REGION" >/dev/null 2>&1; then
  IN_USE_BY=$(aws acm describe-certificate \
    --certificate-arn "$ACM_CERT_ARN" \
    --region "$REGION" \
    --query 'Certificate.InUseBy' \
    --output text)
  if [ -n "$IN_USE_BY" ] && [ "$IN_USE_BY" != "None" ]; then
    echo "  WARNING: certificate is still attached to: $IN_USE_BY"
    echo "           refusing to delete; investigate first."
  else
    if confirm "delete ACM cert $ACM_CERT_ARN?"; then
      aws acm delete-certificate \
        --certificate-arn "$ACM_CERT_ARN" \
        --region "$REGION"
      echo "  -> deleted"
    fi
  fi
else
  echo "  [skip] cert already gone"
fi

# ---- Done -------------------------------------------------------------------

echo
if $DRY_RUN; then
  echo "Dry run complete. Re-run with --apply to actually delete."
else
  echo "Cleanup complete. Update docs/operations/aws-resource-inventory.md to reflect deletions."
fi
