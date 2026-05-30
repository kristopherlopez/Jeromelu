from types import SimpleNamespace

import pytest
from app.miner.media import audio, persistent_video
from youtube_utils.exceptions import DownloadError


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.refreshes = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, _source):
        self.refreshes += 1


def _source():
    return SimpleNamespace(
        source_id="source-1",
        source_type="youtube",
        canonical_url="https://youtu.be/dQw4w9WgXcQ",
        channel_id="channel-1",
        channel=SimpleNamespace(external_id="UCabc123"),
        audio_s3_key=None,
        video_s3_key=None,
        ingestion_status="pending",
    )


def test_acquire_audio_is_idempotent_when_object_exists(monkeypatch):
    source = _source()
    session = FakeSession()
    monkeypatch.setattr(audio, "media_object_exists", lambda _key: True)
    monkeypatch.setattr(
        audio,
        "download_audio",
        lambda *args, **kwargs: pytest.fail("download should not run"),
    )

    result = audio.acquire_audio(session, source)

    assert result.audio_s3_key == "youtube/UCabc123/dQw4w9WgXcQ.m4a"
    assert result.bytes_uploaded is None
    assert source.audio_s3_key == result.audio_s3_key
    assert source.ingestion_status == "collected"
    assert session.commits == 1


def test_acquire_audio_marks_source_failed_on_download_error(monkeypatch):
    source = _source()
    session = FakeSession()
    monkeypatch.setattr(audio, "media_object_exists", lambda _key: False)

    def raise_download_error(*_args, **_kwargs):
        raise DownloadError("blocked")

    monkeypatch.setattr(audio, "download_audio", raise_download_error)

    with pytest.raises(audio.AudioError, match="yt-dlp download failed"):
        audio.acquire_audio(session, source)

    assert source.ingestion_status == "failed"
    assert session.rollbacks == 1
    assert session.refreshes == 1
    assert session.commits == 1


def test_acquire_persistent_video_is_idempotent_when_object_exists(monkeypatch):
    source = _source()
    session = FakeSession()
    monkeypatch.setattr(persistent_video, "media_object_exists", lambda _key: True)
    monkeypatch.setattr(
        persistent_video,
        "_yt_dlp_low_res_video",
        lambda *args, **kwargs: pytest.fail("download should not run"),
    )

    result = persistent_video.acquire_persistent_video(session, source)

    assert result.video_s3_key == "youtube/UCabc123/dQw4w9WgXcQ.video.mp4"
    assert result.bytes_uploaded is None
    assert source.video_s3_key == result.video_s3_key
    assert session.commits == 1
