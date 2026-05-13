"""Walk current ``people`` rows and enrich them from nrl.com profile pages.

This is **enrichment**, not enumeration — it does not discover new
players. The 17 NRL clubs' top-grade rosters come from the SC seed
(:mod:`jeromelu_shared.players.roster`); this module walks each existing
``Person`` row, fetches their nrl.com profile via
:func:`jeromelu_shared.players.nrlcom.fetch_profile`, and promotes:

- ``people.dob``                — set if currently null (lifetime constant)
- ``people.image_url``          — always update (photos get refreshed)
- ``people.metadata_json.birthplace_text`` — set if currently empty
- ``player_attributes.height_cm``  — in-place update on diff (no SCD-2)
- ``player_attributes.weight_kg``  — in-place update on diff (no SCD-2)

Everything else from the JSON-LD (captaincy, jobTitle, etc.) is ignored
in v1 — see ``docs/agents/system/player-roster.md``.

Per-person overrides live in ``people.metadata_json.nrlcom``:

    {
      "slug":       "alternative-slug",   # optional, defaults to slugify(name)
      "team_short": "raiders",            # optional, defaults to team.short_name
      "skip":       true                  # optional, skip this player entirely
    }

After each run, the same block records ``last_checked``, ``last_status``
(``"ok"`` or ``"404"``), and ``tried_url`` for the operator to query
mismatches via SQL or surface them in the operator UI.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from jeromelu_shared.db.models import Person, PlayerAttributes, Team
from jeromelu_shared.players.nrlcom import (
    USER_AGENT,
    NrlProfile,
    fetch_profile,
)

logger = logging.getLogger(__name__)


def refresh_from_nrlcom(
    session: Session,
    *,
    team_filter: list[str] | None = None,
    rate_limit_sleep: float = 0.0,
    today: date | None = None,
) -> dict[str, Any]:
    """Enrich every current player row from nrl.com.

    Args:
        team_filter: Optional list of ``Team.short_name`` values (case-
            insensitive). When set, only players currently attached to
            those teams are walked. Useful for one-club test runs.
        rate_limit_sleep: Seconds to sleep between profile fetches.
            Sequential by design (sketch agreement); 0 is fine for ad-
            hoc runs against ~550 rows.
        today: Override "today" for ``last_checked`` timestamps; tests
            pass a fixed date.

    Returns counts plus the ``mismatches`` list (one entry per 404, with
    ``canonical_name``, ``supercoach_id``, ``team_short``, ``tried_url``).
    """
    today = today or date.today()
    counts = {
        "scanned": 0,
        "enriched": 0,
        "skipped_override": 0,
        "missing_profile": 0,
        "people_field_updates": 0,
        "attribute_field_updates": 0,
    }
    mismatches: list[dict[str, Any]] = []

    rows = session.execute(
        select(Person, PlayerAttributes, Team)
        .join(PlayerAttributes, PlayerAttributes.person_id == Person.person_id)
        .join(Team, Team.team_id == PlayerAttributes.team_id)
        .where(PlayerAttributes.is_current)
    ).all()

    if team_filter:
        wanted = {t.lower() for t in team_filter}
        rows = [r for r in rows if (r.Team.short_name or "").lower() in wanted]

    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=15.0) as client:
        for person, attrs, team in rows:
            counts["scanned"] += 1
            override = (person.metadata_json or {}).get("nrlcom") or {}

            if override.get("skip"):
                counts["skipped_override"] += 1
                continue

            team_short = (team.short_name or team.slug).split("_")[-1]
            try:
                profile, tried_url = fetch_profile(
                    person.canonical_name,
                    team_short,
                    client=client,
                    override_slug=override.get("slug"),
                    override_team_short=override.get("team_short"),
                )
            except httpx.HTTPError as e:
                # Surface upstream errors but don't blow up the whole run.
                logger.warning(
                    "nrlcom fetch error for %s (%s): %s",
                    person.canonical_name, team_short, e,
                )
                _mark_status(person, today, "error", str(e), tried_url=None)
                continue

            if profile is None:
                counts["missing_profile"] += 1
                logger.warning(
                    "nrlcom profile 404: %s (%s) tried=%s",
                    person.canonical_name, team_short, tried_url,
                )
                _mark_status(person, today, "404", None, tried_url=tried_url)
                mismatches.append({
                    "canonical_name": person.canonical_name,
                    "supercoach_id": person.supercoach_id,
                    "team_short": team_short,
                    "tried_url": tried_url,
                })
                continue

            people_changed = _promote_lifetime(person, profile)
            attrs_changed = _promote_slow_changing(attrs, profile)
            if people_changed:
                counts["people_field_updates"] += 1
            if attrs_changed:
                counts["attribute_field_updates"] += 1

            _mark_status(person, today, "ok", None, tried_url=tried_url)
            counts["enriched"] += 1

            if rate_limit_sleep:
                import time
                time.sleep(rate_limit_sleep)

    session.commit()
    logger.info(
        "nrlcom refresh complete: scanned=%d enriched=%d missing=%d skipped=%d",
        counts["scanned"], counts["enriched"],
        counts["missing_profile"], counts["skipped_override"],
    )
    return {"counts": counts, "mismatches": mismatches}


def _promote_lifetime(person: Person, profile: NrlProfile) -> bool:
    """Lifetime-constant promotion to the ``people`` row.

    - ``dob``: set if currently null. Never overwrite (it's a constant).
    - ``image_url``: always update — photos get refreshed each season.
    - ``metadata_json.birthplace_text``: set if currently empty.
    """
    changed = False
    if profile.dob and person.dob is None:
        person.dob = profile.dob
        changed = True
    if profile.image_url and person.image_url != profile.image_url:
        person.image_url = profile.image_url
        changed = True

    md = dict(person.metadata_json or {})
    if profile.birthplace_text and not md.get("birthplace_text"):
        md["birthplace_text"] = profile.birthplace_text
        person.metadata_json = md
        flag_modified(person, "metadata_json")
        changed = True
    return changed


def _promote_slow_changing(attrs: PlayerAttributes, profile: NrlProfile) -> bool:
    """In-place updates for height_cm / weight_kg.

    Per design decision (sketch #1): re-measurements are not SCD-2
    transitions. We update the current row in place so the historical
    timeline stays clean.
    """
    changed = False
    if profile.height_cm and attrs.height_cm != profile.height_cm:
        attrs.height_cm = profile.height_cm
        changed = True
    if profile.weight_kg and attrs.weight_kg != profile.weight_kg:
        attrs.weight_kg = profile.weight_kg
        changed = True
    return changed


def _mark_status(
    person: Person,
    today: date,
    status: str,
    error_text: str | None,
    *,
    tried_url: str | None,
) -> None:
    """Record the last refresh attempt under ``metadata_json.nrlcom``.

    Preserves user-supplied override keys (``slug``, ``team_short``,
    ``skip``); only the bookkeeping keys are touched.
    """
    md = dict(person.metadata_json or {})
    nrlcom = dict(md.get("nrlcom") or {})
    nrlcom["last_checked"] = today.isoformat()
    nrlcom["last_status"] = status
    if tried_url is not None:
        nrlcom["tried_url"] = tried_url
    if error_text is not None:
        nrlcom["last_error"] = error_text
    elif "last_error" in nrlcom and status == "ok":
        nrlcom.pop("last_error", None)
    md["nrlcom"] = nrlcom
    person.metadata_json = md
    flag_modified(person, "metadata_json")
