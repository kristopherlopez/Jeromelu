from types import SimpleNamespace

import pytest
from app.miner.media.keys import (
    AUDIO_SUFFIX,
    PERSISTENT_VIDEO_SUFFIX,
    youtube_audio_key,
    youtube_media_key,
    youtube_persistent_video_key,
)
from app.miner.media.source import resolve_youtube_media_source


class MediaError(Exception):
    pass


def _source(**overrides):
    data = {
        "source_id": "source-1",
        "source_type": "youtube",
        "canonical_url": "https://youtu.be/dQw4w9WgXcQ",
        "channel_id": "channel-1",
        "channel": SimpleNamespace(external_id="UCabc123"),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_resolves_youtube_source_identity():
    media = resolve_youtube_media_source(_source(), error_cls=MediaError)

    assert media.source_id == "source-1"
    assert media.video_id == "dQw4w9WgXcQ"
    assert media.channel_external_id == "UCabc123"


def test_rejects_non_youtube_source():
    with pytest.raises(MediaError, match="source_type='youtube'"):
        resolve_youtube_media_source(_source(source_type="rss"), error_cls=MediaError)


def test_rejects_source_without_loaded_channel_external_id():
    with pytest.raises(MediaError, match="has no external_id"):
        resolve_youtube_media_source(_source(channel=None), error_cls=MediaError)


def test_builds_media_keys():
    media = resolve_youtube_media_source(_source(), error_cls=MediaError)

    assert youtube_media_key(media, ".json") == "youtube/UCabc123/dQw4w9WgXcQ.json"
    assert youtube_audio_key(media) == f"youtube/UCabc123/dQw4w9WgXcQ{AUDIO_SUFFIX}"
    assert youtube_persistent_video_key(media) == f"youtube/UCabc123/dQw4w9WgXcQ{PERSISTENT_VIDEO_SUFFIX}"
