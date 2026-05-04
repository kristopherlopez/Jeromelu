#!/usr/bin/env bash
# Build the Lineup GPU container and push to ECR (Phase 5.5).
#
# Reads from environment / .env via pydantic settings:
#   LINEUP_AWS_REGION      (default ap-southeast-2)
#   LINEUP_ECR_REPO        (default jeromelu/lineup-gpu)
#   HUGGINGFACE_API_KEY    (required — passed via Buildkit --secret so
#                           it doesn't land in image layers)
#
# Optional first arg: image tag (default `latest`). Bump when you ship
# new container code so SageMaker rolls forward; `latest` is fine for
# dev iteration (forces re-pull each deploy).
#
# Usage:
#   bash services/gpu/build_and_push.sh             # tag latest
#   bash services/gpu/build_and_push.sh v2          # tag v2

set -euo pipefail

REGION="${LINEUP_AWS_REGION:-ap-southeast-2}"
REPO="${LINEUP_ECR_REPO:-jeromelu/lineup-gpu}"
TAG="${1:-latest}"

if [ -z "${HUGGINGFACE_API_KEY:-}" ]; then
    echo "ERROR: HUGGINGFACE_API_KEY must be set (export it or source .env)"
    exit 2
fi

ACCOUNT=$(aws sts get-caller-identity --query Account --output text --region "$REGION")
IMAGE="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:$TAG"
SAGEMAKER_BASE_ACCOUNT="763104351884"
BASE_IMAGE="$SAGEMAKER_BASE_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/pytorch-inference:2.4.0-gpu-py311"

echo "[build] target  = $IMAGE"
echo "[build] base    = $BASE_IMAGE"
echo

echo "[build] login to SageMaker DLC ECR (for base-image pull)…"
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$SAGEMAKER_BASE_ACCOUNT.dkr.ecr.$REGION.amazonaws.com"

echo "[build] login to project ECR (for push)…"
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"

echo "[build] docker build (BuildKit + secret)…"
DOCKER_BUILDKIT=1 docker build \
    --secret id=hf_token,env=HUGGINGFACE_API_KEY \
    --build-arg SAGEMAKER_BASE="$BASE_IMAGE" \
    -t "$IMAGE" \
    -f services/gpu/Dockerfile \
    .

echo "[build] docker push…"
docker push "$IMAGE"

echo
echo "[build] OK — pushed $IMAGE"
echo "Next: make lineup-deploy"
