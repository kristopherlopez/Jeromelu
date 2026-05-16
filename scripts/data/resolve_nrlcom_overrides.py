"""One-shot operator script: auto-resolve nrl.com slug overrides.

Walks every ``people`` row currently flagged with
``metadata_json.nrlcom.last_status='404'`` (or ``'error'``) and probes a
small set of candidate slugs:

  1. Drop middle names / censored ``***`` tokens (handles ``Jack *** Bird``
     → ``jack-bird``, ``Cody John Hopwood`` → ``cody-hopwood``).
  2. Common first-name shortenings (``Thomas`` → ``Tom``, ``Joshua`` →
     ``Josh``, etc.).
  3. Combinations of (1) + (2).

First candidate that returns HTTP 200 wins — the slug is written to
``people.metadata_json.nrlcom.slug``. If all candidates 404, the person
is marked ``skip: true`` so the next refresh doesn't keep retrying.

After this runs, re-run the main refresh (``make prod-refresh-players-nrlcom``
or the local equivalent) — the overrides will route through to the right
profile URLs and the hit rate jumps.

Usage::

    python scripts/data/resolve_nrlcom_overrides.py
    python scripts/data/resolve_nrlcom_overrides.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "shared"))

from jeromelu_shared.db.models import Person, PersonAttributes, Team  # noqa: E402
from jeromelu_shared.players.nrlcom import (  # noqa: E402
    PROFILE_URL,
    USER_AGENT,
    slugify_name,
    slugify_team_short,
)


# Common first-name shortenings nrl.com prefers.
COMMON_SHORTENINGS: dict[str, list[str]] = {
    "thomas":     ["tom"],
    "matthew":    ["matt"],
    "daniel":     ["dan", "danny"],
    "joshua":     ["josh"],
    "christopher": ["chris"],
    "benjamin":   ["ben"],
    "william":    ["will", "billy", "bill"],
    "jonathan":   ["jon"],
    "anthony":    ["tony"],
    "michael":    ["mike", "mick"],
    "nathaniel":  ["nate", "nat"],
    "robert":     ["rob", "robbie"],
    "patrick":    ["pat", "paddy"],
    "samuel":     ["sam"],
    "andrew":     ["andy", "drew"],
    "david":      ["dave", "davy"],
    "james":      ["jamie", "jim", "jimmy"],
    "joseph":     ["joe"],
    "alexander":  ["alex"],
    "nicholas":   ["nick"],
    "edward":     ["ed", "eddie"],
    "tyler":      ["ty"],
    "stephen":    ["steve"],
    "richard":    ["rich", "rick"],
    "charles":    ["charlie"],
    "francis":    ["frank"],
    "vincent":    ["vince"],
    "zachary":    ["zach", "zac"],
    "jacob":      ["jake"],
    "isaac":      ["ike"],
    "harrison":   ["harry"],
    "henry":      ["harry"],
    "kelvin":     ["kel"],
    "kerrod":     ["kerry"],
}


def candidate_slugs(canonical_name: str, current_slug: str | None) -> list[str]:
    """Generate ordered candidate slugs to probe.

    Filters out:
      - ``current_slug`` (the one that already 404'd on the standard derivation)
      - duplicates
    """
    parts = canonical_name.strip().split()
    if not parts:
        return []

    # Drop censored middle names (***) and other middle words for matching.
    real_parts = [p for p in parts if not p.startswith("*") and not p.endswith("*")]
    first_last = []
    if len(real_parts) >= 2:
        first_last = [real_parts[0], real_parts[-1]]

    raw_candidates: list[list[str]] = []

    # Strategy A: drop middle/censored words → first + last
    if first_last and (len(parts) > 2 or any(p.startswith("*") for p in parts)):
        raw_candidates.append(first_last)

    # Strategy B: shortened first + last
    if first_last:
        first_lower = first_last[0].lower()
        for short in COMMON_SHORTENINGS.get(first_lower, []):
            raw_candidates.append([short, first_last[1]])

    # Strategy C: full original first + shortened last? — not common; skip.

    # Strategy D: just last name (some legends are slugged this way, e.g.
    # "Benji Marshall" might have been just "marshall" historically). Cheap
    # to include as a final fallback.
    if first_last:
        raw_candidates.append([first_last[1]])

    # Slugify and dedupe, dropping the original failed slug.
    seen = {current_slug or ""}
    out: list[str] = []
    for parts_list in raw_candidates:
        s = slugify_name(" ".join(parts_list))
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="probe and print results, don't write to DB")
    parser.add_argument("--rate-limit-ms", type=int, default=100,
                        help="sleep between HTTP probes (default 100ms)")
    args = parser.parse_args()

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://jeromelu_admin:localdev123@localhost:5440/jeromelu",
    )
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)

    with Session() as s, httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=15) as client:
        rows = s.execute(
            select(Person, PersonAttributes, Team)
            .join(PersonAttributes, PersonAttributes.person_id == Person.person_id)
            .join(Team, Team.team_id == PersonAttributes.team_id)
            .where(PersonAttributes.is_current)
        ).all()

        flagged = [
            (person, attrs, team)
            for person, attrs, team in rows
            if (person.metadata_json or {}).get("nrlcom", {}).get("last_status") in ("404", "error")
        ]
        print(f"Flagged for resolution: {len(flagged)}")

        resolved = 0
        skipped = 0
        for person, _attrs, team in flagged:
            md = dict(person.metadata_json or {})
            nrlcom = dict(md.get("nrlcom") or {})
            current = nrlcom.get("slug") or slugify_name(person.canonical_name)
            team_slug = slugify_team_short(team.short_name or team.slug.split("_")[-1])

            candidates = candidate_slugs(person.canonical_name, current_slug=current)
            hit_slug: str | None = None
            for cand in candidates:
                url = PROFILE_URL.format(team_short=team_slug, slug=cand)
                try:
                    r = client.get(url)
                except httpx.HTTPError:
                    continue
                if r.status_code == 200:
                    hit_slug = cand
                    break
                if args.rate_limit_ms:
                    time.sleep(args.rate_limit_ms / 1000)

            if hit_slug:
                resolved += 1
                action = f"-> slug={hit_slug!r}"
                if not args.dry_run:
                    nrlcom["slug"] = hit_slug
                    nrlcom.pop("last_status", None)  # let next refresh re-evaluate
                    md["nrlcom"] = nrlcom
                    person.metadata_json = md
                    flag_modified(person, "metadata_json")
            else:
                skipped += 1
                action = "-> skip:true"
                if not args.dry_run:
                    nrlcom["skip"] = True
                    md["nrlcom"] = nrlcom
                    person.metadata_json = md
                    flag_modified(person, "metadata_json")

            print(f"  {person.canonical_name:30s} ({team.short_name:10s}) {action}")

        if not args.dry_run:
            s.commit()

    print(f"\nresolved: {resolved}  skipped: {skipped}")


if __name__ == "__main__":
    main()
