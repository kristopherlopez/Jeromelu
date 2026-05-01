"""Consensus snapshot activity — aggregate claim sentiment per person subject."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import joinedload
from temporalio import activity

from jeromelu_shared.db import (
    Claim,
    ClaimAssociation,
    ConsensusSnapshot,
    Person,
    SessionLocal,
)

logger = logging.getLogger(__name__)

BUY_TYPES = {"buy", "captain", "breakout"}
SELL_TYPES = {"sell", "avoid"}
HOLD_TYPES = {"hold"}


@activity.defn
async def update_consensus_snapshots() -> list[dict]:
    """Compute new consensus snapshots and return entities with flipped sentiment.

    Returns list of dicts: [{entity_id, canonical_name, old_dominant, new_dominant}].
    Phase 2: subject lives on claim_associations.person_id (typed FK).
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

        # Get claims with person subjects extracted since last snapshot.
        new_claims = (
            session.query(Claim)
            .join(ClaimAssociation, ClaimAssociation.claim_id == Claim.claim_id)
            .filter(
                Claim.extracted_at > since,
                ClaimAssociation.role == "subject",
                ClaimAssociation.person_id.isnot(None),
            )
            .options(joinedload(Claim.associations))
            .all()
        )

        if not new_claims:
            logger.info("No new claims since last snapshot")
            return []

        # Group by subject person
        person_claims: dict[str, list[Claim]] = {}
        for claim in new_claims:
            for a in claim.associations:
                if a.role == "subject" and a.person_id:
                    pid = str(a.person_id)
                    person_claims.setdefault(pid, []).append(claim)
                    break  # one subject per claim

        # Load person names
        person_ids = list(person_claims.keys())
        people = {
            str(p.person_id): p.canonical_name
            for p in session.query(Person).filter(
                Person.person_id.in_(person_ids)
            ).all()
        }

        # Load previous snapshots for comparison (matched on person_id, the new typed FK)
        prev_snapshots: dict[str, ConsensusSnapshot] = {}
        for snap in (
            session.query(ConsensusSnapshot)
            .filter(ConsensusSnapshot.person_id.in_(person_ids))
            .order_by(ConsensusSnapshot.time_bucket.desc())
            .all()
        ):
            pid = str(snap.person_id)
            if pid not in prev_snapshots:
                prev_snapshots[pid] = snap

        flipped = []

        for pid, claims in person_claims.items():
            buy_count = sum(1 for c in claims if c.claim_type in BUY_TYPES)
            sell_count = sum(1 for c in claims if c.claim_type in SELL_TYPES)
            hold_count = sum(1 for c in claims if c.claim_type in HOLD_TYPES)
            neutral_count = len(claims) - buy_count - sell_count - hold_count
            total = len(claims)

            consensus_score = max(buy_count, sell_count, hold_count) / total if total > 0 else 0.0

            snapshot = ConsensusSnapshot(
                person_id=pid,
                time_bucket=now,
                buy_count=buy_count,
                sell_count=sell_count,
                hold_count=hold_count,
                neutral_count=neutral_count,
                consensus_score=round(consensus_score, 3),
            )
            session.add(snapshot)

            # Detect sentiment flip
            prev = prev_snapshots.get(pid)
            if prev:
                old_dominant = _dominant(prev.buy_count, prev.sell_count, prev.hold_count)
                new_dominant = _dominant(buy_count, sell_count, hold_count)
                if old_dominant != new_dominant and old_dominant and new_dominant:
                    flipped.append({
                        "entity_id": pid,
                        "canonical_name": people.get(pid, "Unknown"),
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
