"""Build a keyterm vocabulary for Deepgram from the canonical roster.

Deepgram's `keyterm` parameter biases the model toward specific terms. Hard
cap is 500 tokens / request; their own guidance is 20-50 high-quality terms.
We bias toward NRL surnames and team identifiers since those are the
highest-confusion tokens. First names rarely get garbled.

Source of truth: the `people` and `teams` tables. `players.yaml` is not
consulted — the backend roster is canonical.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from jeromelu_shared.db import Person, PersonRole, PlayerAttributes, Team
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Deepgram nova-3 docs: 500 tokens hard, 20-50 best, "well under" 100 advised.
# We hold to ~100 entries with a token-count headroom; expansion to topic-
# targeted selection is a separate effort.
KEYTERM_CAP = 100

_NRL_GRADES = ("nrl", "nrlw")


def _surname(canonical_name: str) -> str | None:
    """Best-effort surname extraction.

    Most NRL canonical_names are 'First Last'; some are 'First Mid Last' (e.g.
    'Reuben Garrick-Tu'). We take the final whitespace-separated token, since
    that's what tends to be misheard. Returns None for single-token names —
    those go in as-is rather than being processed.
    """
    parts = canonical_name.split()
    if len(parts) < 2:
        return None
    return parts[-1]


def _truncate(items: Iterable[str], cap: int) -> list[str]:
    """Dedupe (case-insensitive), preserve order, truncate to cap."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if not item:
            continue
        item = item.strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= cap:
            break
    return out


def build_keyterms(session: Session) -> list[str]:
    """Compose the keyterm list, ordered by priority.

    Priority bands (each one fills before the next is consulted):
        1. Active-player surnames (NRL + NRLW)
        2. Team short_names (NRL + NRLW)
        3. Team aliases
        4. Active-player aliases (nicknames)

    Per-band caps prevent a long surname pool from crowding out teams or
    aliases. Hard-capped at ``KEYTERM_CAP`` entries.
    """
    pa_alias = PlayerAttributes
    pr_alias = PersonRole

    player_stmt = (
        select(Person.canonical_name, Person.aliases)
        .join(pr_alias, pr_alias.person_id == Person.person_id)
        .join(pa_alias, pa_alias.person_id == Person.person_id)
        .join(Team, Team.team_id == pa_alias.team_id)
        .where(pr_alias.role == "player")
        .where(pr_alias.effective_to.is_(None))
        .where(pa_alias.is_current.is_(True))
        .where(Team.grade.in_(_NRL_GRADES))
        .where(Team.active.is_(True))
    )

    surnames: list[str] = []
    aliases: list[str] = []
    for canonical_name, alias_list in session.execute(player_stmt).all():
        surname = _surname(canonical_name or "")
        if surname:
            surnames.append(surname)
        for alias in alias_list or []:
            aliases.append(alias)

    team_stmt = select(Team.short_name, Team.aliases).where(Team.grade.in_(_NRL_GRADES)).where(Team.active.is_(True))
    team_short: list[str] = []
    team_aliases: list[str] = []
    for short_name, alias_list in session.execute(team_stmt).all():
        if short_name:
            team_short.append(short_name)
        for alias in alias_list or []:
            team_aliases.append(alias)

    bands = [
        _truncate(surnames, 60),
        _truncate(team_short, 25),
        _truncate(team_aliases, 10),
        _truncate(aliases, 25),
    ]
    combined = _truncate([t for band in bands for t in band], KEYTERM_CAP)
    logger.info(
        "Built %d keyterms (surnames=%d/%d player_aliases=%d/%d team_short=%d/%d team_aliases=%d/%d)",
        len(combined),
        len(bands[0]),
        len(surnames),
        len(bands[3]),
        len(aliases),
        len(bands[1]),
        len(team_short),
        len(bands[2]),
        len(team_aliases),
    )
    return combined
