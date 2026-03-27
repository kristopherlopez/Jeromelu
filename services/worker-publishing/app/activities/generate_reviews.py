"""Review generation activity — compare past predictions against actual scores."""

import logging

from temporalio import activity

from jeromelu_shared.db import (
    Entity,
    Event,
    PlayerRound,
    Prediction,
    SessionLocal,
)

logger = logging.getLogger(__name__)


@activity.defn
async def generate_review_data() -> list[dict]:
    """Find predictions/decisions not yet reviewed and compare against player_rounds.

    Returns list of review dicts for the LLM:
    [{prediction_id, prediction_text, player_name, entity_id,
      actual_score, was_correct, round, season, claim_ids}]
    """
    session = SessionLocal()
    try:
        # Get prediction IDs already reviewed (events with type='review' and a related_prediction_id)
        reviewed_ids = set(
            r[0]
            for r in session.query(Event.related_prediction_id)
            .filter(Event.event_type == "review")
            .filter(Event.related_prediction_id.isnot(None))
            .all()
        )

        # Get unresolved or recently resolved predictions
        predictions = (
            session.query(Prediction)
            .filter(Prediction.subject_entity_id.isnot(None))
            .all()
        )

        # Filter to unreviewed
        unreviewed = [p for p in predictions if p.prediction_id not in reviewed_ids]

        if not unreviewed:
            logger.info("No unreviewed predictions found")
            return []

        # Load entities
        entity_ids = {p.subject_entity_id for p in unreviewed if p.subject_entity_id}
        entities = {}
        if entity_ids:
            for e in session.query(Entity).filter(Entity.entity_id.in_(entity_ids)).all():
                entities[e.entity_id] = e

        reviews = []
        for pred in unreviewed:
            entity = entities.get(pred.subject_entity_id)
            if not entity:
                continue

            # Try to find matching player_round data
            # Use metadata or event_window to determine which round to check
            player_name = entity.canonical_name
            player_id = entity.metadata_json.get("player_id") if entity.metadata_json else None

            if not player_id:
                continue

            # Find the most recent completed round for this player
            player_round = (
                session.query(PlayerRound)
                .filter(PlayerRound.player_id == player_id)
                .filter(PlayerRound.score.isnot(None))
                .order_by(PlayerRound.season.desc(), PlayerRound.round.desc())
                .first()
            )

            if not player_round:
                continue

            reviews.append({
                "prediction_id": str(pred.prediction_id),
                "prediction_text": pred.predicted_value_text or "",
                "prediction_type": pred.prediction_type or "",
                "player_name": player_name,
                "entity_id": str(pred.subject_entity_id),
                "actual_score": player_round.score,
                "actual_round": player_round.round,
                "actual_season": player_round.season,
                "claim_ids": [str(cid) for cid in (pred.evidence_claim_ids or [])],
            })

        logger.info("Found %d predictions ready for review", len(reviews))
        return reviews

    finally:
        session.close()
