"""Wiki API — browsable, interlinked entity pages."""

import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from jeromelu_shared.db import (
    Channel,
    Match,
    Person,
    Round,
    Team,
    Venue,
    WikiPage,
    WikiRevision,
)

from ..deps import get_db

router = APIRouter()


def _page_summary(
    page: WikiPage,
    logo_url: str | None = None,
    platform: str | None = None,
    channel_url: str | None = None,
) -> dict:
    return {
        "page_id": str(page.page_id),
        "slug": page.slug,
        "title": page.title,
        "page_type": page.page_type,
        "summary": page.summary,
        "status": page.status,
        "metadata_json": page.metadata_json or {},
        "updated_at": page.updated_at.isoformat(),
        "logo_url": logo_url,
        "platform": platform,
        "channel_url": channel_url,
    }


def _channel_meta_for_pages(
    db: Session, pages: list[WikiPage]
) -> dict[uuid.UUID, tuple[str | None, str | None, str | None]]:
    """Bulk-load (logo_url, platform, url) for channel-backed pages.
    Returns {page_id: (logo_url, platform, url)}. One extra query regardless of page count."""
    channel_page_ids = [p.page_id for p in pages if p.channel_id]
    if not channel_page_ids:
        return {}
    rows = (
        db.query(WikiPage.page_id, Channel.logo_url, Channel.platform, Channel.url)
        .join(Channel, Channel.channel_id == WikiPage.channel_id)
        .filter(WikiPage.page_id.in_(channel_page_ids))
        .all()
    )
    return {pid: (logo, platform, url) for pid, logo, platform, url in rows}


def _team_logos_for_pages(
    db: Session, pages: list[WikiPage]
) -> dict[uuid.UUID, str | None]:
    """Bulk-load logo_url for team-backed pages. One query regardless of count."""
    team_page_ids = [p.page_id for p in pages if p.team_id]
    if not team_page_ids:
        return {}
    rows = (
        db.query(WikiPage.page_id, Team.logo_url)
        .join(Team, Team.team_id == WikiPage.team_id)
        .filter(WikiPage.page_id.in_(team_page_ids))
        .all()
    )
    return {pid: logo for pid, logo in rows}


def _person_logos_for_pages(
    db: Session, pages: list[WikiPage]
) -> dict[uuid.UUID, str | None]:
    """Bulk-load image_url for person-backed pages.

    Sources nrl.com headshots populated by the
    ``/admin/players/refresh-nrlcom`` endpoint. One query regardless of count.
    """
    person_page_ids = [p.page_id for p in pages if p.person_id]
    if not person_page_ids:
        return {}
    rows = (
        db.query(WikiPage.page_id, Person.image_url)
        .join(Person, Person.person_id == WikiPage.person_id)
        .filter(WikiPage.page_id.in_(person_page_ids))
        .all()
    )
    return {pid: img for pid, img in rows}


def _revision_item(rev: WikiRevision) -> dict:
    return {
        "revision_id": str(rev.revision_id),
        "section_heading": rev.section_heading,
        "summary": rev.summary,
        "source_trigger": rev.source_trigger,
        "created_at": rev.created_at.isoformat(),
    }


def _extract_wiki_links(content: str) -> set[str]:
    """Extract all [[slug]] references from markdown content."""
    return set(re.findall(r"\[\[([^\]]+)\]\]", content))


@router.get("/wiki/pages")
def list_pages(
    page_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=2000),
    before: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """List wiki pages with optional filters."""
    query = db.query(WikiPage).order_by(WikiPage.updated_at.desc())

    if page_type:
        query = query.filter(WikiPage.page_type == page_type)
    if status:
        query = query.filter(WikiPage.status == status)
    if q:
        query = query.filter(WikiPage.title.ilike(f"%{q}%"))
    if before:
        query = query.filter(WikiPage.updated_at < before)

    pages = query.limit(limit + 1).all()

    has_more = len(pages) > limit
    if has_more:
        pages = pages[:limit]
    next_before = pages[-1].updated_at.isoformat() if pages and has_more else None

    channel_meta = _channel_meta_for_pages(db, pages)
    team_logos = _team_logos_for_pages(db, pages)
    person_logos = _person_logos_for_pages(db, pages)

    items = []
    for p in pages:
        logo, platform, url = channel_meta.get(p.page_id, (None, None, None))
        if logo is None:
            logo = team_logos.get(p.page_id) or person_logos.get(p.page_id)
        items.append(_page_summary(p, logo, platform, url))

    return {"items": items, "next_before": next_before}


@router.get("/wiki/recent-changes")
def recent_changes(
    limit: int = Query(default=30, ge=1, le=100),
    before: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Recent wiki revisions across all pages. Powers the wiki homepage activity feed."""
    query = (
        db.query(WikiRevision, WikiPage)
        .join(WikiPage, WikiPage.page_id == WikiRevision.page_id)
        .order_by(WikiRevision.created_at.desc())
    )

    if before:
        query = query.filter(WikiRevision.created_at < before)

    rows = query.limit(limit + 1).all()

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    next_before = rows[-1][0].created_at.isoformat() if rows and has_more else None

    items = [
        {
            "revision_id": str(rev.revision_id),
            "page_slug": page.slug,
            "page_title": page.title,
            "page_type": page.page_type,
            "section_heading": rev.section_heading,
            "summary": rev.summary,
            "created_at": rev.created_at.isoformat(),
        }
        for rev, page in rows
    ]

    return {"items": items, "next_before": next_before}


@router.get("/wiki/pages/{slug}")
def get_page(slug: str, db: Session = Depends(get_db)):
    """Full wiki page detail with recent revisions and linked page map."""
    page = db.query(WikiPage).filter(WikiPage.slug == slug).first()
    if not page:
        raise HTTPException(status_code=404, detail="Wiki page not found")

    # Phase 2: dispatch on whichever typed FK is set. wiki_pages now has typed
    # FKs (person_id, team_id, match_id, venue_id, round_id) alongside the legacy
    # entity_id (dropped in mig 037). Build a uniform `entity` response from
    # whichever typed row is loaded.
    person = (
        db.query(Person).filter(Person.person_id == page.person_id).first()
        if page.person_id else None
    )
    team = (
        db.query(Team).filter(Team.team_id == page.team_id).first()
        if page.team_id else None
    )
    match = (
        db.query(Match).filter(Match.match_id == page.match_id).first()
        if page.match_id else None
    )
    venue = (
        db.query(Venue).filter(Venue.venue_id == page.venue_id).first()
        if page.venue_id else None
    )
    round_row = (
        db.query(Round).filter(Round.round_id == page.round_id).first()
        if page.round_id else None
    )
    channel = (
        db.query(Channel).filter(Channel.channel_id == page.channel_id).first()
        if page.channel_id else None
    )

    if person:
        entity_block = {
            "entity_id": str(person.person_id),
            "canonical_name": person.canonical_name,
            "entity_type": page.page_type,
            "metadata_json": person.metadata_json,
        }
    elif team:
        entity_block = {
            "entity_id": str(team.team_id),
            "canonical_name": team.name,
            "entity_type": "team",
            "metadata_json": team.metadata_json,
        }
    elif match:
        entity_block = {
            "entity_id": str(match.match_id),
            "canonical_name": f"Round {match.round}, {match.season}",
            "entity_type": "match",
            "metadata_json": match.metadata_json,
        }
    elif venue:
        entity_block = {
            "entity_id": str(venue.venue_id),
            "canonical_name": venue.name,
            "entity_type": "venue",
            "metadata_json": venue.metadata_json,
        }
    elif round_row:
        entity_block = {
            "entity_id": str(round_row.round_id),
            "canonical_name": round_row.round_label,
            "entity_type": "round",
            "metadata_json": round_row.metadata_json,
        }
    else:
        entity_block = None

    # Recent revisions
    revisions = (
        db.query(WikiRevision)
        .filter(WikiRevision.page_id == page.page_id)
        .order_by(WikiRevision.created_at.desc())
        .limit(20)
        .all()
    )

    revision_count = (
        db.query(func.count(WikiRevision.revision_id))
        .filter(WikiRevision.page_id == page.page_id)
        .scalar()
    )

    # Resolve [[slug]] links in content to {slug: {title, page_type}}
    linked_slugs = _extract_wiki_links(page.content)
    linked_pages = {}
    if linked_slugs:
        linked = (
            db.query(WikiPage.slug, WikiPage.title, WikiPage.page_type)
            .filter(WikiPage.slug.in_(linked_slugs))
            .all()
        )
        linked_pages = {
            lp.slug: {"title": lp.title, "page_type": lp.page_type}
            for lp in linked
        }

    return {
        "page": {
            "page_id": str(page.page_id),
            "slug": page.slug,
            "title": page.title,
            "page_type": page.page_type,
            "content": page.content,
            "summary": page.summary,
            "status": page.status,
            "metadata_json": page.metadata_json,
            "entity": entity_block,
            "channel": {
                "channel_id": str(channel.channel_id),
                "slug": channel.slug,
                "platform": channel.platform,
                "name": channel.name,
                "url": channel.url,
                "description": channel.description,
                "quality_rating": channel.quality_rating,
                "tags": channel.tags or [],
                "active": channel.active,
                "logo_url": channel.logo_url,
                "last_polled_at": channel.last_polled_at.isoformat() if channel.last_polled_at else None,
            } if channel else None,
            "updated_at": page.updated_at.isoformat(),
            "revision_count": revision_count or 0,
        },
        "revisions": [_revision_item(r) for r in revisions],
        "linked_pages": linked_pages,
    }


@router.get("/wiki/pages/{slug}/revisions")
def get_page_revisions(
    slug: str,
    limit: int = Query(default=50, ge=1, le=200),
    before: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Full revision history for a wiki page."""
    page = db.query(WikiPage).filter(WikiPage.slug == slug).first()
    if not page:
        raise HTTPException(status_code=404, detail="Wiki page not found")

    query = (
        db.query(WikiRevision)
        .filter(WikiRevision.page_id == page.page_id)
        .order_by(WikiRevision.created_at.desc())
    )

    if before:
        query = query.filter(WikiRevision.created_at < before)

    revisions = query.limit(limit + 1).all()

    has_more = len(revisions) > limit
    if has_more:
        revisions = revisions[:limit]
    next_before = revisions[-1].created_at.isoformat() if revisions and has_more else None

    return {
        "page_title": page.title,
        "page_slug": page.slug,
        "items": [_revision_item(r) for r in revisions],
        "next_before": next_before,
    }
