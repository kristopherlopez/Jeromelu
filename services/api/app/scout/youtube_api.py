"""YouTube Data API v3 client used by Scout's deterministic discovery tools.

Why a separate module from the existing `youtube_utils.search` package: that
one uses yt-dlp (unauthenticated, no metadata). For Scout we want subscriber
counts, video counts, country, language, last-upload date, and structured
filtering — all of which require the official Data API.

Requires `YOUTUBE_API_KEY` (free tier: 10,000 units/day; search.list = 100
units, channels.list / channelSections.list / playlistItems.list / videos.list
= 1 unit). A typical Scout run with 6 channel searches + 20 channel-stats
lookups consumes ~620 units. A weekly video-stats refresh across ~150 channels
consumes ~750 units.

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

    list_channel_videos(channel_external_id, after_video_id=None, max_results=200)
        → list of {video_id, title, description, thumbnail_url,
                   published_at, url}
        Walks the channel's uploads playlist newest-first. Stops when it hits
        `after_video_id` (incremental refresh) or `max_results` items.

    get_video_stats(video_ids)
        → dict mapping video_id → {views, likes, comments, duration_seconds,
                                   published_at, title, description,
                                   thumbnail_url, tags, category_id, is_live}.
        Batches up to 50 per call.

`filter_known_external_ids` lets the caller pass a set of already-known YouTube
ids; matching results are dropped server-side before returning to the agent
(saves agent tokens and prevents repeat work).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable

import httpx

from jeromelu_shared.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.googleapis.com/youtube/v3"
_DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


def _best_thumbnail_url(thumbnails: dict[str, Any] | None) -> str | None:
    """Pick the highest-resolution thumbnail YouTube returned.

    YouTube returns up to 5 sizes (default, medium, high, standard, maxres)
    but rarely includes all of them. Walk the list in descending quality and
    return the first one that exists.
    """
    if not thumbnails:
        return None
    for size in ("maxres", "standard", "high", "medium", "default"):
        entry = thumbnails.get(size)
        if entry and entry.get("url"):
            return entry["url"]
    return None


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

def _paginated_search(base_params: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    """Loop search.list with nextPageToken until we have `max_results` items
    or there are no more pages. Each page is one quota call (100 units)."""
    target = max(min(max_results, 200), 1)  # hard cap at 200 to bound quota
    items: list[dict[str, Any]] = []
    page_token: str | None = None
    while len(items) < target:
        page_size = min(50, target - len(items))
        params = {**base_params, "maxResults": page_size}
        if page_token:
            params["pageToken"] = page_token
        raw = _get("search", params)
        page_items = raw.get("items", [])
        if not page_items:
            break
        items.extend(page_items)
        page_token = raw.get("nextPageToken")
        if not page_token:
            break
    return items


def search_channels(
    query: str,
    max_results: int = 50,
    filter_known_external_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Channel search via Data API. Region-biased to AU. Up to 100 via pagination."""
    raw_items = _paginated_search(
        {
            "part": "snippet",
            "q": query,
            "type": "channel",
            "regionCode": "AU",
            "relevanceLanguage": "en",
        },
        max_results,
    )
    known = set(filter_known_external_ids or [])
    out: list[dict[str, Any]] = []
    for item in raw_items:
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
    """Video search. `published_after` is RFC 3339. Up to 100 via pagination."""
    base: dict[str, Any] = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "regionCode": "AU",
        "relevanceLanguage": "en",
    }
    if published_after:
        base["publishedAfter"] = published_after
    raw_items = _paginated_search(base, max_results)
    known = set(filter_known_external_ids or [])
    out: list[dict[str, Any]] = []
    for item in raw_items:
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
    """Detailed metadata for up to 50 channels in one call. Cheap (1 unit).

    Returns the popularity stats (subs / videos / views) plus identity-ish
    fields the API ships in the same response at no extra cost: handle
    (`customUrl`), avatar URL (`snippet.thumbnails`), and the actual uploads
    playlist id (`contentDetails.relatedPlaylists.uploads`). Callers can
    persist the latter three onto `channels` rather than re-deriving them.
    """
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
        cd = item.get("contentDetails", {}) or {}
        related = cd.get("relatedPlaylists", {}) or {}
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
            # Free wins from snippet/contentDetails — cost the same call.
            "handle": snip.get("customUrl") or None,
            "avatar_url": _best_thumbnail_url(snip.get("thumbnails")),
            "uploads_playlist_id": related.get("uploads") or None,
        })
    return out


# ---------------------------------------------------------------------------
# Existence validation — used at persist time to catch fabricated handles.
# Returns the canonical YouTube item dict (with snippet+statistics) or None.
# 1 quota unit per call.
# ---------------------------------------------------------------------------

def validate_channel(external_id: str | None) -> dict[str, Any] | None:
    """Verify a channel exists on YouTube. Accepts UC… ids and @handles.

    Returns the channel item (with snippet, statistics, contentDetails) if
    found — caller can read item['id'] for the canonical UC id even if
    the input was a handle. Returns None if YouTube has no item for the
    given identifier (i.e. the handle was fabricated or the channel was
    deleted).
    """
    if not external_id:
        return None
    if external_id.startswith("@"):
        params = {"part": "snippet,statistics,contentDetails", "forHandle": external_id}
    else:
        params = {"part": "snippet,statistics,contentDetails", "id": external_id}
    raw = _get("channels", params)
    items = raw.get("items", [])
    return items[0] if items else None


def validate_video(video_id: str | None) -> dict[str, Any] | None:
    """Verify a video exists on YouTube. Returns the videos.list item or None."""
    if not video_id:
        return None
    raw = _get("videos", {"part": "snippet,statistics,contentDetails", "id": video_id})
    items = raw.get("items", [])
    return items[0] if items else None


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


# ---------------------------------------------------------------------------
# playlistItems.list / videos.list (1 unit each) — channel uploads + stats
#
# Every YouTube channel has a hidden "uploads" playlist whose ID is just the
# channel ID with the "UC" prefix swapped for "UU". Walking that playlist
# newest-first is the cheapest way to enumerate every video a channel has
# published — far cheaper than search.list?channelId=... (100 units/page).
# ---------------------------------------------------------------------------

# ISO 8601 duration like "PT1H23M45S" — YouTube's format for video length.
_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def _parse_iso_duration(value: str | None) -> int | None:
    """Convert ISO 8601 duration (e.g. 'PT1H23M45S') to seconds. None if unparseable."""
    if not value:
        return None
    m = _DURATION_RE.fullmatch(value)
    if not m:
        return None
    h, mn, s = m.groups()
    return (int(h or 0) * 3600) + (int(mn or 0) * 60) + int(s or 0)


def _uploads_playlist_id(channel_external_id: str) -> str:
    """Convert a UC... channel ID to its uploads playlist ID (UU...).

    YouTube guarantees this for every channel (the "uploads" auto-playlist).
    Cheaper than calling channels.list?part=contentDetails just to read it.
    """
    if not channel_external_id.startswith("UC"):
        # Defensive: if the convention ever breaks for legacy channels, the
        # caller will get a 404 from the API and we can fall back then.
        raise YouTubeAPIError(
            f"Channel external_id does not start with 'UC': {channel_external_id!r}"
        )
    return "UU" + channel_external_id[2:]


def list_channel_videos(
    channel_external_id: str,
    after_video_id: str | None = None,
    max_results: int = 200,
) -> list[dict[str, Any]]:
    """Enumerate videos from a channel's uploads playlist, newest first.

    Uses playlistItems.list (1 quota unit per page) on the channel's auto
    'uploads' playlist. Returns at most `max_results` videos.

    For incremental refresh, pass `after_video_id` = the most-recent video_id
    you already have for this channel. Pagination stops as soon as that id
    appears in the response, so weekly refreshes are typically a single page.
    """
    playlist_id = _uploads_playlist_id(channel_external_id)
    target = max(min(max_results, 1000), 1)
    out: list[dict[str, Any]] = []
    page_token: str | None = None
    while len(out) < target:
        page_size = min(50, target - len(out))
        params: dict[str, Any] = {
            "part": "snippet,contentDetails",
            "playlistId": playlist_id,
            "maxResults": page_size,
        }
        if page_token:
            params["pageToken"] = page_token
        raw = _get("playlistItems", params)
        items = raw.get("items", [])
        if not items:
            break
        hit_known = False
        for item in items:
            cd = item.get("contentDetails", {}) or {}
            snip = item.get("snippet", {}) or {}
            vid = cd.get("videoId") or snip.get("resourceId", {}).get("videoId")
            if not vid:
                continue
            if after_video_id and vid == after_video_id:
                hit_known = True
                break
            out.append({
                "video_id": vid,
                "title": snip.get("title", ""),
                "description": snip.get("description", ""),
                "thumbnail_url": _best_thumbnail_url(snip.get("thumbnails")),
                "published_at": cd.get("videoPublishedAt") or snip.get("publishedAt", ""),
                "url": f"https://www.youtube.com/watch?v={vid}",
            })
        if hit_known:
            break
        page_token = raw.get("nextPageToken")
        if not page_token:
            break
    return out


def get_video_stats(video_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Batch-fetch view / like / comment counts plus identity metadata for a
    list of video ids.

    Single API call covers `part=statistics,contentDetails,snippet`, so the
    returned dict carries everything in those three parts. Time-varying
    fields (views/likes/comments) belong in `video_metrics`; identity fields
    (duration, description, thumbnail, tags, category, is_live, title)
    belong on `sources` — callers split as needed.

    1 quota unit per call, up to 50 ids per call. Missing ids (private,
    deleted, non-existent) are simply absent from the returned dict.
    """
    if not video_ids:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        raw = _get(
            "videos",
            {
                "part": "statistics,contentDetails,snippet",
                "id": ",".join(batch),
            },
        )
        for item in raw.get("items", []):
            stats = item.get("statistics", {}) or {}
            cd = item.get("contentDetails", {}) or {}
            snip = item.get("snippet", {}) or {}
            entry: dict[str, Any] = {}
            # statistics — time-varying
            if "viewCount" in stats:
                try:
                    entry["views"] = int(stats["viewCount"])
                except (TypeError, ValueError):
                    pass
            if "likeCount" in stats:
                try:
                    entry["likes"] = int(stats["likeCount"])
                except (TypeError, ValueError):
                    pass
            if "commentCount" in stats:
                try:
                    entry["comments"] = int(stats["commentCount"])
                except (TypeError, ValueError):
                    pass
            # contentDetails — identity
            duration_seconds = _parse_iso_duration(cd.get("duration"))
            if duration_seconds is not None:
                entry["duration_seconds"] = duration_seconds
            # snippet — identity (paid for already, was being discarded)
            if snip.get("publishedAt"):
                entry["published_at"] = snip["publishedAt"]
            if snip.get("title"):
                entry["title"] = snip["title"]
            if snip.get("description") is not None:
                entry["description"] = snip["description"]
            if snip.get("channelId"):
                entry["channel_id"] = snip["channelId"]
            if snip.get("channelTitle"):
                entry["channel_title"] = snip["channelTitle"]
            if snip.get("categoryId"):
                entry["category_id"] = snip["categoryId"]
            if snip.get("tags"):
                entry["tags"] = list(snip["tags"])
            thumb = _best_thumbnail_url(snip.get("thumbnails"))
            if thumb:
                entry["thumbnail_url"] = thumb
            live = snip.get("liveBroadcastContent")
            if live and live != "none":
                entry["is_live"] = True
            out[item["id"]] = entry
    return out
