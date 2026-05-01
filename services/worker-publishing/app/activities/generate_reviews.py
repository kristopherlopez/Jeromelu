"""Review generation activity — compare past predictions against actual scores."""

import logging

from sqlalchemy.orm import joinedload
from temporalio import activity

from jeromelu_shared.db import (
    Event,
    Person,
    PlayerRound,
    Prediction,
    PredictionAssociation,
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

        # Phase 2: subject lives on prediction_associations.person_id (typed FK).
        predictions = (
            session.query(Prediction)
            .join(
                PredictionAssociation,
                PredictionAssociation.prediction_id == Prediction.prediction_id,
            )
            .filter(
                PredictionAssociation.role == "subject",
                PredictionAssociation.person_id.isnot(None),
            )
            .options(joinedload(Prediction.associations))
            .all()
        )

        # Filter to unreviewed
        unreviewed = [p for p in predictions if p.prediction_id not in reviewed_ids]

        if not unreviewed:
            logger.info("No unreviewed predictions found")
            return []

        # Load subject persons
        person_ids = {
            a.person_id
            for p in unreviewed
            for a in p.associations
            if a.role == "subject" and a.person_id
        }
        people = {}
        if person_ids:
            for person in session.query(Person).filter(Person.person_id.in_(person_ids)).all():
                people[person.person_id] = person

        reviews = []
        for pred in unreviewed:
            subject_assoc = next(
                (a for a in pred.associations if a.role == "subject" and a.person_id),
                None,
            )
            if not subject_assoc:
                continue
            person = people.get(subject_assoc.person_id)
            if not person:
                continue

            player_name = person.canonical_name
            # supercoach_id was promoted to a column in mig 036; fall back to legacy
            # metadata_json keys (player_id / supercoach_id) for rows that predate
            # the promotion sweep.
            player_id = person.supercoach_id or (
                (person.metadata_json or {}).get("player_id")
                or (person.metadata_json or {}).get("supercoach_id")
            )

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
                "entity_id": str(person.person_id),
                "actual_score": player_round.score,
                "actual_round": player_round.round,
                "actual_season": player_round.season,
                "claim_ids": [str(cid) for cid in (pred.evidence_claim_ids or [])],
            })

        logger.info("Found %d predictions ready for review", len(reviews))
        return reviews

    finally:
        session.close()
