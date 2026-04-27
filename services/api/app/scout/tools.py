"""Scout's tool palette — Anthropic tool definitions + Python handlers.

Built-in tools (Anthropic-hosted): web_search, web_fetch.
Custom tools (local Python): dedupe_check, persist_candidate.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from jeromelu_shared.db import Channel, DiscoveredSource, Source

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool definitions sent to the Anthropic API.
# Built-in tool versions per Anthropic docs (verify on implementation):
#   web_search:  type="web_search_20250305"
#   web_fetch:   type="web_fetch_20250209"
# ---------------------------------------------------------------------------

WEB_SEARCH_TOOL: dict[str, Any] = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 15,
    "user_location": {
        "type": "approximate",
        "city": "Sydney",
        "region": "New South Wales",
        "country": "AU",
        "timezone": "Australia/Sydney",
    },
}

WEB_FETCH_TOOL: dict[str, Any] = {
    "type": "web_fetch_20250209",
    "name": "web_fetch",
}

DEDUPE_CHECK_TOOL: dict[str, Any] = {
    "name": "dedupe_check",
    "description": (
        "Check whether a YouTube channel or video is already known to the system "
        "(tracked in channels, ingested in sources, or previously surfaced as a "
        "candidate in discovered_sources). Call this BEFORE persisting a candidate "
        "to avoid wasted work on duplicates."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["channel", "video"],
                "description": "Whether the candidate is a YouTube channel or a single video.",
            },
            "url": {
                "type": "string",
                "description": (
                    "Full YouTube URL. Accepts channel URLs "
                    "(youtube.com/channel/UC..., youtube.com/@handle) and "
                    "video URLs (youtube.com/watch?v=..., youtu.be/...)."
                ),
            },
        },
        "required": ["kind", "url"],
    },
}

PERSIST_CANDIDATE_TOOL: dict[str, Any] = {
    "name": "persist_candidate",
    "description": (
        "File a discovered NRL YouTube channel or video for human review. "
        "The reviewer will approve or reject. Always call dedupe_check first. "
        "If the candidate already exists with the same (platform, kind, external_id), "
        "this is a no-op and returns status='duplicate'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["channel", "video"],
            },
            "url": {
                "type": "string",
                "description": "Canonical YouTube URL.",
            },
            "title": {
                "type": "string",
                "description": "Channel name or video title.",
            },
            "description": {
                "type": "string",
                "description": "1-3 sentence summary of what the channel/video is about.",
            },
            "channel_external_id": {
                "type": "string",
                "description": (
                    "For videos only: the parent channel's YouTube ID "
                    "(UC...) if you can determine it."
                ),
            },
            "content_categories": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "match", "analysis", "news", "injury", "tactical",
                        "opinion", "player-content", "classic", "rules-officiating",
                        "supercoach", "nrlw", "origin", "international", "junior",
                    ],
                },
                "description": "One or more category tags. See system prompt.",
            },
            "score": {
                "type": "number",
                "description": "Your qualitative quality score 0.0–1.0.",
            },
            "score_reasons": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Short justifications. At least 2 entries.",
            },
            "metadata": {
                "type": "object",
                "description": (
                    "Free-form facts gathered during evaluation: subscriber count, "
                    "view count, upload cadence, language, last upload date, etc."
                ),
            },
            "discovered_via": {
                "type": "string",
                "description": (
                    "How you found it: a search query string, a related-to:<channel> "
                    "reference, or 'manual' for human-pasted URLs."
                ),
            },
        },
        "required": [
            "kind", "url", "title", "content_categories",
            "score", "score_reasons", "discovered_via",
        ],
    },
}


def all_tools() -> list[dict[str, Any]]:
    """Tool array passed to the Anthropic Messages API."""
    return [WEB_SEARCH_TOOL, WEB_FETCH_TOOL, DEDUPE_CHECK_TOOL, PERSIST_CANDIDATE_TOOL]


# ---------------------------------------------------------------------------
# Custom tool handlers (Python implementations)
# ---------------------------------------------------------------------------

_YT_VIDEO_PATTERNS = [
    re.compile(r"youtube\.com/watch\?.*?v=([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"youtube\.com/shorts/([A-Za-z0-9_-]{11})"),
]

_YT_CHANNEL_ID_PATTERN = re.compile(r"youtube\.com/channel/(UC[A-Za-z0-9_-]{22})")
_YT_HANDLE_PATTERN = re.compile(r"youtube\.com/@([A-Za-z0-9_.-]+)")


def extract_youtube_id(kind: str, url: str) -> str | None:
    """Extract the canonical YouTube external_id from a URL.

    Channels: returns the UC... id if present, otherwise the @handle.
    Videos: returns the 11-char video id.
    """
    if kind == "video":
        for pat in _YT_VIDEO_PATTERNS:
            m = pat.search(url)
            if m:
                return m.group(1)
        # Try parsing query string as last resort
        try:
            qs = parse_qs(urlparse(url).query)
            if "v" in qs and qs["v"]:
                return qs["v"][0]
        except Exception:
            pass
        return None

    if kind == "channel":
        m = _YT_CHANNEL_ID_PATTERN.search(url)
        if m:
            return m.group(1)
        m = _YT_HANDLE_PATTERN.search(url)
        if m:
            return f"@{m.group(1)}"
        return None

    return None


def handle_dedupe_check(session: Session, *, kind: str, url: str) -> dict[str, Any]:
    """Return whether this candidate is already known.

    Checks (in order): channels, sources (for videos), discovered_sources.
    """
    external_id = extract_youtube_id(kind, url)
    if not external_id:
        return {
            "known": False,
            "reason": "could-not-extract-id",
            "external_id": None,
        }

    # 1. Already a tracked channel?
    if kind == "channel":
        existing = session.execute(
            select(Channel.channel_id, Channel.name).where(
                Channel.platform == "youtube",
                Channel.external_id == external_id,
            )
        ).first()
        if existing:
            return {
                "known": True,
                "where": "channels",
                "name": existing.name,
                "external_id": external_id,
            }

    # 2. Already an ingested source (video URL match)?
    if kind == "video":
        existing_src = session.execute(
            select(Source.source_id, Source.title).where(
                Source.canonical_url == url
            )
        ).first()
        if existing_src:
            return {
                "known": True,
                "where": "sources",
                "title": existing_src.title,
                "external_id": external_id,
            }

    # 3. Already surfaced as a candidate (any status)?
    existing_disc = session.execute(
        select(DiscoveredSource.id, DiscoveredSource.status).where(
            DiscoveredSource.platform == "youtube",
            DiscoveredSource.kind == kind,
            DiscoveredSource.external_id == external_id,
        )
    ).first()
    if existing_disc:
        return {
            "known": True,
            "where": "discovered_sources",
            "status": existing_disc.status,
            "external_id": external_id,
        }

    return {"known": False, "external_id": external_id}


def handle_persist_candidate(
    session: Session,
    *,
    run_id: str,
    kind: str,
    url: str,
    title: str,
    content_categories: list[str],
    score: float,
    score_reasons: list[str],
    discovered_via: str,
    description: str | None = None,
    channel_external_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert a candidate. Idempotent on (platform, kind, external_id)."""
    external_id = extract_youtube_id(kind, url)
    if not external_id:
        return {
            "ok": False,
            "error": "could-not-extract-youtube-id",
            "url": url,
        }

    stmt = (
        pg_insert(DiscoveredSource)
        .values(
            kind=kind,
            platform="youtube",
            external_id=external_id,
            url=url,
            title=title,
            description=description,
            channel_external_id=channel_external_id,
            content_categories=content_categories or [],
            score=score,
            score_reasons=score_reasons or [],
            metadata_json=metadata or {},
            discovered_via=discovered_via,
            status="pending",
            run_id=run_id,
        )
        .on_conflict_do_nothing(constraint="uq_discovered_platform_kind_external")
        .returning(DiscoveredSource.id)
    )
    result = session.execute(stmt).first()
    session.commit()

    if result is None:
        # Already exists — fetch what's there
        existing = session.execute(
            select(DiscoveredSource.id, DiscoveredSource.status).where(
                DiscoveredSource.platform == "youtube",
                DiscoveredSource.kind == kind,
                DiscoveredSource.external_id == external_id,
            )
        ).first()
        return {
            "ok": True,
            "status": "duplicate",
            "candidate_id": str(existing.id) if existing else None,
            "previous_status": existing.status if existing else None,
        }

    logger.info("Scout filed candidate kind=%s id=%s title=%s", kind, external_id, title)
    return {
        "ok": True,
        "status": "filed",
        "candidate_id": str(result.id),
        "external_id": external_id,
    }


CUSTOM_TOOL_HANDLERS = {
    "dedupe_check": handle_dedupe_check,
    "persist_candidate": handle_persist_candidate,
}
