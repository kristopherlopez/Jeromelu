from __future__ import annotations

from uuid import uuid4

from app.scout.source_discovery import deterministic_youtube as dy


def _draft(kind: str, external_id: str) -> dy.CandidateDraft:
    return dy.CandidateDraft(
        kind=kind,
        external_id=external_id,
        url=(
            f"https://www.youtube.com/channel/{external_id}"
            if kind == "channel"
            else f"https://www.youtube.com/watch?v={external_id}"
        ),
        title=f"{kind} {external_id}",
        description="NRL analysis",
        channel_external_id="UCparent" if kind == "video" else None,
        content_categories=["analysis"],
        score=0.7,
        score_reasons=["Video metadata includes NRL signal: nrl.", "YouTube returned useful metadata."],
        metadata={"discovery_signals": [{"mode": "test"}]},
        discovered_via="deterministic_youtube:test",
    )


def test_run_filters_known_ids_scores_and_persists_novel_candidates(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        dy,
        "load_known_youtube_ids",
        lambda _session: dy.KnownYouTubeIds(channel_ids={"UCknown"}, video_ids={"VIDKNOWN"}),
    )

    def fake_search_channels(query, *, max_results, filter_known_external_ids):
        captured["channel_filter"] = set(filter_known_external_ids)
        assert query == "NRL discovery"
        assert max_results == 10
        return [
            {
                "channel_id": "UCknown",
                "title": "Known NRL Channel",
                "description": "Should be skipped despite the mocked API returning it.",
            },
            {
                "channel_id": "UCnew",
                "title": "NRL Injury Report",
                "description": "Rugby league late mail and team news.",
            },
            {
                "channel_id": "UCcooking",
                "title": "Weekend Cooking",
                "description": "Recipes and kitchen gear.",
            },
        ]

    def fake_harvest_channels_from_videos(query, *, max_videos, published_after, filter_known_external_ids):
        captured["harvest_filter"] = set(filter_known_external_ids)
        assert query == "NRL harvest"
        assert max_videos == 25
        assert published_after == "2026-04-01T00:00:00Z"
        return [
            {
                "channel_id": "UCharvest",
                "channel_title": "Origin Breakdown",
                "first_seen_video_title": "NRL State of Origin tactical review",
                "first_seen_video_published_at": "2026-04-03T00:00:00Z",
            }
        ]

    def fake_search_videos(query, *, max_results, published_after, filter_known_external_ids):
        captured["video_filter"] = set(filter_known_external_ids)
        assert query == "NRL video"
        assert max_results == 25
        assert published_after == "2026-04-01T00:00:00Z"
        return [
            {
                "video_id": "VIDKNOWN",
                "channel_id": "UCknown",
                "channel_title": "Known NRL Channel",
                "title": "Known video",
                "description": "Should be skipped.",
                "published_at": "2026-04-02T00:00:00Z",
                "url": "https://www.youtube.com/watch?v=VIDKNOWN",
            },
            {
                "video_id": "VIDNEW",
                "channel_id": "UCparent",
                "channel_title": "NRL Voice",
                "title": "NRL injury update",
                "description": "Rugby league late mail.",
                "published_at": "2026-04-02T00:00:00Z",
                "url": "https://www.youtube.com/watch?v=VIDNEW",
            },
        ]

    def fake_get_channel_stats(channel_ids):
        captured["channel_stats_ids"] = list(channel_ids)
        return [
            {
                "channel_id": "UCnew",
                "title": "NRL Injury Report",
                "description": "Rugby league late mail and team news.",
                "country": "AU",
                "default_language": "en",
                "published_at": "2024-01-01T00:00:00Z",
                "subs": 5_000,
                "video_count": 30,
                "view_count": 750_000,
                "handle": "@nrlinjury",
                "avatar_url": "https://example.test/avatar.jpg",
                "uploads_playlist_id": "UUnew",
            },
            {
                "channel_id": "UCcooking",
                "title": "Weekend Cooking",
                "description": "Recipes and kitchen gear.",
                "country": "AU",
                "default_language": "en",
                "published_at": "2024-01-01T00:00:00Z",
                "subs": 100_000,
                "video_count": 100,
                "view_count": 2_000_000,
                "handle": "@cooking",
                "avatar_url": None,
                "uploads_playlist_id": "UUcooking",
            },
            {
                "channel_id": "UCharvest",
                "title": "Origin Breakdown",
                "description": "NRL tactical breakdown and State of Origin analysis.",
                "country": "AU",
                "default_language": "en",
                "published_at": "2024-01-01T00:00:00Z",
                "subs": 900,
                "video_count": 12,
                "view_count": 40_000,
                "handle": "@originbreakdown",
                "avatar_url": None,
                "uploads_playlist_id": "UUharvest",
            },
        ]

    def fake_get_video_stats(video_ids):
        captured["video_stats_ids"] = list(video_ids)
        return {
            "VIDNEW": {
                "title": "NRL injury update",
                "description": "Rugby league late mail.",
                "channel_id": "UCparent",
                "channel_title": "NRL Voice",
                "published_at": "2026-04-02T00:00:00Z",
                "views": 30_000,
                "likes": 1_200,
                "comments": 80,
                "duration_seconds": 620,
                "thumbnail_url": "https://example.test/thumb.jpg",
                "tags": ["NRL", "injury"],
            }
        }

    def fake_persist(session, *, run_id, candidates, dry_run):
        captured["persist_run_id"] = run_id
        captured["persist_dry_run"] = dry_run
        captured["candidates"] = list(candidates)
        return dy.PersistSummary(
            inserted=len(candidates),
            duplicates=0,
            candidate_ids=[f"id-{i}" for i, _candidate in enumerate(candidates, start=1)],
        )

    monkeypatch.setattr(dy.youtube_api, "search_channels", fake_search_channels)
    monkeypatch.setattr(dy.youtube_api, "harvest_channels_from_videos", fake_harvest_channels_from_videos)
    monkeypatch.setattr(dy.youtube_api, "search_videos", fake_search_videos)
    monkeypatch.setattr(dy.youtube_api, "get_channel_stats", fake_get_channel_stats)
    monkeypatch.setattr(dy.youtube_api, "get_video_stats", fake_get_video_stats)
    monkeypatch.setattr(dy, "persist_candidate_drafts", fake_persist)

    result = dy.run_deterministic_youtube_discovery(
        object(),
        run_id="scout-test",
        channel_queries=["NRL discovery"],
        harvest_queries=["NRL harvest"],
        video_queries=["NRL video"],
        published_after="2026-04-01T00:00:00Z",
    )

    persisted = captured["candidates"]
    persisted_ids = {candidate.external_id for candidate in persisted}
    assert persisted_ids == {"UCnew", "UCharvest", "VIDNEW"}
    assert "UCknown" in captured["channel_filter"]
    assert "UCknown" in captured["harvest_filter"]
    assert "VIDKNOWN" in captured["video_filter"]
    assert "UCknown" not in captured["channel_stats_ids"]
    assert "VIDKNOWN" not in captured["video_stats_ids"]
    assert result.candidates_below_threshold == 1
    assert result.candidates_inserted == 3
    assert captured["persist_run_id"] == "scout-test"
    assert captured["persist_dry_run"] is False

    channel = next(candidate for candidate in persisted if candidate.external_id == "UCnew")
    assert channel.metadata["subscribers"] == 5_000
    assert channel.metadata["uploads_playlist_id"] == "UUnew"
    assert len(channel.score_reasons) >= 2
    assert channel.discovered_via.startswith("deterministic_youtube:channel_search")

    video = next(candidate for candidate in persisted if candidate.external_id == "VIDNEW")
    assert video.channel_external_id == "UCparent"
    assert video.metadata["views"] == 30_000
    assert "injury" in video.content_categories


def test_persist_candidate_drafts_uses_idempotent_insert_and_commits():
    class FakeResult:
        def __init__(self, row):
            self.row = row

        def first(self):
            return self.row

    class FakeSession:
        def __init__(self):
            self.rows = [FakeResult((uuid4(),)), FakeResult(None)]
            self.statements = []
            self.commits = 0

        def execute(self, statement):
            self.statements.append(statement)
            return self.rows.pop(0)

        def commit(self):
            self.commits += 1

    session = FakeSession()

    summary = dy.persist_candidate_drafts(
        session,
        run_id="scout-test",
        candidates=[_draft("channel", "UCnew"), _draft("video", "VIDnew")],
    )

    assert summary.inserted == 1
    assert summary.duplicates == 1
    assert len(summary.candidate_ids) == 1
    assert len(session.statements) == 2
    assert session.commits == 1


def test_persist_candidate_drafts_dry_run_skips_db_write():
    class ExplodingSession:
        def execute(self, _statement):
            raise AssertionError("dry-run should not execute SQL")

        def commit(self):
            raise AssertionError("dry-run should not commit")

    summary = dy.persist_candidate_drafts(
        ExplodingSession(),
        run_id="scout-test",
        candidates=[_draft("channel", "UCnew")],
        dry_run=True,
    )

    assert summary.inserted == 0
    assert summary.duplicates == 0
    assert summary.candidate_ids == []
