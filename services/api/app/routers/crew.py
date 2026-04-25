"""Jaromelu status and round overview endpoints.

Internal note: the underlying `CrewActivity` table still tracks per-internal-mode
activity (scout / scribe / analyst / stats / fixtures) for engineering telemetry,
but the user-facing API surfaces a single Jaromelu status — the wholesale model
(see docs/agents/crew/README.md). File name retained for git history; routes
have moved off the `/crew/...` prefix.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, desc, distinct
from sqlalchemy.orm import Session

from jeromelu_shared.db import (
    CrewActivity,
    Claim,
    Source,
    SourceDocument,
    Entity,
)
from ..deps import get_db

router = APIRouter()


@router.get("/jaromelu/status")
def jaromelu_status(db: Session = Depends(get_db)):
    """Current single-character Jaromelu status for the homepage.

    Aggregates the most recent CrewActivity row across all internal modes into
    a single status. The internal mode (e.g. scout / analyst) is reflected only
    in the action string — never as a separate agent identity in the response.
    """

    latest = (
        db.query(CrewActivity)
        .order_by(desc(CrewActivity.created_at))
        .first()
    )

    if latest and latest.activity_type == "started":
        status = "active"
    else:
        status = "dormant"

    last_activity = None
    if latest:
        last_activity = {
            "summary": latest.summary,
            "timestamp": latest.created_at.isoformat(),
            "activity_type": latest.activity_type,
        }

    action = latest.summary if status == "active" and latest else None

    # Determine current round from latest crew activity or claims
    latest_round = (
        db.query(func.max(CrewActivity.round))
        .filter(CrewActivity.round.isnot(None))
        .scalar()
    )
    if not latest_round:
        latest_round = (
            db.query(func.max(Claim.effective_round))
            .filter(Claim.effective_round.isnot(None))
            .scalar()
        )

    return {
        "status": status,
        "action": action,
        "last_activity": last_activity,
        "current_round": latest_round or 0,
        "current_season": 2026,
    }


@router.get("/round/{round_num}")
def round_overview(
    round_num: int,
    season: int = Query(default=2026),
    db: Session = Depends(get_db),
):
    """Full round overview — Jaromelu's activity, consensus, sources."""

    # 1. Activity for this round (internal mode rows aggregate to a single Jaromelu timeline)
    activities = (
        db.query(CrewActivity)
        .filter(CrewActivity.round == round_num, CrewActivity.season == season)
        .order_by(desc(CrewActivity.created_at))
        .all()
    )

    activity_log = [
        {
            "activity_id": str(a.activity_id),
            "activity_type": a.activity_type,
            "summary": a.summary,
            "detail_json": a.detail_json or {},
            "created_at": a.created_at.isoformat(),
        }
        for a in activities
    ]

    # 2. Round status
    has_started = any(a.activity_type == "started" for a in activities)
    all_completed = all(
        a.activity_type in ("completed", "handoff")
        for a in activities
        if a.activity_type != "started"
    ) if activities else False

    if not activities:
        round_status = "pending"
    elif has_started and not all_completed:
        round_status = "in_progress"
    else:
        round_status = "complete"

    # 3. Claims for this round — consensus
    claim_rows = (
        db.query(
            Claim.claim_type,
            Entity.canonical_name,
            Entity.entity_id,
            func.count().label("cnt"),
        )
        .join(Entity, Claim.subject_entity_id == Entity.entity_id)
        .filter(Claim.effective_round == round_num, Claim.season == season)
        .group_by(Claim.claim_type, Entity.canonical_name, Entity.entity_id)
        .all()
    )

    # Aggregate per player
    player_consensus = {}
    for claim_type, name, entity_id, cnt in claim_rows:
        if name not in player_consensus:
            player_consensus[name] = {
                "entity_id": str(entity_id),
                "name": name,
                "buy": 0, "sell": 0, "hold": 0, "captain": 0,
                "avoid": 0, "breakout": 0, "matchup_edge": 0,
            }
        if claim_type in player_consensus[name]:
            player_consensus[name][claim_type] += cnt

    consensus = list(player_consensus.values())

    # Claim type totals
    type_totals = {}
    for claim_type, _, _, cnt in claim_rows:
        type_totals[claim_type] = type_totals.get(claim_type, 0) + cnt

    # 4. Sources for this round
    source_rows = (
        db.query(
            Source.source_id,
            Source.title,
            Source.creator_name,
            func.count(distinct(Claim.claim_id)).label("claim_count"),
        )
        .join(SourceDocument, Source.source_id == SourceDocument.source_id)
        .join(Claim, SourceDocument.document_id == Claim.document_id)
        .filter(Claim.effective_round == round_num, Claim.season == season)
        .group_by(Source.source_id, Source.title, Source.creator_name)
        .order_by(desc("claim_count"))
        .all()
    )

    sources = [
        {
            "source_id": str(s.source_id),
            "title": s.title,
            "creator_name": s.creator_name,
            "claim_count": s.claim_count,
        }
        for s in source_rows
    ]

    return {
        "round": round_num,
        "season": season,
        "status": round_status,
        "signal": {
            "total_claims": sum(type_totals.values()),
            **{k: type_totals.get(k, 0) for k in ["buy", "sell", "hold", "captain", "avoid", "breakout", "matchup_edge"]},
        },
        "consensus": consensus,
        "sources": sources,
        "activity_log": activity_log,
    }
