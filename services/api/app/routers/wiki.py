"""Wiki API — browsable, interlinked entity pages."""

import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from jeromelu_shared.db import Entity, WikiPage, WikiRevision

from ..deps import get_db

router = APIRouter()


def _page_summary(page: WikiPage) -> dict:
    return {
        "page_id": str(page.page_id),
        "slug": page.slug,
        "title": page.title,
        "page_type": page.page_type,
        "summary": page.summary,
        "status": page.status,
        "metadata_json": page.metadata_json or {},
        "updated_at": page.updated_at.isoformat(),
    }


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
    limit: int = Query(default=100, ge=1, le=500),
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

    return {
        "items": [_page_summary(p) for p in pages],
        "next_before": next_before,
    }


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

    # Load the entity
    entity = db.query(Entity).filter(Entity.entity_id == page.entity_id).first()

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
            "entity": {
                "entity_id": str(entity.entity_id),
                "canonical_name": entity.canonical_name,
                "entity_type": entity.entity_type,
                "metadata_json": entity.metadata_json,
            } if entity else None,
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
