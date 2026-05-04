import boto3
from botocore.config import Config

from jeromelu_shared.config import settings


def get_s3_client():
    if settings.s3_endpoint:
        # Local MinIO. Path-style addressing is what MinIO expects.
        return boto3.client(
            "s3",
            config=Config(signature_version="s3v4"),
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
        )
    # Real AWS. Virtual-host addressing is required for SigV4 presigned URLs
    # to hit the regional endpoint directly — without it the URL targets
    # `s3.amazonaws.com` (us-east-1) and a SigV4 signature for ap-southeast-2
    # is rejected with SignatureDoesNotMatch.
    return boto3.client(
        "s3",
        region_name="ap-southeast-2",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
        ),
    )


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


def upload_audio(key: str, file_path: str, content_type: str = "audio/mp4") -> None:
    """Upload a local audio file to the raw-audio bucket."""
    client = get_s3_client()
    client.upload_file(
        str(file_path),
        settings.s3_audio_bucket,
        key,
        ExtraArgs={"ContentType": content_type},
    )


def audio_object_exists(key: str) -> bool:
    client = get_s3_client()
    try:
        client.head_object(Bucket=settings.s3_audio_bucket, Key=key)
        return True
    except Exception:
        return False


def presign_audio(key: str, expires_seconds: int = 900) -> str:
    """Generate a temporary URL for the audio bucket. Used to hand audio
    to Deepgram by URL rather than uploading the bytes inline."""
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_audio_bucket, "Key": key},
        ExpiresIn=expires_seconds,
    )


def presign_video(key: str, expires_seconds: int = 3600) -> str:
    """Generate a temporary URL for a video file in the audio bucket
    (Phase 4 stores low-res mp4s alongside audio). Default TTL is longer
    than ``presign_audio`` because the URL is consumed by a long-lived
    browser ``<video>`` element rather than a one-shot batch transcription."""
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_audio_bucket, "Key": key},
        ExpiresIn=expires_seconds,
    )


def presign_raw(key: str, expires_seconds: int = 3600) -> str:
    """Generate a temporary URL for a raw-transcripts bucket object
    (pyannote JSON, face-track JSON). Used by the review UI to fetch
    artefacts directly from S3 without proxying through the API."""
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_raw_bucket, "Key": key},
        ExpiresIn=expires_seconds,
    )
