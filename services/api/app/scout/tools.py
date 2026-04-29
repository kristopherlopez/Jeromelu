"""Scout's tool palette — Anthropic tool definitions + Python handlers.

Built-in tools (Anthropic-hosted): web_search, web_fetch.
Custom tools (local Python): dedupe_check, dedupe_check_bulk, persist_candidate.

Also exposes `summarise_known_sources()` — used by the run loop to seed the
per-run user brief with the channels Scout already knows, so it doesn't
re-discover them.
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
# Built-in tool versions (verified live 2026-04-28 — API reports valid set):
#   web_search:  web_search_20250305 | web_search_20260209 (dynamic filtering, requires code_execution)
#   web_fetch:   web_fetch_20250910 | web_fetch_20260209 | web_fetch_20260309
# ---------------------------------------------------------------------------

WEB_SEARCH_TOOL: dict[str, Any] = {
    "type": "web_search_20250305",
    "name": "web_search",
    # Each search returns 1-3KB of result content into the conversation, which
    # round-trips on every subsequent turn. 6 keeps the per-run input budget
    # comfortably under Anthropic's 50k tokens/min rate limit while still
    # leaving room for varied query angles.
    "max_uses": 6,
    "user_location": {
        "type": "approximate",
        "city": "Sydney",
        "region": "New South Wales",
        "country": "AU",
        "timezone": "Australia/Sydney",
    },
}

WEB_FETCH_TOOL: dict[str, Any] = {
    "type": "web_fetch_20260309",
    "name": "web_fetch",
    # Restrict to direct model-driven calls. Required for Haiku 4.5; harmless
    # on Sonnet/Opus. Without this, Haiku rejects with "does not support
    # programmatic tool calling."
    "allowed_callers": ["direct"],
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


DEDUPE_CHECK_BULK_TOOL: dict[str, Any] = {
    "name": "dedupe_check_bulk",
    "description": (
        "Batched dedupe. Pass a list of {kind, url} items (typically a whole "
        "page of web_search results) and get back a known/unknown verdict for "
        "each in one call. PREFER THIS over single dedupe_check whenever you "
        "have more than one candidate to check — it saves turns and keeps you "
        "from drilling into already-known sources."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["channel", "video"]},
                        "url": {"type": "string"},
                    },
                    "required": ["kind", "url"],
                },
                "description": "List of candidates to check.",
            },
        },
        "required": ["items"],
    },
}


def all_tools() -> list[dict[str, Any]]:
    """Tool array passed to the Anthropic Messages API."""
    return [
        WEB_SEARCH_TOOL,
        WEB_FETCH_TOOL,
        DEDUPE_CHECK_BULK_TOOL,
        DEDUPE_CHECK_TOOL,
        PERSIST_CANDIDATE_TOOL,
    ]


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
        # Use index_elements (column list) rather than the constraint name —
        # migration 017 created the unique constraint inline (no explicit name)
        # so Postgres auto-named it; the model's explicit `name=` doesn't match
        # the actual DB. index_elements lets Postgres resolve the constraint
        # by the columns it covers, working regardless of how it was named.
        .on_conflict_do_nothing(
            index_elements=["platform", "kind", "external_id"]
        )
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


def handle_dedupe_check_bulk(
    session: Session, *, items: list[dict[str, str]]
) -> dict[str, Any]:
    """Batched dedupe — check many URLs in one tool call.

    Each item: {"kind": "channel"|"video", "url": "..."}.
    Returns: {"results": [{...same shape as dedupe_check..., "input": item}, ...]}.
    """
    results: list[dict[str, Any]] = []
    for item in items:
        kind = item.get("kind", "")
        url = item.get("url", "")
        if kind not in ("channel", "video") or not url:
            results.append(
                {"input": item, "ok": False, "error": "invalid-item"}
            )
            continue
        verdict = handle_dedupe_check(session, kind=kind, url=url)
        results.append({"input": item, **verdict})
    return {"checked": len(results), "results": results}


def summarise_known_sources(session: Session, *, max_lines: int = 200) -> str:
    """Build a compact text summary of YouTube sources Scout already knows.

    Used to seed the per-run user brief. Two sections:
      1. Tracked channels (in `channels`, active or inactive)
      2. Previously surfaced candidates (in `discovered_sources`, any status)

    Capped at `max_lines` total to keep token cost bounded.
    """
    tracked = session.execute(
        select(Channel.name, Channel.external_id, Channel.active)
        .where(Channel.platform == "youtube")
        .order_by(Channel.name)
    ).all()

    surfaced = session.execute(
        select(
            DiscoveredSource.title,
            DiscoveredSource.external_id,
            DiscoveredSource.status,
        )
        .where(
            DiscoveredSource.platform == "youtube",
            DiscoveredSource.kind == "channel",
        )
        .order_by(DiscoveredSource.discovered_at.desc())
    ).all()

    lines: list[str] = []
    lines.append("KNOWN SET — DO NOT REDISCOVER")
    lines.append("")

    if tracked:
        lines.append(f"Tracked YouTube channels ({len(tracked)}):")
        for row in tracked[:max_lines]:
            tag = "" if row.active else " [inactive]"
            ext = row.external_id or "?"
            lines.append(f"  - {row.name} — {ext}{tag}")
        if len(tracked) > max_lines:
            lines.append(f"  ... and {len(tracked) - max_lines} more")
        lines.append("")

    if surfaced:
        lines.append(
            f"Previously surfaced as candidates ({len(surfaced)}, any status):"
        )
        budget = max(0, max_lines - len(tracked))
        for row in surfaced[:budget]:
            lines.append(f"  - {row.title} — {row.external_id} [{row.status}]")
        if len(surfaced) > budget:
            lines.append(f"  ... and {len(surfaced) - budget} more")
        lines.append("")

    if not tracked and not surfaced:
        lines.append("(empty — no known sources yet, you have a clean slate)")

    lines.append(
        "Rule: do not search for these names. If they appear in search results, "
        "skip them. Search ADJACENT — niches around them, not them. Always run "
        "dedupe_check_bulk on a fresh search result list before drilling in."
    )
    return "\n".join(lines)


CUSTOM_TOOL_HANDLERS = {
    "dedupe_check": handle_dedupe_check,
    "dedupe_check_bulk": handle_dedupe_check_bulk,
    "persist_candidate": handle_persist_candidate,
}
