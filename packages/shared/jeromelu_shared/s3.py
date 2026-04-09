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
    else:
        kwargs["region_name"] = "ap-southeast-2"
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


def upload_asset(key: str, file_path: str, content_type: str = "video/mp4") -> str:
    """Upload a file to the public assets bucket. Returns the S3 key."""
    client = get_s3_client()
    client.upload_file(
        str(file_path),
        settings.s3_assets_bucket,
        key,
        ExtraArgs={
            "ContentType": content_type,
            "CacheControl": "public, max-age=31536000, immutable",
        },
    )
    return key


def get_asset_url(key: str) -> str:
    """Return the public URL for an asset. Uses CDN in prod, MinIO in dev."""
    if settings.cdn_base_url:
        return f"{settings.cdn_base_url}/{key}"
    return f"{settings.s3_endpoint}/{settings.s3_assets_bucket}/{key}"


def upload_player_data(key: str, body: bytes | str) -> None:
    client = get_s3_client()
    if isinstance(body, str):
        body = body.encode("utf-8")
    client.put_object(Bucket=settings.s3_player_data_bucket, Key=key, Body=body)
