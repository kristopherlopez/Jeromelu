"""Feed API — serve Events as FeedItems for the frontend."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from jeromelu_shared.db import Event, Person, Prediction, Source
from jeromelu_shared.rag import ask_jeromelu
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..deps import get_db

router = APIRouter()

# Map DB event_type → frontend FeedItemType
EVENT_TYPE_MAP = {
    "watching": "watching",
    "signal": "signal",
    "thinking": "thinking",
    "prediction": "prediction",
    "action": "action",
    "review": "review",
    "sys": "sys",
    "question": "question",
    "answer": "answer",
}

# Filter groups map to display_mode sets
FILTER_MAP = {
    "thoughts": {"watching", "signal", "thinking", "review"},
    "actions": {"action", "sys"},
    "predictions": {"prediction"},
    "chat": {"question", "answer"},
}


def _event_to_item(ev: Event, entities: dict, sources: dict, predictions: dict) -> dict:
    """Serialize an Event to a feed item dict.

    Post-mig-038: entities maps person_id → Person. The "player filter" loosens
    to "any person" since person rows aren't typed by role at this layer; events
    is deferred for full redesign so this is acceptable.
    """
    # Person/player refs
    players = []
    if ev.related_entity_ids:
        for eid in ev.related_entity_ids:
            person = entities.get(eid)
            if person and person.canonical_name:
                players.append(
                    {
                        "name": person.canonical_name,
                        "entityId": str(person.person_id),
                    }
                )

    # Source ref (single, from FK)
    source = None
    if ev.related_source_id and ev.related_source_id in sources:
        s = sources[ev.related_source_id]
        source = {
            "title": s.title,
            "sourceId": str(s.source_id),
            "creator": s.creator_name,
        }

    # Multiple sources (from answer metadata)
    sources_list = None
    if ev.event_type == "answer" and ev.metadata_json:
        raw_sources = ev.metadata_json.get("sources", [])
        if raw_sources:
            sources_list = [
                {
                    "title": rs.get("title", ""),
                    "sourceId": rs.get("source_id", ""),
                    "creator": rs.get("creator_name"),
                }
                for rs in raw_sources
            ]

    # Prediction ref
    prediction = None
    if ev.related_prediction_id and ev.related_prediction_id in predictions:
        p = predictions[ev.related_prediction_id]
        status = "pending"
        if p.resolution_status == "correct":
            status = "correct"
        elif p.resolution_status == "wrong":
            status = "wrong"
        prediction = {"status": status}
    elif ev.event_type == "review" and ev.metadata_json:
        prediction = {
            "status": ev.metadata_json.get("resolution_status", "pending"),
            "outcome": ev.metadata_json.get("outcome"),
        }

    item = {
        "id": str(ev.event_id),
        "type": EVENT_TYPE_MAP.get(ev.event_type, ev.event_type),
        "text": ev.display_text,
        "timestamp": ev.created_at.isoformat(),
        "players": players if players else None,
        "source": source,
        "prediction": prediction,
    }

    if sources_list:
        item["sources"] = sources_list

    return item


@router.get("/feed")
def get_feed(
    limit: int = Query(default=50, ge=1, le=200),
    before: datetime | None = Query(default=None),
    filter: str | None = Query(default=None),
    entity_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Paginated feed of events."""
    query = db.query(Event).filter(Event.visibility == "public").order_by(Event.created_at.desc())

    # Cursor pagination
    if before:
        query = query.filter(Event.created_at < before)

    # Filter by category
    if filter and filter in FILTER_MAP:
        modes = FILTER_MAP[filter]
        query = query.filter(Event.display_mode.in_(modes))

    # Filter by entity
    if entity_id:
        query = query.filter(Event.related_entity_ids.any(entity_id))

    events = query.limit(limit + 1).all()

    # Determine next cursor
    has_more = len(events) > limit
    if has_more:
        events = events[:limit]
    next_before = events[-1].created_at.isoformat() if events and has_more else None

    # Batch-load related entities
    all_entity_ids: set[uuid.UUID] = set()
    for ev in events:
        if ev.related_entity_ids:
            all_entity_ids.update(ev.related_entity_ids)

    entities: dict[uuid.UUID, Person] = {}
    if all_entity_ids:
        for p in db.query(Person).filter(Person.person_id.in_(all_entity_ids)).all():
            entities[p.person_id] = p

    # Batch-load related sources
    source_ids = {ev.related_source_id for ev in events if ev.related_source_id}
    sources: dict[uuid.UUID, Source] = {}
    if source_ids:
        for s in db.query(Source).filter(Source.source_id.in_(source_ids)).all():
            sources[s.source_id] = s

    # Batch-load related predictions
    pred_ids = {ev.related_prediction_id for ev in events if ev.related_prediction_id}
    predictions: dict[uuid.UUID, Prediction] = {}
    if pred_ids:
        for p in db.query(Prediction).filter(Prediction.prediction_id.in_(pred_ids)).all():
            predictions[p.prediction_id] = p

    items = [_event_to_item(ev, entities, sources, predictions) for ev in events]

    return {
        "items": items,
        "next_before": next_before,
    }


# ---------------------------------------------------------------------------
# POST /api/feed/ask — Ask JeromeLu, persist Q&A as feed events
# ---------------------------------------------------------------------------


class FeedAskRequest(BaseModel):
    question: str = Field(..., max_length=500)
    temperature: str = Field(default="sharp", pattern=r"^(straight|sharp|roast)$")


@router.post("/feed/ask")
def feed_ask(body: FeedAskRequest, db: Session = Depends(get_db)):
    """Ask JeromeLu a question. Creates question + answer events in the feed."""
    # 1. Create the question event
    question_event = Event(
        event_type="question",
        display_mode="question",
        display_text=body.question,
        visibility="public",
        metadata_json={"temperature": body.temperature},
    )
    question_event.immutable_hash = question_event.compute_hash()
    db.add(question_event)
    db.flush()  # get event_id and created_at assigned

    # 2. Run RAG pipeline
    result = ask_jeromelu(db, body.question, body.temperature)

    # 3. Create the answer event
    player_entity_ids = [uuid.UUID(p["entity_id"]) for p in result["players"]]

    answer_event = Event(
        event_type="answer",
        display_mode="answer",
        display_text=result["answer"],
        visibility="public",
        related_entity_ids=player_entity_ids,
        metadata_json={
            "sources": result["sources"],
            "kb_entries_used": result["kb_entries_used"],
            "temperature": body.temperature,
            "question_event_id": str(question_event.event_id),
        },
    )
    answer_event.immutable_hash = answer_event.compute_hash()
    db.add(answer_event)
    db.commit()

    # 4. Load people for serialization (player_entity_ids == person_ids by mig 036).
    entities: dict[uuid.UUID, object] = {}
    if player_entity_ids:
        for p in db.query(Person).filter(Person.person_id.in_(player_entity_ids)).all():
            entities[p.person_id] = p

    return {
        "question_item": _event_to_item(question_event, entities, {}, {}),
        "answer_item": _event_to_item(answer_event, entities, {}, {}),
    }
