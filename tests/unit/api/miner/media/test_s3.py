from pathlib import Path

import pytest
from app.miner.media import s3 as media_s3
from botocore.exceptions import ClientError


def _client_error(code: str, status: int) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": "boom"},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        "HeadObject",
    )


class HeadClient:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls = []

    def head_object(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {}


class UploadClient:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls = []

    def upload_file(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error:
            raise self.error


def test_media_object_exists_true(monkeypatch):
    client = HeadClient()
    monkeypatch.setattr(media_s3, "get_s3_client", lambda: client)

    assert media_s3.media_object_exists("youtube/chan/video.m4a") is True
    assert client.calls[0]["Key"] == "youtube/chan/video.m4a"


def test_media_object_exists_false_for_404(monkeypatch):
    client = HeadClient(_client_error("404", 404))
    monkeypatch.setattr(media_s3, "get_s3_client", lambda: client)

    assert media_s3.media_object_exists("missing") is False


def test_media_object_exists_raises_for_non_404_client_error(monkeypatch):
    client = HeadClient(_client_error("AccessDenied", 403))
    monkeypatch.setattr(media_s3, "get_s3_client", lambda: client)

    with pytest.raises(media_s3.MediaStorageError, match="failed to check"):
        media_s3.media_object_exists("blocked")


def test_upload_media_file_wraps_upload_errors(monkeypatch, tmp_path: Path):
    client = UploadClient(RuntimeError("offline"))
    monkeypatch.setattr(media_s3, "get_s3_client", lambda: client)
    file_path = tmp_path / "clip.mp4"
    file_path.write_bytes(b"video")

    with pytest.raises(media_s3.MediaStorageError, match="failed to upload"):
        media_s3.upload_media_file(
            "youtube/chan/video.video.mp4",
            str(file_path),
            content_type="video/mp4",
        )


def test_upload_media_file_sets_content_type(monkeypatch, tmp_path: Path):
    client = UploadClient()
    monkeypatch.setattr(media_s3, "get_s3_client", lambda: client)
    file_path = tmp_path / "audio.m4a"
    file_path.write_bytes(b"audio")

    media_s3.upload_media_file(
        "youtube/chan/video.m4a",
        str(file_path),
        content_type="audio/mp4",
    )

    args, kwargs = client.calls[0]
    assert args[0] == str(file_path)
    assert args[2] == "youtube/chan/video.m4a"
    assert kwargs["ExtraArgs"] == {"ContentType": "audio/mp4"}
