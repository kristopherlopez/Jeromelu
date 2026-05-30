"""S3 helpers for Miner media objects."""

from __future__ import annotations

from botocore.exceptions import ClientError
from jeromelu_shared.config import settings
from jeromelu_shared.s3 import get_s3_client


class MediaStorageError(Exception):
    """Raised when the media bucket cannot be checked or written."""


def _is_not_found(exc: ClientError) -> bool:
    code = str(exc.response.get("Error", {}).get("Code", ""))
    status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return code in {"404", "NoSuchKey", "NotFound"} or status == 404


def media_object_exists(key: str) -> bool:
    client = get_s3_client()
    try:
        client.head_object(Bucket=settings.s3_audio_bucket, Key=key)
        return True
    except ClientError as exc:
        if _is_not_found(exc):
            return False
        raise MediaStorageError(f"failed to check s3://{settings.s3_audio_bucket}/{key}: {exc}") from exc
    except Exception as exc:
        raise MediaStorageError(f"failed to check s3://{settings.s3_audio_bucket}/{key}: {exc}") from exc


def upload_media_file(key: str, file_path: str, *, content_type: str) -> None:
    client = get_s3_client()
    try:
        client.upload_file(
            file_path,
            settings.s3_audio_bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
    except Exception as exc:
        raise MediaStorageError(f"failed to upload s3://{settings.s3_audio_bucket}/{key}: {exc}") from exc
