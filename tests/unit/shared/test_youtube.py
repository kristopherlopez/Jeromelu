from jeromelu_shared.youtube import (
    extract_channel_external_id,
    extract_video_id,
    extract_youtube_id,
)


def test_extract_video_id_from_common_urls():
    assert extract_video_id("https://www.youtube.com/watch?v=abcdefghijk") == "abcdefghijk"
    assert extract_video_id("https://youtu.be/ABCDEFGHI01?t=10") == "ABCDEFGHI01"
    assert extract_video_id("https://www.youtube.com/shorts/123456789ab") == "123456789ab"


def test_extract_video_id_rejects_invalid_values():
    assert extract_video_id(None) is None
    assert extract_video_id("https://www.youtube.com/watch?v=too-short") is None
    assert extract_video_id("https://example.com/watch?v=abcdefghijk") is None


def test_extract_channel_external_id():
    channel_id = "UCabcdefghijklmnopqrstuv"

    assert extract_channel_external_id(f"https://www.youtube.com/channel/{channel_id}") == channel_id
    assert extract_channel_external_id("https://www.youtube.com/@nrlpod.test") == "@nrlpod.test"
    assert extract_channel_external_id("https://www.youtube.com/c/LegacyName") is None


def test_extract_youtube_id_dispatches_by_kind():
    assert extract_youtube_id("video", "https://youtu.be/ABCDEFGHI01") == "ABCDEFGHI01"
    assert extract_youtube_id("channel", "https://www.youtube.com/@show") == "@show"
    assert extract_youtube_id("playlist", "https://www.youtube.com/playlist?list=x") is None
