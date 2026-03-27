"""Consensus snapshot activity — aggregate claim sentiment per entity."""

import logging
from datetime import datetime, timezone

from temporalio import activity

from jeromelu_shared.db import (
    Claim,
    ConsensusSnapshot,
    Entity,
    SessionLocal,
)

logger = logging.getLogger(__name__)

BUY_TYPES = {"buy", "captain", "breakout"}
SELL_TYPES = {"sell", "avoid"}
HOLD_TYPES = {"hold"}


@activity.defn
async def update_consensus_snapshots() -> list[dict]:
    """Compute new consensus snapshots and return entities with flipped sentiment.

    Returns list of dicts: [{entity_id, canonical_name, old_dominant, new_dominant}]
    """
    session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # Get the latest snapshot time to find new claims since then
        latest_snapshot = (
            session.query(ConsensusSnapshot.time_bucket)
            .order_by(ConsensusSnapshot.time_bucket.desc())
            .first()
        )
        since = latest_snapshot[0] if latest_snapshot else datetime.min.replace(tzinfo=timezone.utc)

        # Get claims extracted since last snapshot
        new_claims = (
            session.query(Claim)
            .filter(Claim.extracted_at > since)
            .filter(Claim.subject_entity_id.isnot(None))
            .all()
        )

        if not new_claims:
            logger.info("No new claims since last snapshot")
            return []

        # Group by entity
        entity_claims: dict[str, list[Claim]] = {}
        for claim in new_claims:
            eid = str(claim.subject_entity_id)
            entity_claims.setdefault(eid, []).append(claim)

        # Load entity names
        entity_ids = list(entity_claims.keys())
        entities = {
            str(e.entity_id): e.canonical_name
            for e in session.query(Entity).filter(
                Entity.entity_id.in_(entity_ids)
            ).all()
        }

        # Load previous snapshots for comparison
        prev_snapshots: dict[str, ConsensusSnapshot] = {}
        for snap in (
            session.query(ConsensusSnapshot)
            .filter(ConsensusSnapshot.subject_entity_id.in_(entity_ids))
            .order_by(ConsensusSnapshot.time_bucket.desc())
            .all()
        ):
            eid = str(snap.subject_entity_id)
            if eid not in prev_snapshots:
                prev_snapshots[eid] = snap

        flipped = []

        for eid, claims in entity_claims.items():
            buy_count = sum(1 for c in claims if c.claim_type in BUY_TYPES)
            sell_count = sum(1 for c in claims if c.claim_type in SELL_TYPES)
            hold_count = sum(1 for c in claims if c.claim_type in HOLD_TYPES)
            neutral_count = len(claims) - buy_count - sell_count - hold_count
            total = len(claims)

            consensus_score = max(buy_count, sell_count, hold_count) / total if total > 0 else 0.0

            snapshot = ConsensusSnapshot(
                subject_entity_id=eid,
                time_bucket=now,
                buy_count=buy_count,
                sell_count=sell_count,
                hold_count=hold_count,
                neutral_count=neutral_count,
                consensus_score=round(consensus_score, 3),
            )
            session.add(snapshot)

            # Detect sentiment flip
            prev = prev_snapshots.get(eid)
            if prev:
                old_dominant = _dominant(prev.buy_count, prev.sell_count, prev.hold_count)
                new_dominant = _dominant(buy_count, sell_count, hold_count)
                if old_dominant != new_dominant and old_dominant and new_dominant:
                    flipped.append({
                        "entity_id": eid,
                        "canonical_name": entities.get(eid, "Unknown"),
                        "old_dominant": old_dominant,
                        "new_dominant": new_dominant,
                    })

        session.commit()
        logger.info(
            "Updated %d consensus snapshots, %d sentiment flips detected",
            len(entity_claims),
            len(flipped),
        )
        return flipped

    except Exception:
        session.rollback()
        logger.exception("Failed to update consensus snapshots")
        raise
    finally:
        session.close()


def _dominant(buy: int, sell: int, hold: int) -> str | None:
    """Return the dominant sentiment, or None if all zero."""
    if buy == sell == hold == 0:
        return None
    counts = {"buy": buy, "sell": sell, "hold": hold}
    return max(counts, key=counts.get)  # type: ignore[arg-type]
