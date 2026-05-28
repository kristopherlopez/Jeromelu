"""Squad roster and trade history endpoints."""

from fastapi import APIRouter, Depends, Query
from jeromelu_shared.db import (
    Claim,
    ClaimAssociation,
    KnowledgeBase,
    PlayerRound,
    SquadSlot,
    SquadTrade,
)
from pydantic import BaseModel
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..deps import get_db

router = APIRouter()


def _player_info(slot: SquadSlot, db: Session) -> dict:
    """Enrich a squad slot with PlayerRound stats."""
    info = {
        "entity_id": str(slot.player_entity_id) if slot.player_entity_id else None,
        "name": slot.player_name,
        "team": None,
        "price": None,
        "avg_score": None,
        "last_score": None,
        "price_change": None,
    }

    if not slot.player_entity_id:
        return info

    # Find matching PlayerRound by name (PlayerRound uses player_name, not entity_id)
    latest_pr = (
        db.query(PlayerRound)
        .filter(PlayerRound.player_name == slot.player_name)
        .order_by(desc(PlayerRound.season), desc(PlayerRound.round))
        .first()
    )

    if latest_pr:
        info["team"] = latest_pr.team
        info["price"] = latest_pr.price
        info["avg_score"] = latest_pr.season_avg
        info["last_score"] = latest_pr.score
        info["price_change"] = latest_pr.round_price_change

    return info


def _player_consensus(entity_id, current_round: int, season: int, db: Session) -> dict:
    """Get claim consensus for a player in the current round."""
    consensus = {"buy": 0, "sell": 0, "hold": 0, "captain": 0, "avoid": 0}

    if not entity_id:
        return consensus

    # Phase 2: claim subject lives on claim_associations.person_id (typed FK)
    # not Claim.subject_entity_id (polymorphic UUID). person_id == old entity_id
    # by migration 036 design.
    rows = (
        db.query(Claim.claim_type, func.count().label("cnt"))
        .join(ClaimAssociation, ClaimAssociation.claim_id == Claim.claim_id)
        .filter(
            ClaimAssociation.person_id == entity_id,
            ClaimAssociation.role == "subject",
            Claim.effective_round == current_round,
            Claim.season == season,
        )
        .group_by(Claim.claim_type)
        .all()
    )

    for claim_type, cnt in rows:
        if claim_type in consensus:
            consensus[claim_type] = cnt

    return consensus


@router.get("/squad")
def get_squad(
    season: int = Query(default=2026),
    db: Session = Depends(get_db),
):
    """Current squad roster with enriched player data."""

    slots = (
        db.query(SquadSlot)
        .filter(SquadSlot.active == True, SquadSlot.season == season)  # noqa: E712
        .order_by(SquadSlot.slot_index)
        .all()
    )

    if not slots:
        return {
            "roster": [],
            "captain": None,
            "recent_trades": [],
            "plan": None,
            "season": season,
            "current_round": 0,
        }

    # Determine current round from latest claim data
    current_round = (db.query(func.max(Claim.effective_round)).filter(Claim.season == season).scalar()) or 0

    # Build roster
    roster = []
    captain_pick = None

    for slot in slots:
        player = _player_info(slot, db)
        consensus = _player_consensus(slot.player_entity_id, current_round, season, db)

        entry = {
            "slot_index": slot.slot_index,
            "position": slot.position,
            "is_bench": 14 <= slot.slot_index <= 17,
            "player": player,
            "is_captain": slot.is_captain,
            "is_vice_captain": slot.is_vice_captain,
            "rationale": slot.rationale,
            "conviction": slot.conviction,
            "added_round": slot.added_round,
            "consensus": consensus,
        }
        roster.append(entry)

        if slot.is_captain:
            captain_pick = {
                "entity_id": str(slot.player_entity_id) if slot.player_entity_id else None,
                "name": slot.player_name,
                "rationale": slot.rationale,
                "conviction": slot.conviction,
            }

    # Recent trades (last 5)
    trades = (
        db.query(SquadTrade).filter(SquadTrade.season == season).order_by(desc(SquadTrade.created_at)).limit(5).all()
    )

    recent_trades = [
        {
            "round": t.round,
            "player_out": t.player_out_name,
            "player_in": t.player_in_name,
            "rationale": t.rationale,
            "created_at": t.created_at.isoformat(),
        }
        for t in trades
    ]

    # Plan — latest KnowledgeBase entry of type 'decision'
    plan_entry = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.kb_type == "decision", KnowledgeBase.season == season)
        .order_by(desc(KnowledgeBase.created_at))
        .first()
    )

    plan = None
    if plan_entry:
        plan = {
            "text": plan_entry.content,
            "round": plan_entry.effective_round,
        }

    return {
        "roster": roster,
        "captain": captain_pick,
        "recent_trades": recent_trades,
        "plan": plan,
        "season": season,
        "current_round": current_round,
    }


@router.get("/squad/history")
def squad_history(
    season: int = Query(default=2026),
    limit: int = Query(default=20, le=50),
    db: Session = Depends(get_db),
):
    """Full trade history."""
    trades = (
        db.query(SquadTrade)
        .filter(SquadTrade.season == season)
        .order_by(desc(SquadTrade.created_at))
        .limit(limit)
        .all()
    )

    return {
        "trades": [
            {
                "trade_id": str(t.trade_id),
                "round": t.round,
                "player_out": t.player_out_name,
                "player_in": t.player_in_name,
                "rationale": t.rationale,
                "created_at": t.created_at.isoformat(),
            }
            for t in trades
        ],
        "season": season,
    }


# --- Admin endpoints for manual squad management ---


class SlotInput(BaseModel):
    slot_index: int
    position: str
    player_name: str
    player_entity_id: str | None = None
    is_captain: bool = False
    is_vice_captain: bool = False
    rationale: str | None = None
    conviction: str = "medium"
    added_round: int | None = None


class SetSquadRequest(BaseModel):
    slots: list[SlotInput]
    season: int = 2026


@router.post("/admin/squad/set")
def set_squad(req: SetSquadRequest, db: Session = Depends(get_db)):
    """Set or replace the active squad. Deactivates existing slots."""
    import uuid as _uuid

    # Deactivate current squad
    db.query(SquadSlot).filter(
        SquadSlot.active,
        SquadSlot.season == req.season,
    ).update({"active": False})

    # Insert new slots
    for s in req.slots:
        slot = SquadSlot(
            position=s.position,
            slot_index=s.slot_index,
            player_entity_id=_uuid.UUID(s.player_entity_id) if s.player_entity_id else None,
            player_name=s.player_name,
            is_captain=s.is_captain,
            is_vice_captain=s.is_vice_captain,
            rationale=s.rationale,
            conviction=s.conviction,
            added_round=s.added_round,
            season=req.season,
            active=True,
        )
        db.add(slot)

    db.commit()
    return {"status": "ok", "slots_set": len(req.slots)}


class TradeInput(BaseModel):
    round: int
    player_out_name: str
    player_out_entity_id: str | None = None
    player_in_name: str
    player_in_entity_id: str | None = None
    rationale: str | None = None
    season: int = 2026


@router.post("/admin/squad/trade")
def record_trade(req: TradeInput, db: Session = Depends(get_db)):
    """Record a trade."""
    import uuid as _uuid

    trade = SquadTrade(
        round=req.round,
        season=req.season,
        player_out_entity_id=_uuid.UUID(req.player_out_entity_id) if req.player_out_entity_id else None,
        player_out_name=req.player_out_name,
        player_in_entity_id=_uuid.UUID(req.player_in_entity_id) if req.player_in_entity_id else None,
        player_in_name=req.player_in_name,
        rationale=req.rationale,
    )
    db.add(trade)
    db.commit()
    return {"status": "ok", "trade_id": str(trade.trade_id)}
