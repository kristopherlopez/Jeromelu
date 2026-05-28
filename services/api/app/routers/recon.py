"""Admin endpoints for reviewing and promoting Scout's discovered candidates.

Workflow:
  Scout fills `scout_candidates` (status='pending').
  Reviewer hits these endpoints to approve / reject candidates.
  Approval promotes a row into the canonical tables:
    - kind='channel' → INSERT channels row + INSERT channel-type wiki_pages row
    - kind='video'   → INSERT sources row (channel_id linked to parent if known)

All approve/reject ops are transactional. Idempotent on re-approval (already-
approved rows stay approved without crashing).

Auth: same X-Admin-Key header pattern as the rest of /admin/*.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from jeromelu_shared.db import Channel, ChannelMetric, ScoutCandidate, Source, WikiPage
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..deps import get_db
from ..scout.youtube.refresh import (
    audit_channel_coverage,
    refresh_all_channel_stats,
    refresh_all_channels_incremental,
    refresh_all_video_stats,
    refresh_channel_videos,
)
from .admin import require_admin

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    """Lowercase, hyphen-separated, alphanumeric only. Falls back to 'channel'."""
    base = _SLUG_STRIP.sub("-", (name or "").lower()).strip("-")
    return base or "channel"


def _unique_slug(session: Session, model, slug_col, base: str) -> str:
    """Return `base`, or `base-2`, `base-3`, ... such that nothing matches."""
    candidate = base
    n = 2
    while session.execute(select(slug_col).where(slug_col == candidate)).first():
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def _normalised_youtube_metrics(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Pull YouTube stats from a scout_candidates.metadata_json dict and
    normalise into the canonical channel_metrics shape. Handles the early
    'subs' / 'subscribers' key inconsistency Scout produced before we pinned
    the schema."""
    md = metadata or {}
    subs = md.get("subscribers") or md.get("subs")
    out: dict[str, Any] = {}
    if subs is not None:
        try:
            out["subscribers"] = int(subs)
        except (TypeError, ValueError):
            pass
    if (vc := md.get("video_count")) is not None:
        try:
            out["videos"] = int(vc)
        except (TypeError, ValueError):
            pass
    if (vw := md.get("view_count")) is not None:
        try:
            out["views"] = int(vw)
        except (TypeError, ValueError):
            pass
    if md.get("country"):
        out["country"] = md["country"]
    if md.get("published_at"):
        out["channel_published_at"] = md["published_at"]
    return out


def _channel_wiki_content(name: str, description: str | None, tags: list[str]) -> str:
    """Stub content matching the shape of migration 019's backfill."""
    desc = description or ""
    tag_str = ", ".join(tags) if tags else "_(none)_"
    return (
        "## About\n\n"
        f"{desc}\n\n"
        "## Recent Sources\n\n_None yet._\n\n"
        "## Coverage\n\n"
        f"Tags: {tag_str}\n\n"
        "## Hosts\n\n_Hosts will be linked once advisor pages exist._"
    )


# ---------------------------------------------------------------------------
# GET — list candidates
# ---------------------------------------------------------------------------


@router.get("/admin/recon/candidates", dependencies=[Depends(require_admin)])
def list_candidates(
    status: str | None = Query(default="pending"),
    kind: str | None = Query(default=None),
    min_score: float | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    db: Session = Depends(get_db),
):
    """List discovered candidates, default to status=pending."""
    q = db.query(ScoutCandidate)
    if status:
        q = q.filter(ScoutCandidate.status == status)
    if kind:
        q = q.filter(ScoutCandidate.kind == kind)
    if min_score is not None:
        q = q.filter(ScoutCandidate.score >= min_score)
    rows = (
        q.order_by(
            ScoutCandidate.score.desc().nullslast(),
            ScoutCandidate.discovered_at.desc(),
        )
        .limit(limit)
        .all()
    )
    return {
        "count": len(rows),
        "candidates": [
            {
                "id": str(r.id),
                "kind": r.kind,
                "platform": r.platform,
                "external_id": r.external_id,
                "url": r.url,
                "title": r.title,
                "description": r.description,
                "channel_external_id": r.channel_external_id,
                "content_categories": r.content_categories,
                "score": float(r.score) if r.score is not None else None,
                "score_reasons": r.score_reasons,
                "discovered_via": r.discovered_via,
                "discovered_at": r.discovered_at.isoformat(),
                "status": r.status,
                "run_id": r.run_id,
            }
            for r in rows
        ],
    }


@router.get("/admin/recon/candidates/{candidate_id}", dependencies=[Depends(require_admin)])
def get_candidate(candidate_id: UUID, db: Session = Depends(get_db)):
    row = db.get(ScoutCandidate, candidate_id)
    if not row:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {
        "id": str(row.id),
        "kind": row.kind,
        "platform": row.platform,
        "external_id": row.external_id,
        "url": row.url,
        "title": row.title,
        "description": row.description,
        "channel_external_id": row.channel_external_id,
        "content_categories": row.content_categories,
        "score": float(row.score) if row.score is not None else None,
        "score_reasons": row.score_reasons,
        "metadata_json": row.metadata_json,
        "discovered_via": row.discovered_via,
        "discovered_at": row.discovered_at.isoformat(),
        "status": row.status,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "reviewed_by": row.reviewed_by,
        "reviewed_note": row.reviewed_note,
        "promoted_channel_id": (str(row.promoted_channel_id) if row.promoted_channel_id else None),
        "run_id": row.run_id,
    }


# ---------------------------------------------------------------------------
# POST — approve
# ---------------------------------------------------------------------------


@router.post(
    "/admin/recon/candidates/{candidate_id}/approve",
    dependencies=[Depends(require_admin)],
)
def approve_candidate(
    candidate_id: UUID,
    body: dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
):
    """Promote a scout_candidates row into the canonical tables.

    For kind='channel': insert into channels + wiki_pages.
    For kind='video':   insert into sources.

    Idempotent — re-approving an already-approved row is a no-op.
    """
    row = db.get(ScoutCandidate, candidate_id)
    if not row:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if row.status == "approved" and row.promoted_channel_id:
        return {
            "ok": True,
            "status": "already_approved",
            "candidate_id": str(row.id),
            "promoted_channel_id": str(row.promoted_channel_id),
        }

    reviewed_by = body.get("reviewed_by") or "admin"
    note = body.get("note")

    if row.kind == "channel":
        # Promote channel: upsert channels row + create channel-type wiki page
        slug_base = _slugify(row.title)
        slug = _unique_slug(db, Channel, Channel.slug, slug_base)
        # Logo URL was captured into metadata_json by persist_candidate at
        # discovery time (from the YouTube validation response). Copy it
        # forward so the wiki UI can render avatars without an extra fetch.
        logo_url = (row.metadata_json or {}).get("logo_url")
        ch_stmt = (
            pg_insert(Channel)
            .values(
                slug=slug,
                platform=row.platform,
                external_id=row.external_id,
                name=row.title,
                url=row.url,
                description=row.description,
                quality_rating=round((row.score or 0.5) * 10),
                tags=row.content_categories or [],
                active=True,
                logo_url=logo_url,
            )
            .on_conflict_do_nothing(index_elements=["platform", "external_id"])
            .returning(Channel.channel_id)
        )
        result = db.execute(ch_stmt).first()
        if result is None:
            # Channel already existed under this (platform, external_id)
            existing = db.execute(
                select(Channel.channel_id).where(
                    Channel.platform == row.platform,
                    Channel.external_id == row.external_id,
                )
            ).first()
            channel_id = existing[0] if existing else None
        else:
            channel_id = result[0]

        # Wiki page (one per channel) — idempotent on (channel_id)
        if channel_id:
            existing_wp = db.execute(select(WikiPage.page_id).where(WikiPage.channel_id == channel_id)).first()
            if not existing_wp:
                wiki_slug = _unique_slug(db, WikiPage, WikiPage.slug, slug_base)
                content = _channel_wiki_content(row.title, row.description, row.content_categories or [])
                summary = (row.description or row.title)[:280]
                metadata = {
                    "platform": row.platform,
                    "url": row.url,
                    "quality_rating": round((row.score or 0.5) * 10),
                    "tags": row.content_categories or [],
                }
                db.add(
                    WikiPage(
                        entity_id=None,
                        channel_id=channel_id,
                        page_type="channel",
                        slug=wiki_slug,
                        title=row.title,
                        content=content,
                        summary=summary,
                        metadata_json=metadata,
                        status="stub",
                    )
                )

            # Snapshot the discovery-time metrics so the wiki has subs / videos /
            # views / country / channel age for this channel from day one.
            # Only YouTube has metadata in this shape today.
            if row.platform == "youtube":
                normalised = _normalised_youtube_metrics(row.metadata_json)
                if normalised:
                    db.add(
                        ChannelMetric(
                            channel_id=channel_id,
                            platform=row.platform,
                            sampled_at=datetime.now(UTC),
                            source="youtube_api",
                            metrics=normalised,
                        )
                    )

        row.status = "approved"
        row.reviewed_at = datetime.now(UTC)
        row.reviewed_by = reviewed_by
        row.reviewed_note = note
        row.promoted_channel_id = channel_id
        db.commit()

        # Backfill the channel's videos as `sources` rows + snapshot initial
        # video stats. Wrapped in a try/except so a YouTube API hiccup never
        # rolls back the approval — the admin can re-run via /admin/scout/
        # refresh-videos to recover.
        enumerate_result: dict[str, Any] | None = None
        if channel_id and row.platform == "youtube":
            channel_obj = db.get(Channel, channel_id)
            if channel_obj is not None:
                try:
                    enumerate_result = refresh_channel_videos(db, channel_obj, full_backfill=True)
                except Exception as e:
                    logger.warning(
                        "Post-approval video enumeration failed for channel %s: %s",
                        channel_id,
                        e,
                    )
                    enumerate_result = {"error": str(e)}

        return {
            "ok": True,
            "status": "approved",
            "candidate_id": str(row.id),
            "promoted_channel_id": str(channel_id) if channel_id else None,
            "wiki_page_created": channel_id is not None,
            "videos_enumerated": enumerate_result,
        }

    elif row.kind == "video":
        # Promote video: insert into sources. Try to link channel_id by parent.
        parent_channel_id = None
        if row.channel_external_id:
            parent = db.execute(
                select(Channel.channel_id).where(
                    Channel.platform == row.platform,
                    Channel.external_id == row.channel_external_id,
                )
            ).first()
            if parent:
                parent_channel_id = parent[0]

        src_stmt = (
            pg_insert(Source)
            .values(
                channel_id=parent_channel_id,
                source_type="youtube",
                title=row.title,
                creator_name=None,
                canonical_url=row.url,
                approved_flag=True,
                ingestion_status="pending",
            )
            .on_conflict_do_nothing(index_elements=["canonical_url"])
            .returning(Source.source_id)
        )
        src_result = db.execute(src_stmt).first()
        source_id = src_result[0] if src_result else None

        row.status = "approved"
        row.reviewed_at = datetime.now(UTC)
        row.reviewed_by = reviewed_by
        row.reviewed_note = note
        db.commit()

        return {
            "ok": True,
            "status": "approved",
            "candidate_id": str(row.id),
            "promoted_source_id": str(source_id) if source_id else None,
            "linked_channel_id": (str(parent_channel_id) if parent_channel_id else None),
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported candidate kind: {row.kind}")


# ---------------------------------------------------------------------------
# POST — reject
# ---------------------------------------------------------------------------


@router.post(
    "/admin/recon/candidates/{candidate_id}/reject",
    dependencies=[Depends(require_admin)],
)
def reject_candidate(
    candidate_id: UUID,
    body: dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
):
    row = db.get(ScoutCandidate, candidate_id)
    if not row:
        raise HTTPException(status_code=404, detail="Candidate not found")

    row.status = "rejected"
    row.reviewed_at = datetime.now(UTC)
    row.reviewed_by = body.get("reviewed_by") or "admin"
    row.reviewed_note = body.get("note")
    db.commit()

    return {
        "ok": True,
        "status": "rejected",
        "candidate_id": str(row.id),
    }


# ---------------------------------------------------------------------------
# Small stats helper for sanity checks
# ---------------------------------------------------------------------------


@router.get("/admin/recon/stats", dependencies=[Depends(require_admin)])
def stats(db: Session = Depends(get_db)):
    rows = (
        db.query(ScoutCandidate.status, ScoutCandidate.kind, func.count())
        .group_by(ScoutCandidate.status, ScoutCandidate.kind)
        .all()
    )
    by_status: dict[str, dict[str, int]] = {}
    for status, kind, n in rows:
        by_status.setdefault(status, {})[kind] = n
    return {"by_status": by_status}


# ---------------------------------------------------------------------------
# POST — daily Scout refresh job
# ---------------------------------------------------------------------------


@router.post(
    "/admin/scout/refresh-videos",
    dependencies=[Depends(require_admin)],
)
def refresh_videos(
    skip_stats: bool = Query(default=False),
    skip_enumerate: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Daily cron entry point.

    Runs two jobs in sequence:
      1. Incremental video enumerate across every active YouTube channel —
         picks up any new uploads since the last run.
      2. Stats refresh across every YouTube source — appends a row to
         video_metrics so we can track view velocity / detect breakouts.

    Both jobs are idempotent. Use `?skip_stats=true` to do enumerate only,
    or `?skip_enumerate=true` to do stats only.
    """
    enumerate_result: dict[str, Any] | None = None
    stats_result: dict[str, Any] | None = None

    if not skip_enumerate:
        enumerate_result = refresh_all_channels_incremental(db)
    if not skip_stats:
        stats_result = refresh_all_video_stats(db)

    return {
        "ok": True,
        "enumerate": enumerate_result,
        "stats": stats_result,
    }


# ---------------------------------------------------------------------------
# POST — per-channel ad-hoc refresh
# ---------------------------------------------------------------------------


def _resolve_channel(db: Session, channel_ref: str) -> Channel:
    """Resolve a channel by UUID or slug; 404 if neither matches."""
    try:
        ch = db.get(Channel, UUID(channel_ref))
        if ch:
            return ch
    except ValueError:
        pass
    ch = db.execute(select(Channel).where(Channel.slug == channel_ref)).scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail=f"Channel not found: {channel_ref}")
    return ch


@router.post(
    "/admin/scout/channels/{channel_ref}/refresh-videos",
    dependencies=[Depends(require_admin)],
)
def refresh_one_channel_videos(
    channel_ref: str,
    full_backfill: bool = Query(default=False),
    max_results: int = Query(default=200, ge=1, le=15000),
    db: Session = Depends(get_db),
):
    """Enumerate one channel's uploads and snapshot per-video stats.

    `channel_ref` accepts UUID or slug. `full_backfill=true` ignores the
    incremental cursor and walks newest-first up to `max_results` videos.
    `max_results` clamps to [1, 15000] (the youtube_api helper's hard cap,
    sized for broadcaster archives).
    """
    channel = _resolve_channel(db, channel_ref)
    result = refresh_channel_videos(db, channel, max_results=max_results, full_backfill=full_backfill)
    return {"ok": True, **result}


# ---------------------------------------------------------------------------
# POST — daily channel stats refresh
# ---------------------------------------------------------------------------


@router.post(
    "/admin/scout/refresh-channel-stats",
    dependencies=[Depends(require_admin)],
)
def refresh_channel_stats(db: Session = Depends(get_db)):
    """Daily cron entry point — snapshot channel popularity into channel_metrics.

    Cheap (~1 quota unit per 50 channels — 3 units for the projected ~150
    channel scale). Kept on its own endpoint so the channel-stats snapshot
    runs even if the heavier /admin/scout/refresh-videos job fails.
    """
    result = refresh_all_channel_stats(db)
    return {"ok": True, **result}


# ---------------------------------------------------------------------------
# GET — channel coverage audit
# ---------------------------------------------------------------------------


@router.get("/admin/scout/channel-coverage")
def channel_coverage(
    only_gaps: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Per-channel reconciliation: YouTube's reported video count (from the
    most recent `channel_metrics` snapshot) vs the number of `sources` rows
    we've ingested per channel.

    `?only_gaps=true` filters to channels where ingested < reported. Pure DB
    read — no YouTube API calls. Freshness depends on the daily
    /admin/scout/refresh-channel-stats cron keeping channel_metrics current.

    Read-only — matches the unauthenticated pattern of other inspection
    endpoints (/admin/pipeline, /admin/sync-status) so the dev-only admin UI
    can fetch without juggling X-Admin-Key.
    """
    result = audit_channel_coverage(db)
    if only_gaps:
        filtered = [r for r in result["per_channel"] if (r.get("gap") or 0) > 0]
        result["per_channel"] = filtered
    return {"ok": True, **result}
