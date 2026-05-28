"""Event generation activity — synthesise claims into feed events via LLM."""

import hashlib
import json
import logging
import uuid

from jeromelu_shared.db import (
    Claim,
    ClaimAssociation,
    Event,
    Person,
    SessionLocal,
    Source,
    SourceDocument,
)
from jeromelu_shared.llm import chat_json
from sqlalchemy.orm import joinedload
from temporalio import activity

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are JeromeLu, an NRL SuperCoach AI analyst. You write short, opinionated, \
first-person feed items about player trades, captain picks, and market movements.

Voice rules:
- First person ("I", "I'm", "my")
- Short punchy sentences. Max 2-3 sentences per item.
- NRL SuperCoach jargon: breakeven, PPM, base stats, ceiling, floor, price movement
- Opinionated — take a side, don't sit on the fence
- Reference player names exactly as provided
- Reference source creators with "via {creator}" style when relevant

You will receive a JSON object with:
- "claims": grouped claims from sources
- "consensus_shifts": entities where sentiment has flipped
- "reviews": past predictions to review against actual results

Return a JSON object with key "events", an array of event objects:
{
  "events": [
    {
      "event_type": "watching|signal|thinking|prediction|action|review|sys",
      "display_text": "The feed item text",
      "related_entity_names": ["Player Name"],
      "related_claim_ids": ["uuid"],
      "related_source_id": "uuid or null",
      "metadata": {}
    }
  ]
}

Event type guide:
- "watching": Reacting to what a source said. Observational, brief commentary.
- "signal": Consensus has shifted. Multiple sources now agree. Highlight the trend.
- "thinking": Analysis and reasoning. Connect the dots between claims and data.
- "prediction": Bold call. Make a specific prediction with conviction.
- "action": Trade decision or captain lock. Decisive, committed tone.
- "review": Reviewing a past prediction against actual results. Own the outcome.
- "sys": Pipeline activity summary (scans, extractions). Factual and terse.

Generate 1 event per logical grouping. Maximum 8 events per batch. \
Do NOT generate events for claims that are too weak (strength < 0.3). \
Every event must have at least one related_claim_id.\
"""


@activity.defn
async def fetch_unprocessed_claims() -> dict:
    """Find claims not yet referenced by any event. Return structured data for LLM.

    Returns dict with:
    - claims: list of claim dicts grouped by source
    - entity_map: {entity_id: canonical_name}
    - source_map: {source_id: {title, creator_name}}
    """
    session = SessionLocal()
    try:
        # Get all claim IDs already referenced by events
        from sqlalchemy import func

        processed_ids_sq = session.query(func.unnest(Event.related_claim_ids).label("cid")).subquery()

        # Find unprocessed claims (with subject person via claim_associations).
        unprocessed = (
            session.query(Claim)
            .join(ClaimAssociation, ClaimAssociation.claim_id == Claim.claim_id)
            .filter(~Claim.claim_id.in_(session.query(processed_ids_sq.c.cid)))
            .filter(
                ClaimAssociation.role == "subject",
                ClaimAssociation.person_id.isnot(None),
            )
            .options(joinedload(Claim.associations))
            .order_by(Claim.extracted_at)
            .all()
        )

        if not unprocessed:
            return {"claims": [], "entity_map": {}, "source_map": {}}

        # Build claim → subject person_id map
        subject_person_by_claim: dict = {}
        person_ids: set = set()
        for c in unprocessed:
            for a in c.associations:
                if a.role == "subject" and a.person_id:
                    subject_person_by_claim[c.claim_id] = a.person_id
                    person_ids.add(a.person_id)

        doc_ids = {c.document_id for c in unprocessed if c.document_id}

        # Load people (subjects)
        entity_map: dict = {}
        if person_ids:
            for p in session.query(Person).filter(Person.person_id.in_(person_ids)).all():
                entity_map[str(p.person_id)] = p.canonical_name

        # Load sources via documents
        source_map = {}
        if doc_ids:
            for doc, src in (
                session.query(SourceDocument, Source)
                .join(Source, Source.source_id == SourceDocument.source_id)
                .filter(SourceDocument.document_id.in_(doc_ids))
                .all()
            ):
                source_map[str(doc.document_id)] = {
                    "source_id": str(src.source_id),
                    "title": src.title,
                    "creator_name": src.creator_name,
                }

        claims_data = []
        for c in unprocessed:
            doc_info = source_map.get(str(c.document_id), {})
            subject_pid = subject_person_by_claim.get(c.claim_id)
            claims_data.append(
                {
                    "claim_id": str(c.claim_id),
                    "claim_type": c.claim_type,
                    "claim_text": c.claim_text,
                    "polarity": c.polarity,
                    "strength": c.strength,
                    "player_name": entity_map.get(str(subject_pid), "Unknown") if subject_pid else "Unknown",
                    "entity_id": str(subject_pid) if subject_pid else None,
                    "source_id": doc_info.get("source_id"),
                    "source_title": doc_info.get("title"),
                    "source_creator": doc_info.get("creator_name"),
                    "effective_round": c.effective_round,
                    "season": c.season,
                }
            )

        logger.info("Found %d unprocessed claims", len(claims_data))
        return {
            "claims": claims_data,
            "entity_map": entity_map,
            "source_map": {
                v["source_id"]: {"title": v["title"], "creator_name": v["creator_name"]}
                for v in source_map.values()
                if v.get("source_id")
            },
        }

    finally:
        session.close()


@activity.defn
async def generate_feed_events(
    claims_data: dict,
    consensus_shifts: list[dict],
    review_data: list[dict],
) -> list[dict]:
    """Call the LLM to synthesise claims into feed events.

    Returns list of event dicts ready for persist_events.
    """
    claims = claims_data.get("claims", [])
    if not claims and not consensus_shifts and not review_data:
        logger.info("No input data for event generation")
        return []

    # Build the user prompt payload
    payload = {
        "claims": claims,
        "consensus_shifts": consensus_shifts,
        "reviews": review_data,
    }

    user_prompt = json.dumps(payload, indent=2)

    try:
        result = chat_json(SYSTEM_PROMPT, user_prompt)
        events = result.get("events", [])
    except Exception:
        logger.exception("LLM call failed for event generation")
        return []

    # Validate and normalize
    valid_types = {"watching", "signal", "thinking", "prediction", "action", "review", "sys"}
    validated = []

    for ev in events:
        event_type = ev.get("event_type", "")
        display_text = ev.get("display_text", "")

        if event_type not in valid_types or not display_text:
            logger.warning("Skipping invalid event: type=%s text=%s", event_type, display_text[:50])
            continue

        # Resolve entity names to IDs
        entity_names = ev.get("related_entity_names", [])
        entity_map = claims_data.get("entity_map", {})
        name_to_id = {v: k for k, v in entity_map.items()}
        related_entity_ids = [name_to_id[n] for n in entity_names if n in name_to_id]

        validated.append(
            {
                "event_type": event_type,
                "display_text": display_text,
                "display_mode": event_type,  # display_mode = event_type in new schema
                "related_entity_ids": related_entity_ids,
                "related_claim_ids": ev.get("related_claim_ids", []),
                "related_source_id": ev.get("related_source_id"),
                "metadata": ev.get("metadata", {}),
            }
        )

    logger.info("LLM generated %d valid events from %d raw", len(validated), len(events))
    return validated


@activity.defn
async def persist_events(events: list[dict]) -> dict:
    """Write Event rows to DB with deduplication via immutable_hash.

    Returns {inserted: int, skipped: int}.
    """
    if not events:
        return {"inserted": 0, "skipped": 0}

    session = SessionLocal()
    try:
        inserted = 0
        skipped = 0

        for ev in events:
            hash_val = _compute_hash(ev)

            # Dedup check
            exists = session.query(Event.event_id).filter(Event.immutable_hash == hash_val).first()
            if exists:
                skipped += 1
                continue

            event = Event(
                event_type=ev["event_type"],
                display_text=ev["display_text"],
                display_mode=ev["display_mode"],
                related_entity_ids=[uuid.UUID(eid) for eid in ev.get("related_entity_ids", [])],
                related_claim_ids=[uuid.UUID(cid) for cid in ev.get("related_claim_ids", [])],
                related_source_id=uuid.UUID(ev["related_source_id"]) if ev.get("related_source_id") else None,
                metadata_json=ev.get("metadata", {}),
                immutable_hash=hash_val,
            )
            session.add(event)
            inserted += 1

        session.commit()
        logger.info("Persisted %d events (%d skipped as duplicates)", inserted, skipped)
        return {"inserted": inserted, "skipped": skipped}

    except Exception:
        session.rollback()
        logger.exception("Failed to persist events")
        raise
    finally:
        session.close()


def _compute_hash(ev: dict) -> str:
    """Deterministic hash for deduplication."""
    claim_ids = sorted(ev.get("related_claim_ids", []))
    payload = json.dumps(
        {
            "event_type": ev["event_type"],
            "display_text": ev["display_text"],
            "related_claim_ids": claim_ids,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()
