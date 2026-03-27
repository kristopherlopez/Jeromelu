"""Knowledge base generation activities — distill claims, stats, and events into curated KB entries."""

import logging
import uuid
from datetime import datetime, timezone

from temporalio import activity

from jeromelu_shared.db import (
    Claim,
    Entity,
    Event,
    KnowledgeBase,
    PlayerRound,
    SessionLocal,
    Source,
    SourceDocument,
)
from jeromelu_shared.llm import chat_json, get_embeddings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts for KB generation
# ---------------------------------------------------------------------------

PLAYER_SUMMARY_PROMPT = """\
You are JeromeLu's knowledge curator. Given claims and stats about an NRL SuperCoach player, \
write a concise summary paragraph that captures:
- Current form and recent scores
- Price trajectory, breakeven, and value assessment
- Consensus view across sources (buy/sell/hold sentiment)
- Key risks and upside

Write in third person, factual tone. Use SuperCoach jargon naturally. Max 150 words.

Return JSON: {"title": "Player Name — Round X Summary", "content": "summary text"}
"""

ROUND_BRIEF_PROMPT = """\
You are JeromeLu's knowledge curator. Given claims about an upcoming NRL round, \
write a brief overview covering:
- Key matchups and headline games
- Teams on bye
- Notable injury/selection news
- Weather or conditions if mentioned

Factual, concise. Max 150 words.

Return JSON: {"title": "Round X Brief", "content": "brief text"}
"""

OPINION_PROMPT = """\
You are JeromeLu, an opinionated NRL SuperCoach analyst. Given claims about a player, \
form YOUR opinion. Take a clear stance (bullish, bearish, or neutral-with-caveat).

Write in first person. Be specific about why. Reference data points. Max 100 words.

Return JSON: {"title": "Opinion: Player Name", "content": "opinion text"}
"""

SOURCE_DIGEST_PROMPT = """\
You are JeromeLu's knowledge curator. Given claims extracted from a single source, \
write a one-paragraph digest summarizing what the source said.

Include the source creator's name. Mention key player calls. Max 100 words.

Return JSON: {"title": "Source: Creator — Title", "content": "digest text"}
"""


@activity.defn
async def generate_player_summaries() -> dict:
    """Generate or update player_summary KB entries for players with recent claims."""
    session = SessionLocal()
    try:
        # Find player entities with claims
        player_entities = (
            session.query(Entity)
            .filter(Entity.entity_type == "player")
            .all()
        )

        generated = 0
        for entity in player_entities:
            # Get recent claims for this player
            claims = (
                session.query(Claim)
                .filter(Claim.subject_entity_id == entity.entity_id)
                .order_by(Claim.extracted_at.desc())
                .limit(20)
                .all()
            )
            if not claims:
                continue

            # Get latest player round stats
            player_id = entity.metadata_json.get("player_id") if entity.metadata_json else None
            stats_text = ""
            if player_id:
                pr = (
                    session.query(PlayerRound)
                    .filter(PlayerRound.player_id == player_id)
                    .filter(PlayerRound.score.isnot(None))
                    .order_by(PlayerRound.season.desc(), PlayerRound.round.desc())
                    .first()
                )
                if pr:
                    stats_text = (
                        f"Latest stats (Rd {pr.round}, {pr.season}): "
                        f"Score {pr.score}, Price ${pr.price}, BE {pr.breakeven}, "
                        f"PPM {pr.ppm:.2f}" if pr.ppm else ""
                    )

            claims_text = "\n".join(
                f"- [{c.claim_type}] {c.claim_text} (strength: {c.strength}, polarity: {c.polarity})"
                for c in claims
            )

            user_prompt = f"Player: {entity.canonical_name}\n\n{stats_text}\n\nClaims:\n{claims_text}"

            try:
                result = chat_json(PLAYER_SUMMARY_PROMPT, user_prompt)
            except Exception:
                logger.exception("LLM failed for player summary: %s", entity.canonical_name)
                continue

            claim_ids = [c.claim_id for c in claims]
            round_num = claims[0].effective_round
            season = claims[0].season

            _upsert_kb_entry(
                session,
                kb_type="player_summary",
                subject_entity_id=entity.entity_id,
                title=result.get("title", f"{entity.canonical_name} Summary"),
                content=result.get("content", ""),
                source_claim_ids=claim_ids,
                effective_round=round_num,
                season=season,
            )
            generated += 1

        session.commit()
        logger.info("Generated %d player summaries", generated)
        return {"player_summaries": generated}

    except Exception:
        session.rollback()
        logger.exception("Failed generating player summaries")
        raise
    finally:
        session.close()


@activity.defn
async def generate_round_briefs() -> dict:
    """Generate round_brief KB entries from round-specific claims."""
    session = SessionLocal()
    try:
        # Find the most recent round/season with claims
        latest = (
            session.query(Claim.effective_round, Claim.season)
            .filter(Claim.effective_round.isnot(None))
            .order_by(Claim.season.desc(), Claim.effective_round.desc())
            .first()
        )
        if not latest:
            return {"round_briefs": 0}

        round_num, season = latest

        # Get all claims for this round
        claims = (
            session.query(Claim)
            .filter(Claim.effective_round == round_num, Claim.season == season)
            .all()
        )
        if not claims:
            return {"round_briefs": 0}

        # Load entity names for context
        entity_ids = {c.subject_entity_id for c in claims if c.subject_entity_id}
        entities = {}
        if entity_ids:
            for e in session.query(Entity).filter(Entity.entity_id.in_(entity_ids)).all():
                entities[e.entity_id] = e.canonical_name

        claims_text = "\n".join(
            f"- [{c.claim_type}] {entities.get(c.subject_entity_id, 'Unknown')}: {c.claim_text}"
            for c in claims
        )

        user_prompt = f"Round {round_num}, Season {season}\n\nClaims:\n{claims_text}"

        try:
            result = chat_json(ROUND_BRIEF_PROMPT, user_prompt)
        except Exception:
            logger.exception("LLM failed for round brief")
            return {"round_briefs": 0}

        _upsert_kb_entry(
            session,
            kb_type="round_brief",
            subject_entity_id=None,
            title=result.get("title", f"Round {round_num} Brief"),
            content=result.get("content", ""),
            source_claim_ids=[c.claim_id for c in claims],
            effective_round=round_num,
            season=season,
        )

        session.commit()
        logger.info("Generated round brief for Round %d", round_num)
        return {"round_briefs": 1}

    except Exception:
        session.rollback()
        logger.exception("Failed generating round briefs")
        raise
    finally:
        session.close()


@activity.defn
async def generate_decisions_log() -> dict:
    """Create decision KB entries from JeromeLu's action/prediction events with outcomes."""
    session = SessionLocal()
    try:
        # Find action/prediction events not yet in KB
        existing_hashes = set(
            r[0] for r in session.query(KnowledgeBase.title)
            .filter(KnowledgeBase.kb_type == "decision")
            .all()
        )

        events = (
            session.query(Event)
            .filter(Event.event_type.in_(["action", "prediction"]))
            .order_by(Event.created_at.desc())
            .limit(50)
            .all()
        )

        generated = 0
        for ev in events:
            title = f"Decision: {ev.display_text[:60]}"
            if title in existing_hashes:
                continue

            # Try to find outcome data for related entities
            outcome_text = ""
            if ev.related_entity_ids:
                for eid in ev.related_entity_ids[:3]:
                    entity = session.query(Entity).get(eid)
                    if not entity:
                        continue
                    player_id = entity.metadata_json.get("player_id") if entity.metadata_json else None
                    if player_id:
                        pr = (
                            session.query(PlayerRound)
                            .filter(PlayerRound.player_id == player_id)
                            .filter(PlayerRound.score.isnot(None))
                            .order_by(PlayerRound.season.desc(), PlayerRound.round.desc())
                            .first()
                        )
                        if pr:
                            outcome_text += f" {entity.canonical_name} scored {pr.score} in Rd {pr.round}."

            content = ev.display_text
            if outcome_text:
                content += f" Outcome:{outcome_text}"

            kb = KnowledgeBase(
                kb_type="decision",
                title=title,
                content=content,
                source_claim_ids=ev.related_claim_ids or [],
                metadata_json={"event_id": str(ev.event_id), "event_type": ev.event_type},
            )
            session.add(kb)
            generated += 1

        session.commit()
        logger.info("Generated %d decision entries", generated)
        return {"decisions": generated}

    except Exception:
        session.rollback()
        logger.exception("Failed generating decisions log")
        raise
    finally:
        session.close()


@activity.defn
async def generate_player_opinions() -> dict:
    """Generate opinion KB entries — JeromeLu's opinionated stance on players."""
    session = SessionLocal()
    try:
        # Find players with enough claims to form an opinion (3+)
        from sqlalchemy import func

        player_claim_counts = (
            session.query(Claim.subject_entity_id, func.count(Claim.claim_id))
            .filter(Claim.subject_entity_id.isnot(None))
            .group_by(Claim.subject_entity_id)
            .having(func.count(Claim.claim_id) >= 3)
            .all()
        )

        generated = 0
        for entity_id, _ in player_claim_counts:
            entity = session.query(Entity).get(entity_id)
            if not entity or entity.entity_type != "player":
                continue

            claims = (
                session.query(Claim)
                .filter(Claim.subject_entity_id == entity_id)
                .order_by(Claim.extracted_at.desc())
                .limit(15)
                .all()
            )

            claims_text = "\n".join(
                f"- [{c.claim_type}] {c.claim_text} (strength: {c.strength}, polarity: {c.polarity})"
                for c in claims
            )

            user_prompt = f"Player: {entity.canonical_name}\n\nClaims:\n{claims_text}"

            try:
                result = chat_json(OPINION_PROMPT, user_prompt)
            except Exception:
                logger.exception("LLM failed for opinion: %s", entity.canonical_name)
                continue

            _upsert_kb_entry(
                session,
                kb_type="opinion",
                subject_entity_id=entity_id,
                title=result.get("title", f"Opinion: {entity.canonical_name}"),
                content=result.get("content", ""),
                source_claim_ids=[c.claim_id for c in claims],
                effective_round=claims[0].effective_round if claims else None,
                season=claims[0].season if claims else None,
            )
            generated += 1

        session.commit()
        logger.info("Generated %d player opinions", generated)
        return {"opinions": generated}

    except Exception:
        session.rollback()
        logger.exception("Failed generating player opinions")
        raise
    finally:
        session.close()


@activity.defn
async def generate_source_digests() -> dict:
    """Generate source_digest KB entries — per-source summaries."""
    session = SessionLocal()
    try:
        # Find sources with claims not yet digested
        existing_source_ids = set(
            r[0] for r in session.query(KnowledgeBase.metadata_json["source_id"].astext)
            .filter(KnowledgeBase.kb_type == "source_digest")
            .filter(KnowledgeBase.metadata_json["source_id"].isnot(None))
            .all()
        )

        # Get sources with claims via documents
        from sqlalchemy import func

        source_ids_with_claims = (
            session.query(SourceDocument.source_id)
            .join(Claim, Claim.document_id == SourceDocument.document_id)
            .group_by(SourceDocument.source_id)
            .having(func.count(Claim.claim_id) >= 1)
            .all()
        )

        generated = 0
        for (source_id,) in source_ids_with_claims:
            if str(source_id) in existing_source_ids:
                continue

            source = session.query(Source).get(source_id)
            if not source:
                continue

            # Get claims for this source via documents
            doc_ids = [d.document_id for d in source.documents]
            if not doc_ids:
                continue

            claims = (
                session.query(Claim)
                .filter(Claim.document_id.in_(doc_ids))
                .all()
            )
            if not claims:
                continue

            # Load entity names
            entity_ids = {c.subject_entity_id for c in claims if c.subject_entity_id}
            entities = {}
            if entity_ids:
                for e in session.query(Entity).filter(Entity.entity_id.in_(entity_ids)).all():
                    entities[e.entity_id] = e.canonical_name

            claims_text = "\n".join(
                f"- [{c.claim_type}] {entities.get(c.subject_entity_id, 'Unknown')}: {c.claim_text}"
                for c in claims
            )

            user_prompt = (
                f"Source: {source.title}\n"
                f"Creator: {source.creator_name or 'Unknown'}\n\n"
                f"Claims:\n{claims_text}"
            )

            try:
                result = chat_json(SOURCE_DIGEST_PROMPT, user_prompt)
            except Exception:
                logger.exception("LLM failed for source digest: %s", source.title)
                continue

            kb = KnowledgeBase(
                kb_type="source_digest",
                title=result.get("title", f"Source: {source.creator_name} — {source.title}"),
                content=result.get("content", ""),
                source_claim_ids=[c.claim_id for c in claims],
                metadata_json={"source_id": str(source_id)},
            )
            session.add(kb)
            generated += 1

        session.commit()
        logger.info("Generated %d source digests", generated)
        return {"source_digests": generated}

    except Exception:
        session.rollback()
        logger.exception("Failed generating source digests")
        raise
    finally:
        session.close()


@activity.defn
async def embed_kb_entries() -> dict:
    """Batch embed all KB entries that are missing embeddings."""
    session = SessionLocal()
    try:
        entries = (
            session.query(KnowledgeBase)
            .filter(KnowledgeBase.embedding.is_(None))
            .all()
        )

        if not entries:
            return {"embedded": 0}

        # Batch in groups of 50
        batch_size = 50
        total = 0
        for i in range(0, len(entries), batch_size):
            batch = entries[i : i + batch_size]
            texts = [f"{e.title}\n{e.content}" for e in batch]

            try:
                embeddings = get_embeddings(texts)
                for entry, emb in zip(batch, embeddings):
                    entry.embedding = emb
                total += len(batch)
            except Exception:
                logger.exception("Embedding batch %d failed", i)
                continue

        session.commit()
        logger.info("Embedded %d KB entries", total)
        return {"embedded": total}

    except Exception:
        session.rollback()
        logger.exception("Failed embedding KB entries")
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upsert_kb_entry(
    session,
    kb_type: str,
    subject_entity_id: uuid.UUID | None,
    title: str,
    content: str,
    source_claim_ids: list,
    effective_round: int | None = None,
    season: int | None = None,
):
    """Insert or update a KB entry, matching on kb_type + subject_entity_id + effective_round."""
    existing = (
        session.query(KnowledgeBase)
        .filter(
            KnowledgeBase.kb_type == kb_type,
            KnowledgeBase.subject_entity_id == subject_entity_id,
        )
    )
    if effective_round is not None:
        existing = existing.filter(KnowledgeBase.effective_round == effective_round)

    existing = existing.first()

    if existing:
        existing.title = title
        existing.content = content
        existing.source_claim_ids = [uuid.UUID(str(cid)) for cid in source_claim_ids]
        existing.effective_round = effective_round
        existing.season = season
        existing.updated_at = datetime.now(timezone.utc)
        existing.embedding = None  # Force re-embedding
    else:
        kb = KnowledgeBase(
            kb_type=kb_type,
            subject_entity_id=subject_entity_id,
            title=title,
            content=content,
            source_claim_ids=[uuid.UUID(str(cid)) for cid in source_claim_ids],
            effective_round=effective_round,
            season=season,
        )
        session.add(kb)
