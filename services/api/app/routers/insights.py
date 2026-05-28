"""Insights API — serve generated analytical articles."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from jeromelu_shared.db import KnowledgeBase, Source
from jeromelu_shared.db.models import SourceDocument
from jeromelu_shared.insights import ARTICLE_TYPES
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..deps import get_db

router = APIRouter()

# All article kb_type values
_ARTICLE_KB_TYPES = set(ARTICLE_TYPES.values())


def _strip_prefix(kb_type: str) -> str:
    """article_tips -> tips"""
    return kb_type.removeprefix("article_")


@router.get("/insights")
def list_insights(
    article_type: str | None = Query(
        default=None, description="Filter by type: tips, totw, trades, captains, stocks, consensus"
    ),
    round: int | None = Query(default=None, alias="round"),
    season: int = Query(default=2026),
    limit: int = Query(default=20, le=50),
    before: datetime | None = Query(default=None, description="Cursor: created_at before this timestamp"),
    db: Session = Depends(get_db),
):
    """List insight articles with optional filters and cursor pagination."""
    q = db.query(KnowledgeBase).filter(
        KnowledgeBase.kb_type.in_(_ARTICLE_KB_TYPES),
        KnowledgeBase.season == season,
    )

    if article_type:
        kb_type = ARTICLE_TYPES.get(article_type)
        if not kb_type:
            raise HTTPException(400, f"Unknown article_type: {article_type}")
        q = q.filter(KnowledgeBase.kb_type == kb_type)

    if round is not None:
        q = q.filter(KnowledgeBase.effective_round == round)

    if before:
        q = q.filter(KnowledgeBase.created_at < before)

    entries = q.order_by(desc(KnowledgeBase.created_at)).limit(limit).all()

    items = []
    for e in entries:
        meta = e.metadata_json or {}
        items.append(
            {
                "kb_id": str(e.kb_id),
                "article_type": _strip_prefix(e.kb_type),
                "title": e.title,
                "summary": (e.content or "")[:200],
                "effective_round": e.effective_round,
                "season": e.season,
                "created_at": e.created_at.isoformat(),
                "player_count": meta.get("player_count", 0),
            }
        )

    next_before = entries[-1].created_at.isoformat() if entries else None

    return {"items": items, "next_before": next_before}


@router.get("/insights/{kb_id}")
def get_insight(kb_id: str, db: Session = Depends(get_db)):
    """Get a single insight article with full content and source attribution."""
    try:
        uid = uuid.UUID(kb_id)
    except ValueError:
        raise HTTPException(400, "Invalid kb_id") from None

    entry = db.query(KnowledgeBase).filter(KnowledgeBase.kb_id == uid).first()
    if not entry or entry.kb_type not in _ARTICLE_KB_TYPES:
        raise HTTPException(404, "Article not found")

    # Resolve sources from claim IDs
    sources = []
    if entry.source_claim_ids:
        from jeromelu_shared.db import Claim

        doc_ids = (
            db.query(Claim.document_id)
            .filter(Claim.claim_id.in_(entry.source_claim_ids), Claim.document_id.isnot(None))
            .distinct()
            .all()
        )
        doc_id_set = {row[0] for row in doc_ids}

        if doc_id_set:
            source_ids = (
                db.query(SourceDocument.source_id).filter(SourceDocument.document_id.in_(doc_id_set)).distinct().all()
            )
            source_id_set = {row[0] for row in source_ids}

            if source_id_set:
                for s in db.query(Source).filter(Source.source_id.in_(source_id_set)).all():
                    sources.append(
                        {
                            "source_id": str(s.source_id),
                            "title": s.title,
                            "creator_name": s.creator_name,
                        }
                    )

    return {
        "kb_id": str(entry.kb_id),
        "article_type": _strip_prefix(entry.kb_type),
        "title": entry.title,
        "content": entry.content,
        "effective_round": entry.effective_round,
        "season": entry.season,
        "created_at": entry.created_at.isoformat(),
        "metadata": entry.metadata_json,
        "sources": sources,
    }
