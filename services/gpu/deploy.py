"""Deploy or update the Lineup SageMaker Async endpoint (Phase 5.5).

Idempotent — re-running creates the model + endpoint config + endpoint
on first invocation, then updates them on subsequent runs without
downtime (SageMaker rolling update for endpoint config changes).

Usage:
    python -m services.gpu.deploy

Reads from environment / pydantic settings:
    LINEUP_AWS_REGION       (default ap-southeast-2)
    LINEUP_ECR_REPO         (default jeromelu/lineup-gpu)
    LINEUP_ENDPOINT_NAME    (default jeromelu-lineup-async)
    LINEUP_SAGEMAKER_ROLE_ARN  (required — see SETUP.md)
    HUGGINGFACE_API_KEY     (required — passed into container env)
    AWS_ACCOUNT_ID or AWS_PROFILE  (boto3 standard credential chain)
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

from jeromelu_shared.config import settings


INSTANCE_TYPE = "ml.g4dn.xlarge"


def _account_id(region: str) -> str:
    sts = boto3.client("sts", region_name=region)
    return sts.get_caller_identity()["Account"]


def _image_uri(account: str, region: str, repo: str, tag: str = "latest") -> str:
    return f"{account}.dkr.ecr.{region}.amazonaws.com/{repo}:{tag}"


def _ensure_role_arn() -> str:
    if not settings.lineup_sagemaker_role_arn:
        raise SystemExit(
            "LINEUP_SAGEMAKER_ROLE_ARN is empty — see services/gpu/SETUP.md "
            "for one-time IAM role creation."
        )
    return settings.lineup_sagemaker_role_arn


def _model_name(endpoint: str, image_tag: str) -> str:
    """One model per image tag so endpoint config updates roll forward
    cleanly. The endpoint name stays stable; the model behind it changes."""
    return f"{endpoint}-{image_tag}"


def _config_name(endpoint: str, image_tag: str) -> str:
    return f"{endpoint}-cfg-{image_tag}"


def _create_or_update_model(sm, *, model_name: str, image: str, role: str, hf_token: str) -> None:
    try:
        sm.describe_model(ModelName=model_name)
        print(f"[deploy] model {model_name} already exists — leaving as-is")
        return
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ValidationException":
            raise

    print(f"[deploy] creating model {model_name}")
    sm.create_model(
        ModelName=model_name,
        ExecutionRoleArn=role,
        PrimaryContainer={
            "Image": image,
            "Environment": {
                "HUGGINGFACE_API_KEY": hf_token,
                "S3_ENDPOINT": "",  # use real AWS, not MinIO
                # Pin S3 region so boto3 inside the container talks to the
                # right endpoint without a hop through us-east-1.
                "AWS_DEFAULT_REGION": settings.lineup_aws_region,
            },
        },
    )


def _create_or_update_endpoint_config(
    sm, *, config_name: str, model_name: str, region: str,
) -> None:
    try:
        sm.describe_endpoint_config(EndpointConfigName=config_name)
        print(f"[deploy] endpoint config {config_name} already exists")
        return
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ValidationException":
            raise

    print(f"[deploy] creating endpoint config {config_name}")
    sm.create_endpoint_config(
        EndpointConfigName=config_name,
        ProductionVariants=[
            {
                "VariantName": "AllTraffic",
                "ModelName": model_name,
                "InstanceType": INSTANCE_TYPE,
                "InitialInstanceCount": 1,
            },
        ],
        AsyncInferenceConfig={
            "OutputConfig": {
                "S3OutputPath": (
                    f"s3://{settings.s3_raw_bucket}/{settings.lineup_output_prefix}/"
                ),
            },
            "ClientConfig": {
                # One source at a time per endpoint instance — confirmed
                # decision (5).
                "MaxConcurrentInvocationsPerInstance": 1,
            },
        },
    )


def _create_or_update_endpoint(sm, *, endpoint: str, config_name: str) -> None:
    try:
        sm.describe_endpoint(EndpointName=endpoint)
        print(f"[deploy] updating endpoint {endpoint} → config {config_name}")
        sm.update_endpoint(EndpointName=endpoint, EndpointConfigName=config_name)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ValidationException":
            raise
        print(f"[deploy] creating endpoint {endpoint}")
        sm.create_endpoint(EndpointName=endpoint, EndpointConfigName=config_name)


def _wait_in_service(sm, endpoint: str, timeout: int = 1800) -> None:
    print(f"[deploy] waiting for endpoint {endpoint} to be InService …")
    deadline = time.time() + timeout
    while time.time() < deadline:
        info = sm.describe_endpoint(EndpointName=endpoint)
        status = info["EndpointStatus"]
        print(f"  status={status}")
        if status == "InService":
            return
        if status in ("Failed", "OutOfService"):
            reason = info.get("FailureReason", "")
            raise SystemExit(f"endpoint failed: {status} — {reason}")
        time.sleep(15)
    raise SystemExit(f"timed out waiting for endpoint after {timeout}s")


def main(argv: list[str]) -> int:
    image_tag = argv[1] if len(argv) > 1 else os.environ.get("LINEUP_IMAGE_TAG", "latest")

    region = settings.lineup_aws_region
    repo = settings.lineup_ecr_repo
    endpoint = settings.lineup_endpoint_name
    role = _ensure_role_arn()
    hf_token = settings.huggingface_api_key
    if not hf_token:
        raise SystemExit("HUGGINGFACE_API_KEY must be set in .env")

    account = _account_id(region)
    image = _image_uri(account, region, repo, tag=image_tag)
    model_name = _model_name(endpoint, image_tag)
    config_name = _config_name(endpoint, image_tag)

    print(f"[deploy] region={region}  image={image}")
    sm = boto3.client("sagemaker", region_name=region)

    _create_or_update_model(
        sm, model_name=model_name, image=image, role=role, hf_token=hf_token,
    )
    _create_or_update_endpoint_config(
        sm, config_name=config_name, model_name=model_name, region=region,
    )
    _create_or_update_endpoint(sm, endpoint=endpoint, config_name=config_name)
    _wait_in_service(sm, endpoint)

    print(f"[deploy] OK — endpoint={endpoint} model={model_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
