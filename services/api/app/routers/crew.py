"""Crew status and round overview endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, desc, distinct, case
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

AGENT_META = {
    "scout":    {"name": "Scout",    "icon": "\U0001F50D", "next_run": "Tonight 10PM"},
    "scribe":   {"name": "Scribe",   "icon": "\u270D\uFE0F",  "next_run": "When Scout finds videos"},
    "analyst":  {"name": "Analyst",  "icon": "\U0001F9E0", "next_run": "After Scribe finishes"},
    "stats":    {"name": "Stats",    "icon": "\U0001F4CA", "next_run": "Monday 6AM"},
    "fixtures": {"name": "Fixtures", "icon": "\U0001F3DF\uFE0F",  "next_run": "Thursday 6PM"},
}

AGENT_ORDER = ["scout", "scribe", "analyst", "stats", "fixtures"]


@router.get("/crew/status")
def crew_status(db: Session = Depends(get_db)):
    """Current status of each crew agent for the homepage."""

    # Get the latest activity for each agent
    latest_per_agent = {}
    for agent_id in AGENT_ORDER:
        row = (
            db.query(CrewActivity)
            .filter(CrewActivity.agent_id == agent_id)
            .order_by(desc(CrewActivity.created_at))
            .first()
        )
        latest_per_agent[agent_id] = row

    agents = []
    for agent_id in AGENT_ORDER:
        meta = AGENT_META[agent_id]
        row = latest_per_agent.get(agent_id)

        if row and row.activity_type == "started":
            status = "active"
        else:
            status = "dormant"

        last_activity = None
        if row:
            last_activity = {
                "summary": row.summary,
                "timestamp": row.created_at.isoformat(),
                "activity_type": row.activity_type,
            }

        agents.append({
            "id": agent_id,
            "name": meta["name"],
            "icon": meta["icon"],
            "status": status,
            "action": row.summary if status == "active" and row else None,
            "last_activity": last_activity,
            "next_run": meta["next_run"],
        })

    # Determine current round from latest crew activity or claims
    latest_round_row = (
        db.query(func.max(CrewActivity.round))
        .filter(CrewActivity.round.isnot(None))
        .scalar()
    )
    if not latest_round_row:
        latest_round_row = (
            db.query(func.max(Claim.effective_round))
            .filter(Claim.effective_round.isnot(None))
            .scalar()
        )

    return {
        "agents": agents,
        "current_round": latest_round_row or 0,
        "current_season": 2026,
    }


@router.get("/round/{round_num}")
def round_overview(
    round_num: int,
    season: int = Query(default=2026),
    db: Session = Depends(get_db),
):
    """Full round overview — crew activity, consensus, sources."""

    # 1. Crew activity for this round
    activities = (
        db.query(CrewActivity)
        .filter(CrewActivity.round == round_num, CrewActivity.season == season)
        .order_by(desc(CrewActivity.created_at))
        .all()
    )

    activity_log = [
        {
            "activity_id": str(a.activity_id),
            "agent_id": a.agent_id,
            "agent_name": a.agent_name,
            "activity_type": a.activity_type,
            "summary": a.summary,
            "detail_json": a.detail_json or {},
            "created_at": a.created_at.isoformat(),
        }
        for a in activities
    ]

    # Crew summary — count completed/failed per agent
    crew_summary = {}
    for a in activities:
        if a.agent_id not in crew_summary:
            crew_summary[a.agent_id] = {"completed": 0, "failed": 0, "name": a.agent_name}
        if a.activity_type == "completed":
            crew_summary[a.agent_id]["completed"] += 1
        elif a.activity_type == "failed":
            crew_summary[a.agent_id]["failed"] += 1

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
        "crew_summary": crew_summary,
        "signal": {
            "total_claims": sum(type_totals.values()),
            **{k: type_totals.get(k, 0) for k in ["buy", "sell", "hold", "captain", "avoid", "breakout", "matchup_edge"]},
        },
        "consensus": consensus,
        "sources": sources,
        "activity_log": activity_log,
    }
