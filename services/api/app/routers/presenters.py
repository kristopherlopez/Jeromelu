"""Admin endpoints for the Presenter Research review queue.

Workflow:
  POST /admin/presenters/research/{channel_id}     — run the agent
  GET  /admin/presenters/candidates?channel_id=…   — list filed candidates
  POST /admin/presenters/candidates/{id}/confirm   — promote into people +
                                                     source_presenters
  POST /admin/presenters/candidates/{id}/reject    — mark rejected
  GET  /admin/presenters/by-channel/{channel_id}   — confirmed + pending

Confirmation creates (or links) a `people` row and writes the
`source_presenters` association. Idempotent — re-confirming a candidate is a
no-op; the (channel_id, person_id) UNIQUE constraint catches double-confirm.

See docs/todo/source-presenters.md.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from jeromelu_shared.db import (
    Channel,
    MinerPresenterCandidate,
    Person,
    SourcePresenter,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..deps import get_db
from ..miner.presenter_research.agent import run_presenter_research

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    base = _SLUG_STRIP.sub("-", (name or "").lower()).strip("-")
    return base or "person"


def _unique_person_slug(session: Session, base: str) -> str:
    """Return `base` or `base-2`, `base-3`, … such that no `people.slug` matches."""
    candidate = base
    n = 2
    while True:
        hit = session.execute(select(Person.person_id).where(Person.slug == candidate).limit(1)).first()
        if hit is None:
            return candidate
        candidate = f"{base}-{n}"
        n += 1


def _candidate_to_dict(c: MinerPresenterCandidate) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "channel_id": str(c.channel_id),
        "name": c.name,
        "role": c.role,
        "evidence": c.evidence_json or [],
        "llm_confidence": c.llm_confidence,
        "notes": c.notes,
        "existing_person_id": str(c.existing_person_id) if c.existing_person_id else None,
        "status": c.status,
        "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None,
        "reviewed_by": c.reviewed_by,
        "confirmed_person_id": str(c.confirmed_person_id) if c.confirmed_person_id else None,
        "run_id": c.run_id,
        "discovered_at": c.discovered_at.isoformat(),
    }


def _confirmed_to_dict(sp: SourcePresenter, person_name: str) -> dict[str, Any]:
    return {
        "id": str(sp.id),
        "channel_id": str(sp.channel_id),
        "person_id": str(sp.person_id),
        "person_name": person_name,
        "role": sp.role,
        "is_regular": sp.is_regular,
        "since_ts": sp.since_ts.isoformat() if sp.since_ts else None,
        "confirmed_at": sp.confirmed_at.isoformat(),
        "confirmed_by": sp.confirmed_by,
        "candidate_id": str(sp.candidate_id) if sp.candidate_id else None,
    }


# ---------------------------------------------------------------------------
# POST /admin/presenters/research/{channel_id} — run the agent
# ---------------------------------------------------------------------------


class PresenterResearchTriggerBody(BaseModel):
    model: str | None = None
    dry_run: bool = False


@router.post("/admin/presenters/research/{channel_id}")
def trigger_presenter_research(
    channel_id: UUID,
    body: PresenterResearchTriggerBody = Body(default_factory=PresenterResearchTriggerBody),
    db: Session = Depends(get_db),
):
    """Run Presenter Research for one channel. Synchronous — typical
    runtime ~20–60s. Returns the run summary."""
    channel = db.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="channel not found")

    try:
        result = run_presenter_research(
            db,
            channel_id,
            model=body.model or "claude-sonnet-4-6",
            dry_run=body.dry_run,
        )
    except RuntimeError as e:
        # Most likely "ANTHROPIC_API_KEY not set"
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {
        "ok": True,
        "run_id": result.run_id,
        "channel_id": str(result.channel_id),
        "status": result.status,
        "candidates_filed": result.candidates_filed,
        "duplicates_skipped": result.duplicates_skipped,
        "turns_used": result.turns_used,
        "tool_calls": result.tool_calls,
        "estimated_cost_usd": result.estimated_cost_usd,
        "stop_reason": result.stop_reason,
        "notes": result.notes,
    }


# ---------------------------------------------------------------------------
# GET /admin/presenters/candidates — list filed candidates
# ---------------------------------------------------------------------------


@router.get("/admin/presenters/candidates")
def list_candidates(
    channel_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None, description="pending|confirmed|rejected"),
    limit: int = Query(default=200, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(MinerPresenterCandidate).order_by(MinerPresenterCandidate.discovered_at.desc())
    if channel_id is not None:
        stmt = stmt.where(MinerPresenterCandidate.channel_id == channel_id)
    if status:
        if status not in ("pending", "confirmed", "rejected"):
            raise HTTPException(status_code=400, detail="bad status")
        stmt = stmt.where(MinerPresenterCandidate.status == status)
    stmt = stmt.limit(limit)

    rows = db.execute(stmt).scalars().all()
    return {"ok": True, "count": len(rows), "items": [_candidate_to_dict(c) for c in rows]}


# ---------------------------------------------------------------------------
# GET /admin/presenters/by-channel/{channel_id} — confirmed + pending side-by-side
# ---------------------------------------------------------------------------


@router.get("/admin/presenters/by-channel/{channel_id}")
def by_channel(
    channel_id: UUID,
    db: Session = Depends(get_db),
):
    channel = db.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="channel not found")

    pending_rows = (
        db.execute(
            select(MinerPresenterCandidate)
            .where(
                MinerPresenterCandidate.channel_id == channel_id,
                MinerPresenterCandidate.status == "pending",
            )
            .order_by(
                MinerPresenterCandidate.role,
                MinerPresenterCandidate.llm_confidence.desc().nullslast(),
            )
        )
        .scalars()
        .all()
    )

    rejected_rows = (
        db.execute(
            select(MinerPresenterCandidate)
            .where(
                MinerPresenterCandidate.channel_id == channel_id,
                MinerPresenterCandidate.status == "rejected",
            )
            .order_by(MinerPresenterCandidate.reviewed_at.desc().nullslast())
            .limit(50)
        )
        .scalars()
        .all()
    )

    confirmed_join = db.execute(
        select(SourcePresenter, Person.canonical_name)
        .join(Person, Person.person_id == SourcePresenter.person_id)
        .where(SourcePresenter.channel_id == channel_id)
        .order_by(SourcePresenter.role, Person.canonical_name)
    ).all()

    return {
        "ok": True,
        "channel": {
            "channel_id": str(channel.channel_id),
            "name": channel.name,
            "platform": channel.platform,
            "url": channel.url,
        },
        "confirmed": [_confirmed_to_dict(sp, name) for (sp, name) in confirmed_join],
        "pending": [_candidate_to_dict(c) for c in pending_rows],
        "rejected": [_candidate_to_dict(c) for c in rejected_rows],
    }


# ---------------------------------------------------------------------------
# POST /admin/presenters/candidates/{id}/confirm
# ---------------------------------------------------------------------------


class ConfirmBody(BaseModel):
    existing_person_id: UUID | None = None
    role_override: str | None = None
    reviewed_by: str | None = None
    confirmed_by: str | None = None


@router.post("/admin/presenters/candidates/{candidate_id}/confirm")
def confirm_candidate(
    candidate_id: UUID,
    body: ConfirmBody = Body(default_factory=ConfirmBody),
    db: Session = Depends(get_db),
):
    """Promote a candidate into a confirmed presenter.

    If `existing_person_id` is provided, links to that Person. Otherwise
    creates a new `people` row with `canonical_name = candidate.name` and a
    unique slug. Always writes a `source_presenters` row (channel_id,
    person_id, role, candidate_id).

    Idempotent on re-confirm: if a `source_presenters` row already exists for
    (channel_id, person_id) the candidate is still marked confirmed and the
    existing association is returned.
    """
    candidate = db.get(MinerPresenterCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="candidate not found")

    if candidate.status == "confirmed" and candidate.confirmed_person_id is not None:
        # Already done — just return the existing association.
        existing_sp = db.execute(
            select(SourcePresenter).where(
                SourcePresenter.channel_id == candidate.channel_id,
                SourcePresenter.person_id == candidate.confirmed_person_id,
            )
        ).scalar_one_or_none()
        person = db.get(Person, candidate.confirmed_person_id)
        return {
            "ok": True,
            "status": "already-confirmed",
            "candidate": _candidate_to_dict(candidate),
            "person_id": str(candidate.confirmed_person_id),
            "person_name": person.canonical_name if person else None,
            "association": (_confirmed_to_dict(existing_sp, person.canonical_name) if existing_sp and person else None),
        }

    role = body.role_override or candidate.role
    if role not in ("host", "co-host", "regular", "frequent-guest"):
        raise HTTPException(status_code=400, detail="bad role")

    # Resolve / create Person.
    if body.existing_person_id is not None:
        person = db.get(Person, body.existing_person_id)
        if person is None:
            raise HTTPException(status_code=400, detail="existing_person_id not found")
        person_id = person.person_id
        person_name = person.canonical_name
    else:
        # Create a new Person from the candidate name. Slug must be unique.
        slug = _unique_person_slug(db, _slugify(candidate.name))
        new_person = Person(
            canonical_name=candidate.name,
            aliases=[],
            slug=slug,
            metadata_json={"created_by": "presenter_research_confirm"},
        )
        db.add(new_person)
        db.flush()  # populate person_id
        person_id = new_person.person_id
        person_name = new_person.canonical_name

    # Write the association. UNIQUE (channel_id, person_id) catches the
    # case where this person was already linked to this channel via a
    # different prior candidate.
    sp = SourcePresenter(
        channel_id=candidate.channel_id,
        person_id=person_id,
        role=role,
        is_regular=role in ("host", "co-host", "regular"),
        confirmed_by=body.confirmed_by or body.reviewed_by,
        candidate_id=candidate.id,
    )
    db.add(sp)
    try:
        db.flush()
        association_status = "created"
    except IntegrityError:
        db.rollback()
        # Existing association — refetch and treat as idempotent success.
        existing_sp = db.execute(
            select(SourcePresenter).where(
                SourcePresenter.channel_id == candidate.channel_id,
                SourcePresenter.person_id == person_id,
            )
        ).scalar_one()
        sp = existing_sp
        association_status = "already-exists"
        # Re-attach the candidate that we lost on the rollback.
        candidate = db.get(MinerPresenterCandidate, candidate_id)

    candidate.status = "confirmed"
    candidate.confirmed_person_id = person_id
    candidate.reviewed_at = datetime.now(UTC)
    candidate.reviewed_by = body.reviewed_by or body.confirmed_by
    db.commit()

    db.refresh(candidate)
    db.refresh(sp)

    return {
        "ok": True,
        "status": "confirmed",
        "association_status": association_status,
        "candidate": _candidate_to_dict(candidate),
        "person_id": str(person_id),
        "person_name": person_name,
        "association": _confirmed_to_dict(sp, person_name),
    }


# ---------------------------------------------------------------------------
# POST /admin/presenters/candidates/{id}/reject
# ---------------------------------------------------------------------------


class RejectBody(BaseModel):
    note: str | None = None
    reviewed_by: str | None = None


@router.post("/admin/presenters/candidates/{candidate_id}/reject")
def reject_candidate(
    candidate_id: UUID,
    body: RejectBody = Body(default_factory=RejectBody),
    db: Session = Depends(get_db),
):
    candidate = db.get(MinerPresenterCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="candidate not found")

    if candidate.status == "confirmed":
        raise HTTPException(
            status_code=409,
            detail="candidate already confirmed — cannot reject",
        )

    candidate.status = "rejected"
    candidate.reviewed_at = datetime.now(UTC)
    candidate.reviewed_by = body.reviewed_by
    if body.note:
        candidate.notes = f"{candidate.notes}\n[reviewer] {body.note}" if candidate.notes else f"[reviewer] {body.note}"
    db.commit()
    db.refresh(candidate)
    return {"ok": True, "candidate": _candidate_to_dict(candidate)}
