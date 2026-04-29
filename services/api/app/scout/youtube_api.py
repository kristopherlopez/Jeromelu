"""YouTube Data API v3 client used by Scout's deterministic discovery tools.

Why a separate module from the existing `youtube_utils.search` package: that
one uses yt-dlp (unauthenticated, no metadata). For Scout we want subscriber
counts, video counts, country, language, last-upload date, and structured
filtering — all of which require the official Data API.

Requires `YOUTUBE_API_KEY` (free tier: 10,000 units/day; search.list = 100
units, channels.list / channelSections.list = 1 unit). A typical Scout run
with 6 channel searches + 20 channel-stats lookups consumes ~620 units.

Module surface — all functions are sync (Scout's loop is sync) and use httpx
(already a transitive dep via anthropic/openai SDKs):

    search_channels(query, max_results=10, filter_known_external_ids=None)
        → list of {channel_id, title, description, channel_url}

    search_videos(query, max_results=10, published_after=None,
                  filter_known_external_ids=None)
        → list of {video_id, channel_id, title, description, published_at, url}

    get_channel_stats(channel_ids)
        → list of {channel_id, title, description, subs, video_count,
                   view_count, country, last_upload, default_language}

    get_channel_sections(channel_id)
        → list of featured channel_ids (channelSections of type 'multipleChannels')

`filter_known_external_ids` lets the caller pass a set of already-known YouTube
ids; matching results are dropped server-side before returning to the agent
(saves agent tokens and prevents repeat work).
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

import httpx

from jeromelu_shared.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.googleapis.com/youtube/v3"
_DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class YouTubeAPIError(RuntimeError):
    """Raised when the YouTube API returns an error or no key is configured."""


def _api_key() -> str:
    key = settings.youtube_api_key
    if not key:
        raise YouTubeAPIError(
            "YOUTUBE_API_KEY is not set — Scout's YouTube tools cannot run"
        )
    return key


def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    """One GET against the Data API. Raises YouTubeAPIError on non-2xx."""
    full_params = {**params, "key": _api_key()}
    try:
        with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
            r = client.get(f"{_BASE_URL}/{path}", params=full_params)
    except httpx.HTTPError as e:
        raise YouTubeAPIError(f"YouTube API request failed: {e}") from e
    if r.status_code >= 400:
        # Bubble up the API's own error message — usually informative
        # (quota exceeded, key revoked, etc.).
        raise YouTubeAPIError(
            f"YouTube API {path} returned {r.status_code}: {r.text[:500]}"
        )
    return r.json()


# ---------------------------------------------------------------------------
# search.list (100 units per call)
# ---------------------------------------------------------------------------

def search_channels(
    query: str,
    max_results: int = 50,
    filter_known_external_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Channel search via Data API. Region-biased to AU."""
    raw = _get(
        "search",
        {
            "part": "snippet",
            "q": query,
            "type": "channel",
            "maxResults": min(max(max_results, 1), 50),
            "regionCode": "AU",
            "relevanceLanguage": "en",
        },
    )
    known = set(filter_known_external_ids or [])
    out: list[dict[str, Any]] = []
    for item in raw.get("items", []):
        cid = item.get("snippet", {}).get("channelId") or item.get("id", {}).get("channelId")
        if not cid or cid in known:
            continue
        snip = item["snippet"]
        out.append({
            "channel_id": cid,
            "title": snip.get("channelTitle") or snip.get("title", ""),
            "description": snip.get("description", ""),
            "channel_url": f"https://www.youtube.com/channel/{cid}",
        })
    return out


def search_videos(
    query: str,
    max_results: int = 50,
    published_after: str | None = None,
    filter_known_external_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Video search. `published_after` is RFC 3339 (e.g. '2026-04-01T00:00:00Z')."""
    params: dict[str, Any] = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": min(max(max_results, 1), 50),
        "regionCode": "AU",
        "relevanceLanguage": "en",
    }
    if published_after:
        params["publishedAfter"] = published_after
    raw = _get("search", params)
    known = set(filter_known_external_ids or [])
    out: list[dict[str, Any]] = []
    for item in raw.get("items", []):
        vid = item.get("id", {}).get("videoId")
        if not vid or vid in known:
            continue
        snip = item["snippet"]
        out.append({
            "video_id": vid,
            "channel_id": snip.get("channelId", ""),
            "channel_title": snip.get("channelTitle", ""),
            "title": snip.get("title", ""),
            "description": snip.get("description", ""),
            "published_at": snip.get("publishedAt", ""),
            "url": f"https://www.youtube.com/watch?v={vid}",
        })
    return out


# ---------------------------------------------------------------------------
# Long-tail discovery — videos → distinct channels
#
# YouTube channel search is ranked; long-tail channels never make the top 50.
# But popular VIDEOS for niche queries do, and each video carries a channel_id.
# Searching videos and extracting distinct channels reveals channels that:
#   - Publish viral one-off content but have low subscriber counts
#   - Cover specific events (round, match, player) and rank on those terms
#   - Are too small to win a channel-search relevance battle
# ---------------------------------------------------------------------------

def harvest_channels_from_videos(
    query: str,
    max_videos: int = 50,
    published_after: str | None = None,
    filter_known_external_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Search videos for `query`, return distinct channels publishing them.

    First-seen video title is included so the agent can see WHY this channel
    surfaced (helps with category/score judgment).
    """
    videos = search_videos(
        query,
        max_results=max_videos,
        published_after=published_after,
    )
    known = set(filter_known_external_ids or [])
    seen: dict[str, dict[str, Any]] = {}
    for v in videos:
        cid = v.get("channel_id")
        if not cid or cid in known or cid in seen:
            continue
        seen[cid] = {
            "channel_id": cid,
            "channel_title": v.get("channel_title", ""),
            "first_seen_video_title": v.get("title", ""),
            "first_seen_video_published_at": v.get("published_at", ""),
        }
    return list(seen.values())


# ---------------------------------------------------------------------------
# channels.list (1 unit per call regardless of how many ids passed, up to 50)
# ---------------------------------------------------------------------------

def get_channel_stats(channel_ids: list[str]) -> list[dict[str, Any]]:
    """Detailed metadata for up to 50 channels in one call. Cheap (1 unit)."""
    if not channel_ids:
        return []
    raw = _get(
        "channels",
        {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(channel_ids[:50]),
        },
    )
    out: list[dict[str, Any]] = []
    for item in raw.get("items", []):
        snip = item.get("snippet", {}) or {}
        stats = item.get("statistics", {}) or {}
        out.append({
            "channel_id": item["id"],
            "title": snip.get("title", ""),
            "description": snip.get("description", ""),
            "country": snip.get("country", ""),
            "default_language": snip.get("defaultLanguage", ""),
            "published_at": snip.get("publishedAt", ""),
            "subs": int(stats.get("subscriberCount", 0)) if not stats.get("hiddenSubscriberCount") else None,
            "video_count": int(stats.get("videoCount", 0)) if stats.get("videoCount") else 0,
            "view_count": int(stats.get("viewCount", 0)) if stats.get("viewCount") else 0,
        })
    return out


# ---------------------------------------------------------------------------
# channelSections.list (1 unit) — featured channels surface
# ---------------------------------------------------------------------------

def get_channel_sections(channel_id: str) -> list[str]:
    """Return channel_ids that the given channel features in any 'channels' section.

    Strong signal for finding adjacent creators: a podcast network usually
    features its other shows; an ex-player's channel often features peers.
    """
    raw = _get(
        "channelSections",
        {
            "part": "snippet,contentDetails",
            "channelId": channel_id,
        },
    )
    related: set[str] = set()
    for item in raw.get("items", []):
        cd = item.get("contentDetails", {}) or {}
        for cid in cd.get("channels", []) or []:
            if cid and cid != channel_id:
                related.add(cid)
    return sorted(related)
