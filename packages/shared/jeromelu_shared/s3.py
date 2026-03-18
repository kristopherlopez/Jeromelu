import boto3
from botocore.config import Config

from jeromelu_shared.config import settings


def get_s3_client():
    kwargs = {
        "config": Config(signature_version="s3v4"),
    }
    if settings.s3_endpoint:
        kwargs["endpoint_url"] = settings.s3_endpoint
        kwargs["aws_access_key_id"] = settings.s3_access_key
        kwargs["aws_secret_access_key"] = settings.s3_secret_key
    return boto3.client("s3", **kwargs)


def upload_raw(key: str, body: bytes | str) -> None:
    client = get_s3_client()
    if isinstance(body, str):
        body = body.encode("utf-8")
    client.put_object(Bucket=settings.s3_raw_bucket, Key=key, Body=body)


def download_raw(key: str) -> bytes:
    client = get_s3_client()
    resp = client.get_object(Bucket=settings.s3_raw_bucket, Key=key)
    return resp["Body"].read()


def upload_player_data(key: str, body: bytes | str) -> None:
    client = get_s3_client()
    if isinstance(body, str):
        body = body.encode("utf-8")
    client.put_object(Bucket=settings.s3_player_data_bucket, Key=key, Body=body)
