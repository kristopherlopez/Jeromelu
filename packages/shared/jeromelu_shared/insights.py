"""Insights generation utilities — shared logic for all article generators."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from jeromelu_shared.db import Claim, KnowledgeBase, Person, PlayerRound, Source
from jeromelu_shared.llm import chat_text, get_embeddings
from jeromelu_shared.rag import BASE_PROMPT, TEMPERATURE_ADDONS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Article type registry
# ---------------------------------------------------------------------------

ARTICLE_TYPES = {
    "tips": "article_tips",
    "totw": "article_totw",
    "trades": "article_trades",
    "captains": "article_captains",
    "stocks": "article_stocks",
    "consensus": "article_consensus",
}

# System prompt addons per article type (appended after BASE_PROMPT context)
ARTICLE_PROMPTS = {
    "article_tips": (
        "Write a SuperCoach round preview for the upcoming round. "
        "Cover: top captain picks, key trade targets, players to avoid, and any matchup edges. "
        "Be opinionated — rank your picks, don't just list them. Use the data provided. "
        "Write in markdown with clear sections. Keep it punchy, 600-800 words."
    ),
    "article_totw": (
        "Pick the Team of the Week based on last round's scores. "
        "Select one player per SuperCoach position (FLB, CTW x2, 5/8, HFB, HOK, FRF x2, 2RF x2, FLX). "
        "Justify each pick briefly. Call out any surprise performers. "
        "Write in markdown. Keep it punchy, 500-700 words."
    ),
    "article_trades": (
        "Identify the best trade targets for this round. "
        "Cover players to buy (underpriced, rising form) and sell (overpriced, declining). "
        "Use price data, breakevens, and podcast consensus. Rank your top 3 buys and top 3 sells. "
        "Write in markdown. Keep it punchy, 500-700 words."
    ),
    "article_captains": (
        "Rank the top captain picks for this round. "
        "Consider recent form, opposition matchups, and what the podcasts are saying. "
        "Give a top 5 with conviction levels. Be decisive — pick a clear #1. "
        "Write in markdown. Keep it punchy, 400-600 words."
    ),
    "article_stocks": (
        "Write a Stocks Up / Stocks Down column. "
        "Identify 3-5 players whose value is rising (form, price, sentiment) and 3-5 falling. "
        "Use score trends, price movement, and shifts in podcast consensus. "
        "Write in markdown. Keep it punchy, 500-700 words."
    ),
    "article_consensus": (
        "Write a Podcast Consensus Report for this round. "
        "Compare what different SuperCoach podcasts are saying about key players. "
        "Where do they agree? Where do they diverge? Who's being talked about most? "
        "Name the sources. Write in markdown. Keep it punchy, 600-800 words."
    ),
}

# ---------------------------------------------------------------------------
# Data query helpers
# ---------------------------------------------------------------------------


def get_current_round(db: Session, season: int) -> int:
    """Determine the current round from the latest claim data."""
    return (db.query(func.max(Claim.effective_round)).filter(Claim.season == season).scalar()) or 0


# NOTE: query_round_claims / query_claim_consensus reference Claim.subject_entity_id
# which no longer exists on the model — entity links moved to ClaimAssociation in
# migration 036. These functions are dormant (only called by scripts/insights/
# generate_round_tips.py) and need rewriting to JOIN through ClaimAssociation.
# Tracked as TASK-53. The five pyright: ignore markers below are scoped to the
# attribute-access errors that the live Claim model raises.
def query_round_claims(
    db: Session,
    round_num: int,
    season: int,
    claim_types: list[str] | None = None,
) -> dict[str, list[dict]]:
    """Query claims for a round, grouped by player entity_id.

    Returns: {entity_id_str: [{"claim_type": ..., "claim_text": ..., "source_id": ..., ...}, ...]}
    """
    q = db.query(Claim).filter(
        Claim.effective_round == round_num,
        Claim.season == season,
        Claim.subject_entity_id.isnot(None),  # pyright: ignore[reportAttributeAccessIssue]  # Claim.subject_entity_id removed in migration 036 → TASK-53
    )
    if claim_types:
        q = q.filter(Claim.claim_type.in_(claim_types))

    claims = q.all()

    grouped: dict[str, list[dict]] = {}
    for c in claims:
        eid = str(c.subject_entity_id)  # pyright: ignore[reportAttributeAccessIssue]  # Claim.subject_entity_id removed in migration 036 → TASK-53
        grouped.setdefault(eid, []).append(
            {
                "claim_id": str(c.claim_id),
                "claim_type": c.claim_type,
                "claim_text": c.claim_text,
                "strength": c.strength,
                "polarity": c.polarity,
                "source_document_id": str(c.document_id) if c.document_id else None,
            }
        )

    return grouped


def query_claim_consensus(
    db: Session,
    round_num: int,
    season: int,
) -> dict[str, dict[str, int]]:
    """Aggregate claim counts per player per claim_type.

    Returns: {entity_id_str: {"buy": N, "sell": N, "hold": N, "captain": N, "avoid": N}}
    """
    rows = (
        db.query(
            Claim.subject_entity_id,  # pyright: ignore[reportAttributeAccessIssue]  # Claim.subject_entity_id removed in migration 036 → TASK-53
            Claim.claim_type,
            func.count().label("cnt"),
        )
        .filter(
            Claim.effective_round == round_num,
            Claim.season == season,
            Claim.subject_entity_id.isnot(None),  # pyright: ignore[reportAttributeAccessIssue]  # Claim.subject_entity_id removed in migration 036 → TASK-53
        )
        .group_by(Claim.subject_entity_id, Claim.claim_type)  # pyright: ignore[reportAttributeAccessIssue]  # Claim.subject_entity_id removed in migration 036 → TASK-53
        .all()
    )

    result: dict[str, dict[str, int]] = {}
    for entity_id, claim_type, cnt in rows:
        eid = str(entity_id)
        if eid not in result:
            result[eid] = {"buy": 0, "sell": 0, "hold": 0, "captain": 0, "avoid": 0}
        if claim_type in result[eid]:
            result[eid][claim_type] = cnt

    return result


def query_top_players(
    db: Session,
    round_num: int,
    season: int,
    position: str | None = None,
    top_n: int | None = 20,
    order_by: str = "score",
) -> list[dict]:
    """Query top PlayerRound entries for a round with Person join.

    Returns list of dicts with player stats and person info.
    """
    q = (
        db.query(PlayerRound, Person)
        .outerjoin(
            Person,
            Person.canonical_name == PlayerRound.player_name,
        )
        .filter(
            PlayerRound.round == round_num,
            PlayerRound.season == season,
        )
    )

    if position:
        q = q.filter(PlayerRound.position == position)

    order_col = getattr(PlayerRound, order_by, PlayerRound.score)
    q = q.order_by(desc(order_col))

    if top_n:
        q = q.limit(top_n)

    results = []
    for pr, person in q.all():
        results.append(
            {
                "entity_id": str(person.person_id) if person else None,
                "player_name": pr.player_name,
                "team": pr.team,
                "position": pr.position,
                "score": pr.score,
                "price": pr.price,
                "breakeven": pr.breakeven,
                "season_avg": pr.season_avg,
                "three_rd_avg": pr.three_rd_avg,
                "five_rd_avg": pr.five_rd_avg,
                "round_price_change": pr.round_price_change,
                "season_price_change": pr.season_price_change,
                "magic_number": pr.magic_number,
                "base": pr.base,
                "ppm": pr.ppm,
                "minutes": pr.minutes,
                "opposition": pr.opposition,
            }
        )

    return results


def resolve_entity_names(db: Session, entity_ids: set[str]) -> dict[str, str]:
    """Map entity_id strings to canonical names (people only — typed lookup)."""
    if not entity_ids:
        return {}
    uuids = [uuid.UUID(eid) for eid in entity_ids]
    people = db.query(Person).filter(Person.person_id.in_(uuids)).all()
    return {str(p.person_id): p.canonical_name for p in people}


def resolve_sources_from_claims(db: Session, claim_ids: list[uuid.UUID]) -> list[dict]:
    """Find unique sources referenced by a set of claims."""
    if not claim_ids:
        return []

    doc_ids = (
        db.query(Claim.document_id)
        .filter(Claim.claim_id.in_(claim_ids), Claim.document_id.isnot(None))
        .distinct()
        .all()
    )
    doc_id_set = {row[0] for row in doc_ids}
    if not doc_id_set:
        return []

    # SourceDocument -> Source
    from jeromelu_shared.db import SourceDocument

    source_ids = db.query(SourceDocument.source_id).filter(SourceDocument.document_id.in_(doc_id_set)).distinct().all()
    source_id_set = {row[0] for row in source_ids}
    if not source_id_set:
        return []

    sources = db.query(Source).filter(Source.source_id.in_(source_id_set)).all()
    return [{"source_id": str(s.source_id), "title": s.title, "creator_name": s.creator_name} for s in sources]


# ---------------------------------------------------------------------------
# Context builder — turn data into LLM-ready text
# ---------------------------------------------------------------------------


def build_player_context(
    players: list[dict],
    consensus: dict[str, dict[str, int]],
    claims: dict[str, list[dict]] | None = None,
) -> str:
    """Build a structured text block from player stats and claim data."""
    sections = []

    for p in players:
        eid = p.get("entity_id") or ""
        cons = consensus.get(eid, {})
        lines = [
            f"**{p['player_name']}** ({p['team']}, {p['position']})",
            f"  Score: {p['score']} | Price: ${p['price']:,}" if p.get("price") else f"  Score: {p['score']}",
            f"  Season Avg: {p['season_avg']} | 3rd Avg: {p['three_rd_avg']} | 5rd Avg: {p['five_rd_avg']}",
            f"  Breakeven: {p['breakeven']} | Price Change: {p['round_price_change']}",
            f"  Base: {p['base']} | PPM: {p['ppm']} | Minutes: {p['minutes']}",
            f"  vs {p['opposition']}",
        ]

        if any(cons.values()):
            cons_str = ", ".join(f"{k}: {v}" for k, v in cons.items() if v > 0)
            lines.append(f"  Podcast consensus: {cons_str}")

        if claims and eid in claims:
            claim_texts = [c["claim_text"] for c in claims[eid] if c.get("claim_text")][:3]
            if claim_texts:
                lines.append("  Key quotes:")
                for ct in claim_texts:
                    lines.append(f"    - {ct}")

        sections.append("\n".join(lines))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Article generation + storage
# ---------------------------------------------------------------------------


def generate_article(
    db: Session,
    kb_type: str,
    round_num: int,
    season: int,
    player_context: str,
    metadata: dict,
    claim_ids: list[uuid.UUID],
    temperature_mode: str = "sharp",
) -> KnowledgeBase:
    """Generate an article via LLM and store it in KnowledgeBase."""
    article_prompt = ARTICLE_PROMPTS.get(kb_type, "")
    addon = TEMPERATURE_ADDONS.get(temperature_mode, TEMPERATURE_ADDONS["sharp"])

    system_prompt = BASE_PROMPT.format(context=player_context) + "\n\n" + article_prompt + "\n\n" + addon

    user_prompt = f"Write the article for Round {round_num}, Season {season}."

    temp_map = {"straight": 0.3, "sharp": 0.6, "roast": 0.8}
    llm_temp = temp_map.get(temperature_mode, 0.6)

    logger.info("Generating %s for Round %d (temp=%s)", kb_type, round_num, temperature_mode)

    content = chat_text(system_prompt, user_prompt, temperature=llm_temp)

    # Build title
    type_label = kb_type.replace("article_", "").upper()
    title_map = {
        "article_tips": f"Round {round_num} SuperCoach Tips",
        "article_totw": f"Round {round_num} Team of the Week",
        "article_trades": f"Round {round_num} Trade Targets",
        "article_captains": f"Round {round_num} Captain Picks",
        "article_stocks": f"Round {round_num} Stocks Up / Stocks Down",
        "article_consensus": f"Round {round_num} Podcast Consensus",
    }
    title = title_map.get(kb_type, f"Round {round_num} {type_label}")

    return store_article(db, kb_type, title, content, round_num, season, metadata, claim_ids)


def store_article(
    db: Session,
    kb_type: str,
    title: str,
    content: str,
    round_num: int,
    season: int,
    metadata: dict,
    claim_ids: list[uuid.UUID],
) -> KnowledgeBase:
    """Store an article as a KnowledgeBase entry with embedding. Idempotent."""
    # Check for existing
    existing = (
        db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.kb_type == kb_type,
            KnowledgeBase.effective_round == round_num,
            KnowledgeBase.season == season,
        )
        .first()
    )

    # Generate embedding
    embedding = get_embeddings([content])[0]

    if existing:
        logger.info("Updating existing %s for Round %d", kb_type, round_num)
        existing.title = title
        existing.content = content
        existing.embedding = embedding
        existing.metadata_json = metadata
        existing.source_claim_ids = claim_ids
        existing.updated_at = datetime.now(UTC)
        db.commit()
        return existing

    entry = KnowledgeBase(
        kb_type=kb_type,
        title=title,
        content=content,
        embedding=embedding,
        effective_round=round_num,
        season=season,
        metadata_json=metadata,
        source_claim_ids=claim_ids,
    )
    db.add(entry)
    db.commit()

    logger.info("Stored %s for Round %d (kb_id=%s)", kb_type, round_num, entry.kb_id)
    return entry
