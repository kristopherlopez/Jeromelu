"""Jaromelu status and round overview endpoints.

Internal note: the underlying `agent_runs` table still tracks per-internal-mode
activity (scout / scribe / analyst / stats / fixtures) for engineering telemetry,
but the user-facing API surfaces a single Jaromelu status — the wholesale model
(see docs/agents/crew/README.md). File name retained for git history; routes
have moved off the `/crew/...` prefix.
"""

from fastapi import APIRouter, Depends, Query
from jeromelu_shared.db import (
    AgentRun,
    Claim,
    ClaimAssociation,
    Person,
    Source,
    SourceDocument,
)
from sqlalchemy import desc, distinct, func
from sqlalchemy.orm import Session

from ..deps import get_db

router = APIRouter()


@router.get("/jaromelu/status")
def jaromelu_status(db: Session = Depends(get_db)):
    """Current single-character Jaromelu status for the homepage.

    Aggregates the most recent agent_runs row across all internal modes into
    a single status. The internal mode (e.g. scout / analyst) is reflected only
    in the action string — never as a separate agent identity in the response.
    """

    latest = db.query(AgentRun).order_by(desc(AgentRun.started_at)).first()

    status = "active" if (latest and latest.status == "running") else "dormant"

    last_activity = None
    if latest:
        last_activity = {
            "summary": latest.summary,
            "timestamp": (latest.ended_at or latest.started_at).isoformat(),
            "status": latest.status,
        }

    action = latest.summary if status == "active" and latest else None

    # Current round comes from claims — agent_runs is round-agnostic.
    latest_round = db.query(func.max(Claim.effective_round)).filter(Claim.effective_round.isnot(None)).scalar()

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
    """Full round overview — consensus and sources for the round.

    Note: agent_runs no longer carries round/season (it's engineering telemetry
    that doesn't generalise per-round), so `activity_log` is empty here. Round
    status is derived from whether claims exist for the round.
    """

    activity_log: list[dict] = []

    # Round status: claims exist => 'complete' (the round has signal); else 'pending'.
    has_claims = (
        db.query(Claim.claim_id).filter(Claim.effective_round == round_num, Claim.season == season).first() is not None
    )
    round_status = "complete" if has_claims else "pending"

    # 3. Claims for this round — consensus, joined via claim_associations
    claim_rows = (
        db.query(
            Claim.claim_type,
            Person.canonical_name,
            Person.person_id,
            func.count().label("cnt"),
        )
        .join(ClaimAssociation, ClaimAssociation.claim_id == Claim.claim_id)
        .join(Person, ClaimAssociation.person_id == Person.person_id)
        .filter(
            ClaimAssociation.role == "subject",
            Claim.effective_round == round_num,
            Claim.season == season,
        )
        .group_by(Claim.claim_type, Person.canonical_name, Person.person_id)
        .all()
    )

    # Aggregate per player
    player_consensus = {}
    for claim_type, name, entity_id, cnt in claim_rows:
        if name not in player_consensus:
            player_consensus[name] = {
                "entity_id": str(entity_id),
                "name": name,
                "buy": 0,
                "sell": 0,
                "hold": 0,
                "captain": 0,
                "avoid": 0,
                "breakout": 0,
                "matchup_edge": 0,
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
            **{
                k: type_totals.get(k, 0)
                for k in ["buy", "sell", "hold", "captain", "avoid", "breakout", "matchup_edge"]
            },
        },
        "consensus": consensus,
        "sources": sources,
        "activity_log": activity_log,
    }
