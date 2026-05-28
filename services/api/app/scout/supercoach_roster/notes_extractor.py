"""Extract SC editorial notes[] as claims+quotes attributed to the synthetic
SuperCoach Editorial advisor.

Each player in the SC players-cf response carries a `notes[]` array of
editorial commentary (~204 of 550 players have notes, often multiple).
Each note has `{player_id, note, created_on}`. We treat each as one
opinionated claim attributed to a synthetic "SuperCoach Editorial" person.

Idempotency:
  Existing (said_at_reference, quoted_text) tuples are queried once at the
  start, used as a Python set to skip duplicates. No DB unique constraint
  required — the set covers it.

Claim type heuristic:
  Simple keyword match over the note text. claim_type CHECK constraint
  allows 'buy', 'sell', 'hold', 'captain', 'avoid', 'breakout',
  'matchup_edge'. Default to 'hold' (uncertain commentary) when no
  keyword matches.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from jeromelu_shared.db.models import (
    Claim,
    ClaimAssociation,
    Person,
    Quote,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Fixed UUIDs seeded in migration 061
SC_EDITORIAL_PERSON_ID = "aaaaaaaa-0000-4000-8000-000000000001"
SC_EDITORIAL_SOURCE_ID = "aaaaaaaa-0000-4000-8000-000000000002"
SC_EDITORIAL_DOCUMENT_ID = "aaaaaaaa-0000-4000-8000-000000000003"


# Simple keyword → claim_type heuristic. Conservative: most uncertain
# commentary falls to 'hold'. The CHECK constraint on claims.claim_type
# enforces the enum.
_CLAIM_TYPE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(captain|skipper)\b", re.I), "captain"),
    (re.compile(r"\b(avoid|stay away|don'?t pick|fade)\b", re.I), "avoid"),
    (re.compile(r"\b(breakout|pod|differential|sleeper)\b", re.I), "breakout"),
    (re.compile(r"\b(buy|bullish|lock in|must.have|grab)\b", re.I), "buy"),
    (re.compile(r"\b(sell|drop|trade out|move on|cut)\b", re.I), "sell"),
]


def classify_claim_type(note_text: str) -> str:
    """Map note prose to a claim_type enum value. Default 'hold'."""
    for pattern, claim_type in _CLAIM_TYPE_PATTERNS:
        if pattern.search(note_text):
            return claim_type
    return "hold"


def extract_notes_as_claims(
    db: Session,
    *,
    sc_players: list[dict[str, Any]],
) -> dict[str, int]:
    """For each SC player with notes[], persist each note as a quote + claim
    pair attributed to the synthetic SC Editorial advisor.

    Args:
        sc_players: list of player dicts as returned by SC players-cf.
            Each carries `id` (SC player_id) and `notes[]`.

    Returns:
        Counts: {notes_seen, notes_inserted, players_with_notes,
                 player_unmatched, already_present}.
    """
    notes_seen = 0
    notes_inserted = 0
    players_with_notes = 0
    player_unmatched = 0
    already_present = 0

    # 1. Build SC player_id → person_id lookup once.
    sc_ids_with_notes = [p["id"] for p in sc_players if p.get("notes")]
    person_by_sc_id: dict[int, str] = {}
    if sc_ids_with_notes:
        rows = db.execute(
            select(Person.person_id, Person.supercoach_id).where(Person.supercoach_id.in_(sc_ids_with_notes))
        ).all()
        person_by_sc_id = {sc_id: str(pid) for pid, sc_id in rows}

    # 2. Pre-fetch existing (said_at_reference, quoted_text) for the synthetic
    #    editorial speaker — dedup happens against this set.
    existing: set[tuple[str, str]] = set()
    rows = db.execute(
        select(Quote.said_at_reference, Quote.quoted_text).where(Quote.speaker_person_id == SC_EDITORIAL_PERSON_ID)
    ).all()
    for said_at, quoted_text in rows:
        existing.add((said_at or "", quoted_text or ""))

    # 3. Walk each player's notes
    for player in sc_players:
        notes = player.get("notes") or []
        if not notes:
            continue
        players_with_notes += 1

        sc_id = player.get("id")
        subject_person_id = person_by_sc_id.get(sc_id)
        if subject_person_id is None:
            player_unmatched += 1
            continue

        for note in notes:
            notes_seen += 1
            note_text = (note.get("note") or "").strip()
            created_on = (note.get("created_on") or "").strip()
            if not note_text or not created_on:
                continue
            if (created_on, note_text) in existing:
                already_present += 1
                continue

            quote = Quote(
                document_id=SC_EDITORIAL_DOCUMENT_ID,
                speaker_person_id=SC_EDITORIAL_PERSON_ID,
                quoted_text=note_text,
                said_at_reference=created_on,
                confidence=1.0,
            )
            db.add(quote)
            db.flush()  # populate quote.quote_id

            claim = Claim(
                document_id=SC_EDITORIAL_DOCUMENT_ID,
                quote_id=quote.quote_id,
                claim_type=classify_claim_type(note_text),
                claim_text=note_text,
                payload_json={
                    "source": "supercoach-editorial-notes",
                    "sc_player_id": sc_id,
                    "created_on": created_on,
                },
            )
            db.add(claim)
            db.flush()  # populate claim.claim_id

            db.add(
                ClaimAssociation(
                    claim_id=claim.claim_id,
                    role="subject",
                    person_id=subject_person_id,
                )
            )
            existing.add((created_on, note_text))
            notes_inserted += 1

    db.commit()

    logger.info(
        "sc-editorial notes extract: seen=%d inserted=%d already_present=%d players_with_notes=%d unmatched=%d",
        notes_seen,
        notes_inserted,
        already_present,
        players_with_notes,
        player_unmatched,
    )

    return {
        "notes_seen": notes_seen,
        "notes_inserted": notes_inserted,
        "notes_already_present": already_present,
        "players_with_notes": players_with_notes,
        "players_unmatched": player_unmatched,
    }


__all__ = [
    "SC_EDITORIAL_DOCUMENT_ID",
    "SC_EDITORIAL_PERSON_ID",
    "SC_EDITORIAL_SOURCE_ID",
    "classify_claim_type",
    "extract_notes_as_claims",
]
